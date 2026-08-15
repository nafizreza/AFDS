import json
from pathlib import Path

from backend.app.hardware.protocol import Command
from backend.app.hardware.serial_adapter import SerialHardware


ROOT = Path(__file__).resolve().parents[2]


def adapter() -> SerialHardware:
    config = json.loads((ROOT / "config" / "reset_values.json").read_text(encoding="utf-8"))
    config["servos"]["inletValve"].update({"openAngle": 17, "closedAngle": 103})
    config["servos"]["safeFlap"].update({"homeAngle": 61, "dropAngle": 9})
    config["servos"]["unsafeFlap"].update({"homeAngle": 62, "dropAngle": 11})
    return SerialHardware(config)


def test_active_valve_angles_are_translated_to_firmware_payload():
    hardware = adapter()
    assert hardware._payload_with_active_defaults(Command.VALVE_OPEN.value, {})["angle"] == 17
    assert hardware._payload_with_active_defaults(Command.VALVE_CLOSE.value, {})["angle"] == 103


def test_active_flap_and_safe_state_angles_are_translated():
    hardware = adapter()
    assert hardware._payload_with_active_defaults(Command.SORT_SAFE.value, {})["angle"] == 9
    assert hardware._payload_with_active_defaults(Command.SORT_UNSAFE.value, {})["angle"] == 11
    safe = hardware._payload_with_active_defaults(Command.SET_SAFE_STATE.value, {})
    assert safe["valveClosedAngle"] == 103
    assert safe["safeHomeAngle"] == 61
    assert safe["unsafeHomeAngle"] == 62


def test_explicit_maintenance_value_overrides_active_config():
    hardware = adapter()
    payload = hardware._payload_with_active_defaults(Command.VALVE_OPEN.value, {"angle": 42})
    assert payload["angle"] == 42

