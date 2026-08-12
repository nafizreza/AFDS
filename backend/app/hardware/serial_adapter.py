from __future__ import annotations

import asyncio
import contextlib
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .protocol import Command, command_envelope, decode, encode


class HardwareError(RuntimeError):
    pass


COMPLETION_EVENTS: dict[str, set[str]] = {
    Command.INITIALIZE.value: {"INITIALIZED"},
    Command.SET_SAFE_STATE.value: {"SAFE_STATE_APPLIED"},
    Command.VALVE_OPEN.value: {"VALVE_OPEN_COMPLETED"},
    Command.VALVE_CLOSE.value: {"VALVE_CLOSE_COMPLETED"},
    Command.FEED_ONE.value: {"FEED_COMPLETED"},
    Command.STEPPER_MOVE.value: {"STEPPER_MOVE_COMPLETED", "STEPPER_STOPPED"},
    Command.STEPPER_STOP.value: {"STEPPER_STOPPED"},
    Command.STEPPER_DISABLE.value: {"STEPPER_DISABLED"},
    Command.SAFE_FLAP_TEST.value: {"SAFE_FLAP_COMPLETED"},
    Command.SAFE_FLAP_HOME.value: {"SAFE_FLAP_HOME_COMPLETED"},
    Command.UNSAFE_FLAP_TEST.value: {"UNSAFE_FLAP_COMPLETED"},
    Command.UNSAFE_FLAP_HOME.value: {"UNSAFE_FLAP_HOME_COMPLETED"},
    Command.SORT_SAFE.value: {"SORT_SAFE_COMPLETED"},
    Command.SORT_UNSAFE.value: {"SORT_UNSAFE_COMPLETED"},
    Command.PUMP_ON.value: {"PUMP_STATUS"},
    Command.PUMP_OFF.value: {"PUMP_STATUS"},
    Command.PURGE_TIMED.value: {"PURGE_COMPLETED"},
    Command.SENSOR_SNAPSHOT.value: {"SENSOR_SNAPSHOT_COMPLETED"},
    Command.SENSOR_STREAM_START.value: {"SENSOR_STREAM_STARTED"},
    Command.SENSOR_STREAM_STOP.value: {"SENSOR_STREAM_STOPPED"},
}


