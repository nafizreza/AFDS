from __future__ import annotations

import asyncio
import hashlib
import time
from pathlib import Path
from threading import Lock
from typing import Any

from ..core.config import PROJECT_ROOT


class VisionError(RuntimeError):
    pass


class Yolo26VisionService:
    def __init__(self, config: dict[str, Any]):
        self.config = config["vision"]
        model_path = Path(self.config["modelPath"])
        self.model_path = model_path if model_path.is_absolute() else PROJECT_ROOT / model_path
        self._camera: Any = None
        self._model: Any = None
        self._lock = Lock()
        self._ready = False
        self._last_error: str | None = None
        self._latest_jpeg: bytes | None = None
        self._inspection_jpeg: bytes | None = None
        self._inspection_frame_sequence: int | None = None
        self._raw_frames: dict[int, bytes] = {}
        self._latest_result: dict[str, Any] | None = None
        self._frame_sequence = 0
        self.model_checksum: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "ready": self._ready,
            "cameraReady": self._camera is not None,
            "modelReady": self._model is not None,
            "modelPath": str(self.model_path),
            "modelChecksum": self.model_checksum,
            "lastError": self._last_error,
            "frameSequence": self._frame_sequence,
            "inspectionFrameSequence": self._inspection_frame_sequence,
            "inspectionSnapshotUrl": (
                f"/api/v1/camera/inspection.jpg?frame={self._inspection_frame_sequence}"
                if self._inspection_frame_sequence is not None else None
            ),
            "latestDetection": self._latest_result,
        }

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        try:
            import cv2
            from ultralytics import YOLO
            if not self.model_path.exists():
                raise VisionError(f"YOLO26 model not found: {self.model_path}")
            model_digest = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
            camera = cv2.VideoCapture(int(self.config.get("cameraId", 0)))
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.config.get("width", 1280)))
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.config.get("height", 720)))
            camera.set(cv2.CAP_PROP_FPS, int(self.config.get("fps", 30)))
            ok, _ = camera.read()
            if not ok:
                camera.release()
                raise VisionError("Camera opened but did not deliver a frame")
            model = YOLO(str(self.model_path))
            self._camera = camera
            self._model = model
            self.model_checksum = model_digest
            self._ready = True
            self._last_error = None
        except Exception as exc:
            self._ready = False
            self._last_error = str(exc)
            raise VisionError(str(exc)) from exc

    async def close(self) -> None:
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            if self._camera:
                self._camera.release()
            self._camera = None
            self._model = None
            self._ready = False
            self._latest_jpeg = None
            self._inspection_jpeg = None
            self._inspection_frame_sequence = None
            self._raw_frames.clear()

    @staticmethod
    def _fruit_name(raw: str) -> str | None:
        value = raw.strip().upper().replace("-", "_").replace(" ", "_")
        for fruit in ("APPLE", "MANGO", "ORANGE"):
            if value == fruit or value.startswith(f"{fruit}_") or value.endswith(f"_{fruit}"):
                return fruit
        return None

    async def capture(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._capture_sync)

    def _capture_sync(self) -> dict[str, Any]:
        if not self._ready or self._camera is None or self._model is None:
            raise VisionError(self._last_error or "Camera/YOLO service is not ready")
        import cv2
        with self._lock:
            ok, frame = self._camera.read()
            if not ok:
                raise VisionError("Camera frame read failed")
            started = time.perf_counter()
            predictions = self._model.predict(
                source=frame,
                conf=float(self.config.get("confidenceThreshold", 0.35)),
                verbose=False,
            )
            result = predictions[0]
            height, width = frame.shape[:2]
            detections: list[dict[str, Any]] = []
            if result.boxes is not None:
                for class_id, confidence, box in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist(), result.boxes.xyxy.tolist()):
                    raw_name = str(self._model.names[int(class_id)])
                    fruit = self._fruit_name(raw_name)
                    if not fruit:
                        continue
                    x1, y1, x2, y2 = [float(item) for item in box]
                    area_fraction = max(0.0, (x2 - x1) * (y2 - y1) / max(1, width * height))
                    if area_fraction < float(self.config.get("minimumBoxAreaFraction", 0.025)):
                        continue
                    detections.append({
                        "fruitClass": fruit,
                        "rawClass": raw_name,
                        "confidence": round(float(confidence), 4),
                        "boundingBox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                        "frame": {"width": width, "height": height},
                    })
            self._frame_sequence += 1
            frame_sequence = self._frame_sequence
            raw_ok, raw_encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if raw_ok:
                self._raw_frames[frame_sequence] = raw_encoded.tobytes()
                for stale_sequence in sorted(self._raw_frames)[:-12]:
                    self._raw_frames.pop(stale_sequence, None)
            annotated = result.plot()
            ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                self._latest_jpeg = encoded.tobytes()
            payload = {
                "frameSequence": frame_sequence,
                "detections": detections,
                "count": len(detections),
                "latencyMs": round((time.perf_counter() - started) * 1000, 1),
                "modelChecksum": self.model_checksum,
                "timestamp": time.time(),
            }
            self._latest_result = payload
            return payload

    async def wait_for_stable_fruit(self, timeout: float) -> dict[str, Any] | None:
        required = int(self.config.get("stableFrames", 5))
        stable = 0
        selected: dict[str, Any] | None = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = await self.capture()
            if result["count"] == 1:
                current = result["detections"][0]
                if selected and current["fruitClass"] == selected["fruitClass"]:
                    stable += 1
                else:
                    selected = current
                    stable = 1
                if stable >= required:
                    frame_sequence = int(result["frameSequence"])
                    with self._lock:
                        snapshot = self._raw_frames.get(frame_sequence)
                        if snapshot:
                            self._inspection_jpeg = snapshot
                            self._inspection_frame_sequence = frame_sequence
                    return {
                        **result,
                        "selected": current,
                        "stableFrames": stable,
                        "snapshotUrl": f"/api/v1/camera/inspection.jpg?frame={frame_sequence}",
                    }
            else:
                stable = 0
                selected = None
            await asyncio.sleep(0.08)
        return None

    def inspection_jpeg(self) -> bytes | None:
        with self._lock:
            return self._inspection_jpeg

    async def mjpeg(self):
        interval = 1 / max(1, int(self.config.get("streamFps", 12)))
        while True:
            try:
                await self.capture()
                if self._latest_jpeg:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + self._latest_jpeg + b"\r\n"
            except Exception:
                await asyncio.sleep(0.5)
            await asyncio.sleep(interval)
