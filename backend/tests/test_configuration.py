import json

from backend.app.core.config import ConfigurationService, validate_config


def test_repository_defaults_are_valid():
    service = ConfigurationService()
    assert service.active["servos"]["inletValve"]["closedAngle"] == 90
    assert service.active["servos"]["sortingMotion"] == {"offsetDegrees": 10, "intervalMs": 90, "cycles": 4}
    assert service.pins["feederValveServo"] == 32
    assert service.active["vision"]["modelPath"].endswith("yolo26s.pt")


def test_configuration_rejects_purge_over_maximum():
    service = ConfigurationService()
    invalid = json.loads(json.dumps(service.active))
    invalid["purge"]["durationSeconds"] = invalid["purge"]["maximumSeconds"] + 1
    assert "purge.maximumSeconds must be >= purge.durationSeconds" in validate_config(invalid)


def test_configuration_rejects_unsafe_sorting_motion_values():
    service = ConfigurationService()
    invalid = json.loads(json.dumps(service.active))
    invalid["servos"]["sortingMotion"].update({"offsetDegrees": 0, "intervalMs": 10, "cycles": 0})
    errors = validate_config(invalid)
    assert "servos.sortingMotion.offsetDegrees must be between 1 and 45" in errors
    assert "servos.sortingMotion.intervalMs must be between 20 and 1000" in errors
    assert "servos.sortingMotion.cycles must be between 1 and 10" in errors
