# AFDS - Adulterated Fruit Detection System

AFDS is a local, hardware-first fruit inspection and sorting application. It has two operator modes only: **Automatic Hardware** and **Manual**. Maintenance is an exclusive safety lock used for calibration and component testing; it is not a simulation mode.

## What it controls

- SG90 inlet valve on ESP32 GPIO 32
- NEMA 17 / DRV8825 fruit feeder
- YOLO26 live fruit detection and bounding boxes
- MQ-3, MQ-136, ZE08-CH2O and DHT22 sensor acquisition
- Threshold-based condition classification in `backend/app/classification/rfalter.py`
- Fresh and reject MG996R sorting flaps
- Timed vacuum-pump chamber purge

## Quick start

1. Install Python 3.10+, Node.js 20+ and PlatformIO. pnpm is optional; the scripts automatically fall back to npm.
2. Copy `.env.example` to `.env` and set the ESP32 serial port.
3. Run `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`.
4. Build/flash `firmware/` and complete `docs/COMMISSIONING.md`.
5. Run `powershell -ExecutionPolicy Bypass -File scripts\start.ps1`.
6. Open `http://127.0.0.1:8000`.

For separate hot-reloading frontend/backend servers, run `scripts\start-development.ps1` and open `http://127.0.0.1:5173`.

## Project map

- `backend/app/orchestration/` — authoritative automatic state machine and safety ownership
- `backend/app/classification/rfalter.py` — transparent threshold screening
- `backend/app/hardware/` — ESP32 serial protocol adapter
- `backend/app/vision/` — camera, YOLO26 and annotated MJPEG stream
- `frontend/src/pages/` — Overview, Live Monitor, Manual, Maintenance and History
- `firmware/` — modular PlatformIO ESP32 firmware
- `config/` — active/reset/factory values, GPIO map and thresholds
- `data/` — SQLite records, exports, evidence images and logs
- `docs/` — architecture, commissioning and operator handoff

The included weights are expected at `models/yolo26/yolo26s.pt`. The source file copied during generation has SHA-256 `646F8BC3FE0A656803D95C294F7852321748CB29D13466A1AF8862E2DB384A1B`.

The backend is authoritative. A browser refresh never restarts a fruit cycle. Commands include the expected state version so stale or duplicated operator actions are rejected.

## Safety

Software E-stop requests pump off, stepper disable, inlet-valve close and flap home. It is not a physical power-disconnect circuit. With no encoders, limit switches or flap feedback, the application reports actuator positions as **commanded**, not physically confirmed.

Threshold percentages are normalized indices relative to commissioned limits. They are not laboratory concentration measurements.

See `docs/OPERATOR_GUIDE.md` and `docs/COMMISSIONING.md` before connecting hardware.
