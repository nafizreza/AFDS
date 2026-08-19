from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import uuid
from copy import deepcopy
from typing import Any

from ..classification.rfalter import ThresholdClassifier
from ..core.config import ConfigurationError, ConfigurationService, checksum
from ..domain.types import ApiError, ControlOwner, SystemState
from ..hardware.protocol import Command
from ..hardware.serial_adapter import HardwareError, SerialHardware
from ..persistence.database import Database
from ..services.events import EventHub
from ..vision.yolo26_service import VisionError, Yolo26VisionService


ACTIVE_STATES = {
    SystemState.OPENING_VALVE,
    SystemState.FEEDING,
    SystemState.CLOSING_VALVE,
    SystemState.WAITING_FOR_FRUIT,
    SystemState.ACQUIRING,
    SystemState.CLASSIFYING,
    SystemState.SORTING_SAFE,
    SystemState.SORTING_UNSAFE,
    SystemState.PURGING,
    SystemState.CYCLE_COMPLETE,
}


class AFDSController:
    def __init__(self):
        self.config_service = ConfigurationService()
        self.database = Database()
        self.events = EventHub()
        self.hardware = SerialHardware(self.config_service.active, self._hardware_event)
        self.vision = Yolo26VisionService(self.config_service.active)
        self.classifier = ThresholdClassifier(self.config_service.thresholds)
        self.state = SystemState.DISCONNECTED
        self.state_entered_at = dt.datetime.now(dt.timezone.utc)
        self.owner = ControlOwner.NONE
        self.state_version = 0
        self.operator: str | None = None
        self.session_id: str | None = None
        self.cycle_id: str | None = None
        self.cycle_number = 0
        self.stop_after_current = False
        self.last_error: dict[str, Any] | None = None
        self.last_detection: dict[str, Any] | None = None
        self.last_classification: dict[str, Any] | None = None
        self._lock = asyncio.Lock()
        self._maintenance_capture_lock = asyncio.Lock()
        self._cycle_task: asyncio.Task | None = None
        self._pause_gate = asyncio.Event()
        self._pause_gate.set()
        self._state_before_pause = SystemState.READY
        self._summary = {"attempted": 0, "fresh": 0, "unsafe": 0, "inconclusive": 0}

    async def startup(self) -> None:
        self.database.initialize()
        await self._publish("system_ready", {"message": "Backend is ready; hardware is not initialized"})

    async def shutdown(self) -> None:
        if self._cycle_task:
            self._cycle_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cycle_task
        with contextlib.suppress(Exception):
            if self.hardware.connected:
                await self.hardware.stop_telemetry()
                await self.hardware.safe_state()
        await self.hardware.disconnect()
        await self.vision.close()

    def snapshot(self) -> dict[str, Any]:
        config = self.config_service.active
        return {
            "state": self.state.value,
            "stateEnteredAt": self.state_entered_at.isoformat(),
            "stateVersion": self.state_version,
            "owner": self.owner.value,
            "operator": self.operator,
            "sessionId": self.session_id,
            "cycleId": self.cycle_id,
            "cycleNumber": self.cycle_number,
            "stopAfterCurrent": self.stop_after_current,
            "lastError": self.last_error,
            "lastDetection": self.last_detection,
            "lastClassification": self.last_classification,
            "hardware": self.hardware.snapshot(),
            "vision": self.vision.snapshot(),
            "summary": deepcopy(self._summary),
            "configuration": {
                "version": config.get("configurationVersion"),
                "checksum": checksum(config),
                "thresholdProfile": self.config_service.thresholds.get("profileVersion"),
                "thresholdsCommissioned": self.config_service.thresholds.get("commissioned", False),
                "timings": {
                    "samplingSeconds": float(config["sampling"]["durationSeconds"]),
                    "purgeSeconds": float(config["purge"]["durationSeconds"]),
                },
            },
            "controls": self._control_permissions(),
        }

    def _control_permissions(self) -> dict[str, Any]:
        state = self.state
        return {
            "initialize": state in {SystemState.DISCONNECTED, SystemState.ERROR, SystemState.E_STOPPED},
            "startAutomatic": state == SystemState.READY,
            "pause": state in ACTIVE_STATES,
            "resume": state == SystemState.PAUSED,
            "stopAfterCurrent": self.session_id is not None and state not in {SystemState.E_STOPPED, SystemState.DISCONNECTED},
            "enterManual": state in {SystemState.READY, SystemState.ATTENTION_REQUIRED, SystemState.PAUSED},
            "enterMaintenance": self.session_id is None and state in {SystemState.READY, SystemState.DISCONNECTED, SystemState.ERROR},
            "manualCommand": state in {SystemState.MANUAL, SystemState.MAINTENANCE},
            "retryFeed": state == SystemState.ATTENTION_REQUIRED,
            "softwareEstop": True,
        }

    def check_version(self, expected: int) -> None:
        if expected != self.state_version:
            raise ApiError("STALE_STATE", f"Expected state version {expected}; current version is {self.state_version}")

    async def _transition(self, state: SystemState, *, owner: ControlOwner | None = None, detail: dict[str, Any] | None = None) -> None:
        previous = self.state
        self.state = state
        self.state_entered_at = dt.datetime.now(dt.timezone.utc)
        if owner is not None:
            self.owner = owner
        self.state_version += 1
        payload = {"from": previous.value, "to": state.value, "stateVersion": self.state_version, **(detail or {})}
        self.database.audit("state_transition", payload, actor=self.operator or "system", session_id=self.session_id, cycle_id=self.cycle_id)
        await self._publish("state", self.snapshot())

    async def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        await self.events.publish(topic, payload)

    async def _hardware_event(self, topic: str, payload: dict[str, Any]) -> None:
        self.database.audit(topic, payload, session_id=self.session_id, cycle_id=self.cycle_id)
        await self._publish(topic, payload)

    async def initialize(self, operator: str, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if self.state not in {SystemState.DISCONNECTED, SystemState.ERROR, SystemState.E_STOPPED}:
                raise ApiError("INVALID_STATE", "Initialize is not valid in the current state")
            self.operator = operator
            self.last_error = None
            await self._transition(SystemState.INITIALIZING, owner=ControlOwner.NONE)
        try:
            await self.hardware.connect()
            await self.hardware.command(Command.INITIALIZE, {
                "pins": self.config_service.pins,
                "servos": self.config_service.active["servos"],
            })
            await self.hardware.safe_state()
            await self.hardware.start_telemetry(float(self.config_service.active["sampling"]["targetRateHz"]), force=True)
            await self.vision.initialize()
        except (HardwareError, VisionError) as exc:
            self.last_error = {"code": "PREFLIGHT_FAILED", "message": str(exc)}
            await self._transition(SystemState.ERROR, detail=self.last_error)
            return self.snapshot()
        await self._transition(SystemState.READY, owner=ControlOwner.NONE)
        return self.snapshot()

    async def start_automatic(self, operator: str, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if self.state != SystemState.READY or self.session_id or self._cycle_task and not self._cycle_task.done():
                raise ApiError("INVALID_STATE", "Automatic mode requires READY with no active cycle")
            self.operator = operator
            self.owner = ControlOwner.AUTOMATION
            self.stop_after_current = False
            self.session_id = f"SESSION-{uuid.uuid4().hex[:12].upper()}"
            self.cycle_number = 0
            self._summary = {"attempted": 0, "fresh": 0, "unsafe": 0, "inconclusive": 0}
            self.database.create_session(self.session_id, operator, checksum(self.config_service.active))
            self._cycle_task = asyncio.create_task(self._automatic_loop(), name="afds-automatic-cycle")
            await self._publish("session_started", self.snapshot())
            return self.snapshot()

    async def _automatic_loop(self) -> None:
        try:
            while self.session_id and not self.stop_after_current:
                completed = await self._run_one_cycle()
                if not completed:
                    return
                if self.stop_after_current:
                    break
                await self._transition(SystemState.READY, owner=ControlOwner.AUTOMATION)
                await asyncio.sleep(0.4)
            await self._finish_session("COMPLETED")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = {"code": "CYCLE_FAILED", "message": str(exc)}
            await self._transition(SystemState.ERROR, detail=self.last_error)

    async def _run_one_cycle(self) -> bool:
        assert self.session_id
        config = self.config_service.active
        self.cycle_number += 1
        self.cycle_id = f"FRUIT-{uuid.uuid4().hex[:12].upper()}"
        self._summary["attempted"] += 1
        self.database.create_cycle(self.cycle_id, self.session_id, self.cycle_number)

        await self._transition(SystemState.OPENING_VALVE)
        valve = config["servos"]["inletValve"]
        await self.hardware.command(Command.VALVE_OPEN, valve, session_id=self.session_id, cycle_id=self.cycle_id)
        await self._checkpoint()

        await self._transition(SystemState.FEEDING)
        feeder = config["feeder"]
        await self.hardware.command(Command.FEED_ONE, feeder, session_id=self.session_id, cycle_id=self.cycle_id, completion_timeout=float(feeder["completionTimeoutSeconds"]))
        await self._checkpoint()

        await self._transition(SystemState.CLOSING_VALVE)
        await self.hardware.command(Command.VALVE_CLOSE, valve, session_id=self.session_id, cycle_id=self.cycle_id)
        await self._checkpoint()

        await self._transition(SystemState.WAITING_FOR_FRUIT)
        detection = await self.vision.wait_for_stable_fruit(float(config["vision"]["presenceTimeoutSeconds"]))
        if detection is None:
            self.database.update_cycle(self.cycle_id, status="NO_FRUIT")
            await self._transition(SystemState.ATTENTION_REQUIRED, owner=ControlOwner.NONE, detail={"reason": "NO_FRUIT", "message": "No stable fruit was detected. Inspect the reservoir and feeder before retrying."})
            return False

        self.last_detection = detection
        selected = detection["selected"]
        self.database.update_cycle(self.cycle_id, fruit_type=selected["fruitClass"], yolo_confidence=selected["confidence"], detection=detection)
        await self._publish("detection", detection)

        await self._transition(SystemState.ACQUIRING)
        sampling = config["sampling"]
        samples = await self.hardware.collect_sensors(float(sampling["durationSeconds"]), float(sampling["targetRateHz"]), self.session_id, self.cycle_id)
        self.database.save_samples(self.cycle_id, samples)
        await self._checkpoint()

        await self._transition(SystemState.CLASSIFYING)
        classification = self.classifier.classify(selected["fruitClass"], samples).to_dict()
        snapshot_url = detection.get("snapshotUrl")
        classification["visionEvidence"] = {
            "layer": 1,
            "name": "YOLO26s fruit identification",
            "fruitClass": selected["fruitClass"],
            "confidencePercent": round(float(selected["confidence"]) * 100.0, 1),
            "frameSequence": detection.get("frameSequence"),
            "snapshotUrl": snapshot_url,
            "demo": False,
        }
        demo_fusion = classification.get("demoFusion")
        if isinstance(demo_fusion, dict):
            image_evidence = demo_fusion.get("image")
            if isinstance(image_evidence, dict):
                image_evidence["snapshotUrl"] = snapshot_url
        self.last_classification = classification
        self.database.update_cycle(self.cycle_id, classification=classification, final_condition=classification["condition"], route=classification["route"])
        await self._publish("classification", classification)

        if classification["route"] == "SAFE":
            await self._transition(SystemState.SORTING_SAFE)
            # Automatic routing is intentionally a simple drop/hold/home movement.
            # Oscillating SORT_* sequences remain available only in Maintenance.
            await self.hardware.command(Command.SAFE_FLAP_TEST, config["servos"]["safeFlap"], session_id=self.session_id, cycle_id=self.cycle_id)
            self._summary["fresh"] += 1
        else:
            await self._transition(SystemState.SORTING_UNSAFE)
            await self.hardware.command(Command.UNSAFE_FLAP_TEST, config["servos"]["unsafeFlap"], session_id=self.session_id, cycle_id=self.cycle_id)
            self._summary["unsafe"] += 1
            if classification["quality"] == "REVIEW_REQUIRED":
                self._summary["inconclusive"] += 1

        await self._transition(SystemState.PURGING)
        await self.hardware.command(Command.PURGE_TIMED, {"durationSeconds": config["purge"]["durationSeconds"], "maximumSeconds": config["purge"]["maximumSeconds"]}, session_id=self.session_id, cycle_id=self.cycle_id, completion_timeout=float(config["purge"]["maximumSeconds"]) + 5)
        await self._transition(SystemState.CYCLE_COMPLETE)
        self.database.update_cycle(self.cycle_id, status="COMPLETED", completed_at=dt.datetime.now(dt.timezone.utc))
        await self._publish("cycle_complete", {"cycleId": self.cycle_id, "classification": classification, "summary": self._summary})
        return True

    async def _checkpoint(self) -> None:
        await self._pause_gate.wait()
        if self.state == SystemState.E_STOPPED:
            raise asyncio.CancelledError

    async def pause(self, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if self.state not in ACTIVE_STATES:
                raise ApiError("INVALID_STATE", "Pause is not valid in the current state")
            self._state_before_pause = self.state
            self._pause_gate.clear()
            await self._transition(SystemState.PAUSED)
            return self.snapshot()

    async def resume(self, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if self.state != SystemState.PAUSED:
                raise ApiError("INVALID_STATE", "Resume requires PAUSED")
            await self._transition(self._state_before_pause, owner=ControlOwner.AUTOMATION)
            self._pause_gate.set()
            return self.snapshot()

    async def request_stop_after_current(self, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if not self.session_id:
                raise ApiError("NO_SESSION", "There is no active session")
            self.stop_after_current = True
            await self._publish("stop_after_current", {"sessionId": self.session_id})
            if self.state == SystemState.ATTENTION_REQUIRED:
                await self._finish_session("STOPPED")
            return self.snapshot()

    async def retry_feed(self, operator: str, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if self.state != SystemState.ATTENTION_REQUIRED or not self.session_id:
                raise ApiError("INVALID_STATE", "Retry feed requires ATTENTION_REQUIRED")
            self.operator = operator
            self.owner = ControlOwner.AUTOMATION
            self._cycle_task = asyncio.create_task(self._automatic_loop(), name="afds-retry-cycle")
            return self.snapshot()

    async def enter_manual(self, operator: str, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if self.state not in {SystemState.READY, SystemState.ATTENTION_REQUIRED, SystemState.PAUSED}:
                raise ApiError("INVALID_STATE", "Manual ownership is blocked while automation is moving")
            if self._cycle_task and not self._cycle_task.done():
                self._cycle_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._cycle_task
            self.operator = operator
            await self._transition(SystemState.MANUAL, owner=ControlOwner.MANUAL)
            return self.snapshot()

    async def enter_maintenance(self, operator: str, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if self.session_id or self.state not in {SystemState.READY, SystemState.DISCONNECTED, SystemState.ERROR}:
                raise ApiError("INVALID_STATE", "Maintenance requires no active inspection session")
            self.operator = operator
            await self._transition(SystemState.MAINTENANCE, owner=ControlOwner.MAINTENANCE)
            return self.snapshot()

    async def exit_control_mode(self, expected: int) -> dict[str, Any]:
        async with self._lock:
            self.check_version(expected)
            if self.state not in {SystemState.MANUAL, SystemState.MAINTENANCE}:
                raise ApiError("INVALID_STATE", "No manual or maintenance ownership is active")
            if self.hardware.connected:
                await self.hardware.safe_state()
                next_state = SystemState.ATTENTION_REQUIRED if self.session_id else SystemState.READY
                detail = {"reason": "MANUAL_INTERVENTION_COMPLETE", "message": "Inspect the feed path, then retry or stop the session."} if self.session_id else None
                await self._transition(next_state, owner=ControlOwner.NONE, detail=detail)
            else:
                await self._transition(SystemState.DISCONNECTED, owner=ControlOwner.NONE)
            return self.snapshot()

    async def manual_command(self, operator: str, expected: int, command: str, parameters: dict[str, Any]) -> dict[str, Any]:
        self.check_version(expected)
        if self.state not in {SystemState.MANUAL, SystemState.MAINTENANCE}:
            raise ApiError("CONTROL_NOT_OWNED", "Enter Manual or Maintenance before sending hardware commands")
        command = command.upper()
        outputs = self.hardware.snapshot()["outputs"]
        motion_commands = {"VALVE_OPEN", "VALVE_CLOSE", "FEED_ONE", "STEPPER_MOVE", "SAFE_FLAP_TEST", "UNSAFE_FLAP_TEST", "SORT_SAFE", "SORT_UNSAFE"}
        if command in motion_commands and outputs.get("pump") == "ON":
            raise ApiError("INTERLOCK", "Motion is blocked while the pump is on")
        if command == "STEPPER_HOME" and int(self.config_service.pins.get("homeLimit", -1)) < 0:
            raise ApiError("INTERLOCK", "Automatic homing is blocked because no home-limit pin is configured")
        if command == "CAMERA_DETECT":
            result = await self.vision.capture()
        else:
            result = await self.hardware.manual(command, parameters, operator)
        self.database.audit("manual_command", {"command": command, "parameters": parameters, "result": result}, actor=operator, session_id=self.session_id, cycle_id=self.cycle_id)
        await self._publish("manual_result", {"command": command, "result": result})
        return {"state": self.snapshot(), "result": result}

    async def capture_maintenance_sensors(self, operator: str, expected: int, duration_seconds: float, target_rate_hz: float) -> dict[str, Any]:
        self.check_version(expected)
        if self.state != SystemState.MAINTENANCE:
            raise ApiError("CONTROL_NOT_OWNED", "Enter Maintenance before capturing sensor data")
        if not self.hardware.connected:
            raise ApiError("HARDWARE_DISCONNECTED", "Initialize and connect the ESP32 before capturing sensor data", 503)
        if self._maintenance_capture_lock.locked():
            raise ApiError("CAPTURE_IN_PROGRESS", "Another Maintenance sensor capture is already running")

        capture_id = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6].upper()}"
        started_at = dt.datetime.now(dt.timezone.utc)
        async with self._maintenance_capture_lock:
            try:
                samples = await self.hardware.collect_sensors(
                    duration_seconds,
                    target_rate_hz,
                    "MAINTENANCE",
                    capture_id,
                )
            except HardwareError as exc:
                raise ApiError("SENSOR_CAPTURE_FAILED", str(exc), 503) from exc

        for sample in samples:
            elapsed = float(sample.get("elapsed", 0.0))
            sample["capturedAtUtc"] = (started_at + dt.timedelta(seconds=elapsed)).isoformat()
        completed_at = dt.datetime.now(dt.timezone.utc)
        result = {
            "captureId": capture_id,
            "startedAtUtc": started_at.isoformat(),
            "completedAtUtc": completed_at.isoformat(),
            "requestedDurationSeconds": duration_seconds,
            "targetRateHz": target_rate_hz,
            "sampleCount": len(samples),
            "samples": samples,
        }
        self.database.audit(
            "maintenance_sensor_capture",
            {key: value for key, value in result.items() if key != "samples"},
            actor=operator,
        )
        await self._publish("maintenance_sensor_capture_complete", {
            "captureId": capture_id,
            "sampleCount": len(samples),
            "durationSeconds": duration_seconds,
        })
        return result

    async def software_estop(self, operator: str) -> dict[str, Any]:
        if self._cycle_task and not self._cycle_task.done():
            self._cycle_task.cancel()
        self.operator = operator
        self.owner = ControlOwner.EMERGENCY
        with contextlib.suppress(Exception):
            await self.hardware.safe_state()
        if self.session_id:
            self.database.finish_session(self.session_id, "E_STOPPED", self._summary)
        self.session_id = None
        self.cycle_id = None
        await self._transition(SystemState.E_STOPPED, owner=ControlOwner.EMERGENCY)
        return self.snapshot()

    async def _finish_session(self, status: str) -> None:
        if self.session_id:
            self.database.finish_session(self.session_id, status, self._summary)
        completed = self.session_id
        self.session_id = None
        self.cycle_id = None
        self.stop_after_current = False
        await self._publish("session_completed", {"sessionId": completed, "status": status, "summary": self._summary})
        await self._transition(SystemState.READY if self.hardware.connected else SystemState.DISCONNECTED, owner=ControlOwner.NONE)

    def get_configuration(self) -> dict[str, Any]:
        return {"active": self.config_service.active, "thresholds": self.config_service.thresholds, "pins": self.config_service.pins}

    async def save_configuration(self, operator: str, expected: int, description: str, values: dict[str, Any]) -> dict[str, Any]:
        self.check_version(expected)
        if self.state in ACTIVE_STATES or self.session_id:
            raise ApiError("CONFIG_LOCKED", "Configuration cannot change during an active session")
        try:
            active = self.config_service.save(values)
        except ConfigurationError as exc:
            raise ApiError("INVALID_CONFIGURATION", str(exc), 422) from exc
        version = str(active.get("configurationVersion") or f"config-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}")
        self.database.save_configuration(version, operator, description, checksum(active), active)
        self.hardware.config = active
        if self.hardware.connected:
            await self.hardware.start_telemetry(float(active["sampling"]["targetRateHz"]), force=True)
        await self.vision.close()
        self.vision = Yolo26VisionService(active)
        await self._publish("configuration_changed", {"version": version, "operator": operator, "description": description})
        return self.get_configuration()

    async def reset_configuration(self, operator: str, expected: int, source: str) -> dict[str, Any]:
        self.check_version(expected)
        if self.state in ACTIVE_STATES or self.session_id:
            raise ApiError("CONFIG_LOCKED", "Configuration cannot reset during an active session")
        try:
            active = self.config_service.reset(source)
        except ConfigurationError as exc:
            raise ApiError("INVALID_CONFIGURATION", str(exc), 422) from exc
        version = f"reset-{source}-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        active["configurationVersion"] = version
        active = self.config_service.save(active)
        self.database.save_configuration(version, operator, f"Reset from {source}", checksum(active), active)
        self.hardware.config = active
        if self.hardware.connected:
            await self.hardware.start_telemetry(float(active["sampling"]["targetRateHz"]), force=True)
        await self.vision.close()
        self.vision = Yolo26VisionService(active)
        await self._publish("configuration_reset", {"version": version, "source": source, "operator": operator})
        return self.get_configuration()
