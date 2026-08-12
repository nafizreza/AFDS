# Architecture

Dashboard -> FastAPI intents -> authoritative state machine -> hardware/vision/classification services -> ESP32/camera/storage.

The automatic cycle is:

`READY -> OPENING_VALVE -> FEEDING -> CLOSING_VALVE -> WAITING_FOR_FRUIT -> ACQUIRING -> CLASSIFYING -> SORTING -> PURGING -> CYCLE_COMPLETE -> READY`

Recovery states are `ATTENTION_REQUIRED`, `PAUSED`, `ERROR`, `DISCONNECTED` and `E_STOPPED`.

