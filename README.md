# AFDS - Adulterated Fruit Detection System

AFDS is a local, hardware-first fruit inspection and sorting application. It has two operator modes: **Automatic Hardware** and **Manual**. Maintenance is an exclusive lock for calibration and component testing.

This guide is for **Windows Command Prompt (CMD)** and the project at `D:\AFDS`. Run the commands in order. This version uses `backend.app.main:app`; `AFDS_MODE` is not required.

## 1. Install the prerequisites

Install these applications, then reopen CMD so their commands are available:

- **Python 3.10**, including the Windows Python launcher (`py`). The commands below select Python 3.10 explicitly to match the pinned dependencies.
- **Node.js with npm**. The current frontend requires Node.js `20.19+` within version 20, or `22.12+`. A supported LTS release meeting that requirement is recommended.
- **Git**, if downloading the project from GitHub.

PlatformIO will be installed into the Python virtual environment in step 3. pnpm is optional; this guide uses npm.

Check the installed tools:

```cmd
py -3.10 --version
node --version
npm --version
git --version
```

If `py -3.10` is unavailable, install Python 3.10 before continuing.

## 2. Open or download the project

If the project is already at `D:\AFDS`, run:

```cmd
cd /d D:\AFDS
```

For a fresh download, run the following instead. The destination folder must not already contain another copy:

```cmd
cd /d D:\
git clone https://github.com/nafizreza/AFDS.git AFDS
cd AFDS
```

## 3. Create the virtual environment and install Python dependencies

Run from `D:\AFDS`. Skip the first command if this project already has a working `.venv`:

```cmd
py -3.10 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install platformio
python -m pip check
```

The prompt should show `(.venv)`. Keep this environment active for the remaining Python and PlatformIO commands. `uvicorn[standard]` in `requirements.txt` includes the support needed to load `.env`.

## 4. Create and edit the environment file

Create `.env` without overwriting an existing copy:

```cmd
if not exist .env copy .env.example .env
notepad .env
```

Use the following settings, replacing `COM7` with your ESP32's actual port, then save and close Notepad:

```dotenv
AFDS_HOST=127.0.0.1
AFDS_PORT=8000
AFDS_SERIAL_PORT=COM7
AFDS_CONFIG_DIR=config
AFDS_DATA_DIR=data
AFDS_LOG_LEVEL=INFO
```

Connect the ESP32 and list serial ports:

```cmd
python -m serial.tools.list_ports -v
```

You can also find the port under **Device Manager > Ports (COM & LPT)**. Identify the ESP32's USB serial port; a Bluetooth COM port is not the ESP32.

The startup command in step 8 explicitly loads `.env` with `--env-file`. Merely creating `.env` does not load it into the existing PowerShell launcher. Existing environment variables take precedence over `.env`; for example, clear an old CMD port override with `set AFDS_SERIAL_PORT=` before starting.

## 5. Install and build the frontend

From `D:\AFDS`, run:

```cmd
cd frontend
npm ci
npm run build
cd ..
```

This creates `frontend\dist`, which the backend serves at `http://127.0.0.1:8000`. Rebuild after changing frontend source files. No separate frontend server is needed for normal operation.

## 6. Add the YOLO model

Place the trained fruit-detection weights at:

```text
D:\AFDS\models\yolo26\yolo26s.pt
```

The configured model must detect Apple, Mango, and Orange. Model weights are excluded from Git, so a fresh clone needs a separate copy of the correct weights; dependency installation does not supply this trained model.

Check the file:

```cmd
dir models\yolo26\yolo26s.pt
certutil -hashfile models\yolo26\yolo26s.pt SHA256
```

Compare the hash with your approved model copy. The model path and camera ID are configured in `config\active_config.json` when present, otherwise `config\reset_values.json`.

## 7. Build, upload, and commission the ESP32

With the virtual environment active and CMD at `D:\AFDS`, build the firmware:

```cmd
python -m platformio run -d firmware
```