class SerialHardware:
    def __init__(self, config: dict[str, Any], event_callback: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None):
        self.config = config
        self.event_callback = event_callback
        self.port = os.getenv("AFDS_SERIAL_PORT", "COM7")
        self._serial: Any = None
        self._reader_task: asyncio.Task | None = None
        self._pending_ack: dict[str, asyncio.Future] = {}
        self._pending_completion: dict[str, tuple[set[str], asyncio.Future]] = {}
        self._sensor_queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
        self._write_lock = asyncio.Lock()
        self._connected = False
        self._last_heartbeat = 0.0
        self._latest_sample: dict[str, Any] | None = None
        self._outputs = {"pump": "OFF", "stepper": "DISABLED", "inletValve": "UNKNOWN", "safeFlap": "UNKNOWN", "unsafeFlap": "UNKNOWN"}

    @property
    def connected(self) -> bool:
        timeout = float(self.config["protocol"].get("heartbeatTimeoutSeconds", 4))
        return self._connected and (not self._last_heartbeat or time.monotonic() - self._last_heartbeat <= timeout)

    def snapshot(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "port": self.port,
            "lastHeartbeatAgeSeconds": round(time.monotonic() - self._last_heartbeat, 2) if self._last_heartbeat else None,
            "latestSensorSample": self._latest_sample,
            "outputs": dict(self._outputs),
        }

    async def connect(self) -> None:
        if self._connected:
            return
        try:
            import serial
            protocol = self.config["protocol"]
            self._serial = await asyncio.to_thread(
                serial.Serial,
                self.port,
                int(protocol["baudRate"]),
                timeout=0.2,
                write_timeout=1.0,
            )
        except Exception as exc:
            raise HardwareError(f"Cannot open ESP32 serial port {self.port}: {exc}") from exc
        self._connected = True
        self._last_heartbeat = time.monotonic()
        self._reader_task = asyncio.create_task(self._reader_loop(), name="afds-serial-reader")

    async def disconnect(self) -> None:
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        if self._serial:
            await asyncio.to_thread(self._serial.close)
        self._serial = None

    async def _reader_loop(self) -> None:
        while self._connected and self._serial:
            try:
                raw: bytes = await asyncio.to_thread(self._serial.readline)
                if not raw:
                    await asyncio.sleep(0.02)
                    continue
                message = decode(raw)
                await self._handle(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._emit("hardware_error", {"message": str(exc)})
                await asyncio.sleep(0.1)

    async def _handle(self, message: dict[str, Any]) -> None:
        message_type = str(message.get("type", ""))
        message_id = str(message.get("messageId") or message.get("commandId") or "")
        if message_type == "heartbeat":
            self._last_heartbeat = time.monotonic()
        elif message_type == "acknowledgement":
            future = self._pending_ack.get(message_id)
            if future and not future.done():
                future.set_result(message)
        elif message_type == "sensor_data":
            sample = dict(message.get("payload") or {})
            self._latest_sample = sample
            if self._sensor_queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._sensor_queue.get_nowait()
            self._sensor_queue.put_nowait(sample)
            await self._emit("sensor_sample", sample)
        elif message_type in {"event", "error"}:
            event_name = str(message.get("event") or message.get("code") or "UNKNOWN")
            pending = self._pending_completion.get(message_id)
            if pending and not pending[1].done():
                if message_type == "error":
                    pending[1].set_exception(HardwareError(str(message.get("message") or event_name)))
                elif event_name in pending[0]:
                    pending[1].set_result(message)
        await self._emit("hardware_message", message)

    async def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self.event_callback:
            await self.event_callback(topic, payload)

    async def command(self, name: str | Command, payload: dict[str, Any] | None = None, *, session_id: str | None = None, cycle_id: str | None = None, completion_timeout: float | None = None) -> dict[str, Any]:
        if not self.connected or not self._serial:
            raise HardwareError("ESP32 is disconnected")
        command_name = name.value if isinstance(name, Command) else str(name).upper()
        envelope = command_envelope(command_name, payload, session_id=session_id, cycle_id=cycle_id)
        message_id = envelope["messageId"]
        loop = asyncio.get_running_loop()
        ack = loop.create_future()
        completion = loop.create_future()
        self._pending_ack[message_id] = ack
        expected = COMPLETION_EVENTS.get(command_name, {f"{command_name}_COMPLETED"})
        self._pending_completion[message_id] = (expected, completion)
        try:
            async with self._write_lock:
                await asyncio.to_thread(self._serial.write, encode(envelope))
                await asyncio.to_thread(self._serial.flush)
            ack_timeout = float(self.config["protocol"].get("ackTimeoutSeconds", 2))
            acknowledgement = await asyncio.wait_for(ack, ack_timeout)
            if not acknowledgement.get("accepted", True):
                raise HardwareError(str(acknowledgement.get("reason", "Command rejected")))
            timeout = completion_timeout or float(self.config["protocol"].get("completionTimeoutSeconds", 20))
            result = await asyncio.wait_for(completion, timeout)
            if command_name == Command.PUMP_ON.value:
                self._outputs["pump"] = "ON"
            elif command_name in {Command.PUMP_OFF.value, Command.PURGE_TIMED.value, Command.SET_SAFE_STATE.value}:
                self._outputs["pump"] = "OFF"
            elif command_name == Command.VALVE_OPEN.value:
                self._outputs["inletValve"] = "OPEN"
            elif command_name == Command.VALVE_CLOSE.value:
                self._outputs["inletValve"] = "CLOSED"
            elif command_name in {Command.STEPPER_STOP.value, Command.STEPPER_DISABLE.value, Command.FEED_ONE.value, Command.STEPPER_MOVE.value}:
                self._outputs["stepper"] = "DISABLED"
            elif command_name in {Command.SAFE_FLAP_HOME.value, Command.SORT_SAFE.value, Command.SAFE_FLAP_TEST.value}:
                self._outputs["safeFlap"] = "HOME"
            elif command_name in {Command.UNSAFE_FLAP_HOME.value, Command.SORT_UNSAFE.value, Command.UNSAFE_FLAP_TEST.value}:
                self._outputs["unsafeFlap"] = "HOME"
            return {"messageId": message_id, "acknowledgement": acknowledgement, "completion": result}
        except asyncio.TimeoutError as exc:
            raise HardwareError(f"{command_name} timed out") from exc
        finally:
            self._pending_ack.pop(message_id, None)
            self._pending_completion.pop(message_id, None)

    async def safe_state(self) -> None:
        await self.command(Command.SET_SAFE_STATE, {"closeValve": True, "homeFlaps": True})
        self._outputs.update({"pump": "OFF", "stepper": "DISABLED", "inletValve": "CLOSED", "safeFlap": "HOME", "unsafeFlap": "HOME"})

    async def collect_sensors(self, duration: float, rate_hz: float, session_id: str, cycle_id: str) -> list[dict[str, Any]]:
        while not self._sensor_queue.empty():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._sensor_queue.get_nowait()
        interval_ms = max(50, int(1000 / max(rate_hz, 0.1)))
        await self.command(Command.SENSOR_STREAM_START, {"intervalMs": interval_ms}, session_id=session_id, cycle_id=cycle_id)
        started = time.monotonic()
        samples: list[dict[str, Any]] = []
        try:
            while time.monotonic() - started < duration:
                remaining = duration - (time.monotonic() - started)
                try:
                    sample = await asyncio.wait_for(self._sensor_queue.get(), timeout=min(2.5, max(0.1, remaining)))
                    sample["elapsed"] = round(time.monotonic() - started, 3)
                    samples.append(sample)
                except asyncio.TimeoutError:
                    continue
        finally:
            with contextlib.suppress(Exception):
                await self.command(Command.SENSOR_STREAM_STOP, session_id=session_id, cycle_id=cycle_id)
        return samples

    async def manual(self, command: str, parameters: dict[str, Any], operator: str) -> dict[str, Any]:
        allowed = {item.value for item in Command} - {Command.INITIALIZE.value}
        normalized = command.upper()
        if normalized not in allowed:
            raise HardwareError(f"Unsupported manual command: {command}")
        return await self.command(normalized, {**parameters, "operator": operator})
