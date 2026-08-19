import asyncio
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
    config["servos"]["sortingMotion"].update({"offsetDegrees": 12, "intervalMs": 105, "cycles": 6, "returnHomeDelayMs": 725})
    return SerialHardware(config)


def test_active_valve_angles_are_translated_to_firmware_payload():
    hardware = adapter()
    assert hardware._payload_with_active_defaults(Command.VALVE_OPEN.value, {})["angle"] == 17
    assert hardware._payload_with_active_defaults(Command.VALVE_CLOSE.value, {})["angle"] == 103


def test_active_flap_and_safe_state_angles_are_translated():
    hardware = adapter()
    safe_sort = hardware._payload_with_active_defaults(Command.SORT_SAFE.value, {})
    unsafe_sort = hardware._payload_with_active_defaults(Command.SORT_UNSAFE.value, {})
    assert safe_sort["angle"] == 9
    assert safe_sort["homeAngle"] == 61
    assert safe_sort["oppositeHomeAngle"] == 62
    assert unsafe_sort["angle"] == 11
    assert unsafe_sort["homeAngle"] == 62
    assert unsafe_sort["oppositeHomeAngle"] == 61
    assert safe_sort["shakeOffsetDegrees"] == unsafe_sort["shakeOffsetDegrees"] == 12
    assert safe_sort["shakeCycles"] == unsafe_sort["shakeCycles"] == 6
    assert safe_sort["shakeStepMs"] == unsafe_sort["shakeStepMs"] == 105
    assert safe_sort["returnHomeDelayMs"] == unsafe_sort["returnHomeDelayMs"] == 725
    safe = hardware._payload_with_active_defaults(Command.SET_SAFE_STATE.value, {})
    assert safe["valveClosedAngle"] == 103
    assert safe["safeHomeAngle"] == 61
    assert safe["unsafeHomeAngle"] == 62


def test_simple_flap_commands_move_drop_hold_and_home_without_oscillation():
    hardware = adapter()
    safe = hardware._payload_with_active_defaults(Command.SAFE_FLAP_TEST.value, {})
    unsafe = hardware._payload_with_active_defaults(Command.UNSAFE_FLAP_TEST.value, {})
    assert safe["angle"] == 9
    assert safe["homeAngle"] == 61
    assert unsafe["angle"] == 11
    assert unsafe["homeAngle"] == 62
    for payload in (safe, unsafe):
        assert "shakeCycles" not in payload
        assert "shakeOffsetDegrees" not in payload
        assert "shakeStepMs" not in payload
        assert "returnHomeDelayMs" not in payload


def test_explicit_maintenance_value_overrides_active_config():
    hardware = adapter()
    payload = hardware._payload_with_active_defaults(Command.VALVE_OPEN.value, {"angle": 42})
    assert payload["angle"] == 42
    sort_payload = hardware._payload_with_active_defaults(
        Command.SORT_SAFE.value,
        {"oppositeHomeAngle": 27, "shakeOffsetDegrees": 8, "shakeCycles": 3, "shakeStepMs": 75, "returnHomeDelayMs": 640},
    )
    assert sort_payload["oppositeHomeAngle"] == 27
    assert sort_payload["shakeOffsetDegrees"] == 8
    assert sort_payload["shakeCycles"] == 3
    assert sort_payload["shakeStepMs"] == 75
    assert sort_payload["returnHomeDelayMs"] == 640


def test_purge_uses_active_or_explicit_configuration_values():
    hardware = adapter()
    configured = hardware._payload_with_active_defaults(Command.PURGE_TIMED.value, {})
    assert configured["durationSeconds"] == 30
    assert configured["maximumSeconds"] == 180
    explicit = hardware._payload_with_active_defaults(
        Command.PURGE_TIMED.value,
        {"durationSeconds": 45, "maximumSeconds": 60},
    )
    assert explicit["durationSeconds"] == 45
    assert explicit["maximumSeconds"] == 60


def test_manual_purge_waits_for_configured_maximum_instead_of_protocol_default():
    hardware = adapter()
    captured = {}

    async def fake_command(name, payload=None, **kwargs):
        captured.update({"name": name, "payload": payload, **kwargs})
        return {"ok": True}

    hardware.command = fake_command
    asyncio.run(hardware.manual(Command.PURGE_TIMED.value, {}, "operator"))

    assert captured["name"] == Command.PURGE_TIMED.value
    assert captured["completion_timeout"] == 185
    assert captured["payload"]["operator"] == "operator"