Before uploading, review [docs/COMMISSIONING.md](docs/COMMISSIONING.md), verify wiring and power, and prepare the mechanism for firmware startup. Uploading resets the board and can command actuator positions. Close other programs using the serial port.

Upload using the same ESP32 port you put in `.env`:

```cmd
python -m platformio run -d firmware --target upload --upload-port COM7
```

Replace `COM7` in this command as well; PlatformIO does not read the application's `.env` file automatically.

Complete the commissioning checklist before running an automatic fruit cycle. It covers feeder travel, servo angles, pump behavior, sensor calibration, camera lighting, model validation, and thresholds. The supplied threshold profile is marked uncommissioned. A successful build does not confirm physical calibration.

## 8. Start the application

From CMD:

```cmd
cd /d D:\AFDS
call .venv\Scripts\activate.bat
python -m uvicorn backend.app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`, then open:

**http://127.0.0.1:8000**

Leave CMD open while using the application. Press **Ctrl+C** to stop it. The dashboard can start while the hardware is disconnected; hardware initialization also requires the ESP32, camera, and model to be available.

The explicit `--host` and `--port` options above determine the listening address. To use another port, change `--port` in the command; editing `AFDS_PORT` in `.env` alone does not change this command's port.

For later runs, repeat only this step unless dependencies, firmware, or frontend source have changed.

## Verification

Run from `D:\AFDS` with `.venv` active:

```cmd
python -m pip check
python -m pytest
cd frontend
npm run build
cd ..
python -m platformio run -d firmware
```

Review failures before operating the sorter. The latest local check found 20 passing backend tests and two failing tests: the expected inlet closed angle differs from the configuration, and one classifier test assumes a different formalin threshold. These results do not establish hardware readiness.

## Troubleshooting

- **`No module named 'backend.api'`:** use `backend.app.main:app` and run from `D:\AFDS`.
- **Missing Python package:** activate `.venv` and rerun `python -m pip install -r requirements.txt`.
- **`.env` changes are ignored:** include `--env-file .env`, clear conflicting environment variables, and restart the server.
- **ESP32 connection fails:** check the actual USB COM port, update `.env`, and close serial monitors using the port.
- **Frontend not built:** repeat step 5.
- **Port 8000 is in use:** stop the existing server in its CMD window with Ctrl+C, or start this app with `--port 8001` and open `http://127.0.0.1:8001`.
- **Model missing:** supply the trained weights at the path in step 6.

## Project map

- `backend/app/orchestration/` - automatic state machine and control ownership
- `backend/app/classification/rfalter.py` - threshold-based condition screening
- `backend/app/hardware/` - ESP32 serial protocol adapter
- `backend/app/vision/` - camera, YOLO26, and annotated MJPEG stream
- `frontend/src/pages/` - Overview, Live Monitor, Manual, Maintenance, and History
- `firmware/` - PlatformIO ESP32 firmware
- `config/` - active/reset/factory values, GPIO map, and thresholds
- `data/` - SQLite records, exports, evidence images, and logs
- `docs/` - architecture, commissioning, and operator guidance

## What it controls

- SG90 inlet valve on ESP32 GPIO 32
- NEMA 17 / DRV8825 fruit feeder
- YOLO26 live fruit detection and bounding boxes
- MQ-3, MQ-136, ZE08-CH2O, and DHT22 sensor acquisition
- Fresh and reject MG996R sorting flaps
- Timed vacuum-pump chamber purge

The backend owns workflow state. A browser refresh does not restart a fruit cycle. Commands include the expected state version so stale or duplicated operator actions are rejected.

## Safety

Software E-stop requests pump off, stepper disable, inlet-valve close, and flap home. It is not a physical power-disconnect circuit. Without encoders, limit switches, or flap feedback, actuator positions are reported as **commanded**, not physically confirmed.

Classification uses sensor thresholds. Confidence and threshold-relative indices are not laboratory concentration measurements or calibrated probabilities. YOLO identifies fruit; the displayed demonstration image contribution is not an independently trained adulteration classifier.

Read [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md) and [docs/COMMISSIONING.md](docs/COMMISSIONING.md) before operating the hardware.
