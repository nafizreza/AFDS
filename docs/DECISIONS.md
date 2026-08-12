# Engineering decisions

- The backend owns workflow state and interlocks; the dashboard submits intents only.
- ESP32 commands use newline-delimited JSON with acknowledgement and separate completion events.
- YOLO identifies presence/species. Sensor thresholds determine the final condition.
- The no-fruit timeout pauses for inspection rather than blindly feeding again.
- The active configuration is stored as an immutable database version. `config/reset_values.json` is the user-defined reset baseline.
- Every ambiguous or invalid result routes to the unsafe chamber.

