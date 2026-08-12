from __future__ import annotations

import datetime as dt
import json
import uuid
from enum import Enum
from typing import Any


PROTOCOL_VERSION = "1.0"
MAX_FRAME_BYTES = 8192


class Command(str, Enum):
    GET_STATUS = "GET_STATUS"
    INITIALIZE = "INITIALIZE"
    SET_SAFE_STATE = "SET_SAFE_STATE"
    VALVE_OPEN = "VALVE_OPEN"
    VALVE_CLOSE = "VALVE_CLOSE"
    FEED_ONE = "FEED_ONE"
    STEPPER_MOVE = "STEPPER_MOVE"
    STEPPER_STOP = "STEPPER_STOP"
    STEPPER_DISABLE = "STEPPER_DISABLE"
    SAFE_FLAP_TEST = "SAFE_FLAP_TEST"
    SAFE_FLAP_HOME = "SAFE_FLAP_HOME"
    UNSAFE_FLAP_TEST = "UNSAFE_FLAP_TEST"
    UNSAFE_FLAP_HOME = "UNSAFE_FLAP_HOME"
    SORT_SAFE = "SORT_SAFE"
    SORT_UNSAFE = "SORT_UNSAFE"
    PUMP_ON = "PUMP_ON"
    PUMP_OFF = "PUMP_OFF"
    PURGE_TIMED = "PURGE_TIMED"
    SENSOR_SNAPSHOT = "SENSOR_SNAPSHOT"
    SENSOR_STREAM_START = "SENSOR_STREAM_START"
    SENSOR_STREAM_STOP = "SENSOR_STREAM_STOP"


def new_id(prefix: str = "CMD") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def command_envelope(command: str, payload: dict[str, Any] | None = None, *, session_id: str | None = None, cycle_id: str | None = None, message_id: str | None = None) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "type": "command",
        "messageId": message_id or new_id(),
        "sessionId": session_id,
        "cycleId": cycle_id,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "command": command,
        "payload": payload or {},
    }


def encode(message: dict[str, Any]) -> bytes:
    data = json.dumps(message, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    if len(data) > MAX_FRAME_BYTES:
        raise ValueError("Protocol frame is too large")
    return data


def decode(data: bytes | str) -> dict[str, Any]:
    raw = data.decode("utf-8") if isinstance(data, bytes) else data
    if len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
        raise ValueError("Protocol frame is too large")
    value = json.loads(raw)
    if not isinstance(value, dict) or "type" not in value or "protocolVersion" not in value:
        raise ValueError("Invalid protocol envelope")
    return value

