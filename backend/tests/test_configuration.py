import json

from backend.app.core.config import ConfigurationService, validate_config


def test_repository_defaults_are_valid():
    service = ConfigurationService()
    assert service.active["servos"]["inletValve"]["closedAngle"] == 100
    assert service.pins["feederValveServo"] == 32
    assert service.active["vision"]["modelPath"].endswith("yolo26s.pt")


def test_configuration_rejects_purge_over_maximum():
    service = ConfigurationService()
    invalid = json.loads(json.dumps(service.active))
    invalid["purge"]["durationSeconds"] = invalid["purge"]["maximumSeconds"] + 1
    assert "purge.maximumSeconds must be >= purge.durationSeconds" in validate_config(invalid)
