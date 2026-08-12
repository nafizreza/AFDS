from backend.app.hardware.protocol import Command, command_envelope, decode, encode


def test_protocol_round_trip():
    message = command_envelope(Command.VALVE_OPEN.value, {"angle": 180}, message_id="CMD-TEST")
    result = decode(encode(message))
    assert result["messageId"] == "CMD-TEST"
    assert result["payload"]["angle"] == 180
    assert encode(message).endswith(b"\n")


def test_protocol_rejects_non_envelope():
    try:
        decode('{"hello":"world"}')
    except ValueError as exc:
        assert "Invalid protocol" in str(exc)
    else:
        raise AssertionError("Invalid protocol envelope was accepted")

