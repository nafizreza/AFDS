from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class ConfigurationError(ValueError):
    pass


SORTING_MOTION_DEFAULTS = {"offsetDegrees": 10, "intervalMs": 90, "cycles": 4}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot read configuration {path}: {exc}") from exc


def checksum(values: dict[str, Any]) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def normalize_config(values: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(values)
    sorting_motion = normalized.setdefault("servos", {}).setdefault("sortingMotion", {})
    for key, value in SORTING_MOTION_DEFAULTS.items():
        sorting_motion.setdefault(key, value)
    return normalized


def validate_config(values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        vision = values["vision"]
        feeder = values["feeder"]
        servos = values["servos"]
        sampling = values["sampling"]
        purge = values["purge"]
        protocol = values["protocol"]
    except KeyError as exc:
        return [f"Missing required configuration group: {exc.args[0]}"]

    def within(name: str, value: Any, low: float, high: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not low <= value <= high:
            errors.append(f"{name} must be between {low} and {high}")

    within("vision.confidenceThreshold", vision.get("confidenceThreshold"), 0.05, 0.99)
    within("vision.stableFrames", vision.get("stableFrames"), 1, 60)
    within("vision.presenceTimeoutSeconds", vision.get("presenceTimeoutSeconds"), 2, 300)
    within("feeder.stepsForward", feeder.get("stepsForward"), 1, 50000)
    within("feeder.stepsReverse", feeder.get("stepsReverse"), 1, 50000)
    within("feeder.stepRate", feeder.get("stepRate"), 10, 5000)
    within("sampling.durationSeconds", sampling.get("durationSeconds"), 5, 900)
    within("sampling.targetRateHz", sampling.get("targetRateHz"), 0.2, 20)
    within("purge.durationSeconds", purge.get("durationSeconds"), 5, 600)
    within("purge.maximumSeconds", purge.get("maximumSeconds"), 10, 900)
    within("protocol.baudRate", protocol.get("baudRate"), 1200, 2_000_000)
    if purge.get("maximumSeconds", 0) < purge.get("durationSeconds", 0):
        errors.append("purge.maximumSeconds must be >= purge.durationSeconds")

    for name in ("inletValve", "safeFlap", "unsafeFlap"):
        group = servos.get(name, {})
        for key in ("openAngle", "closedAngle", "homeAngle", "dropAngle"):
            if key in group:
                within(f"servos.{name}.{key}", group[key], 0, 180)
    sorting_motion = servos.get("sortingMotion", SORTING_MOTION_DEFAULTS)
    within("servos.sortingMotion.offsetDegrees", sorting_motion.get("offsetDegrees"), 1, 45)
    within("servos.sortingMotion.intervalMs", sorting_motion.get("intervalMs"), 20, 1000)
    within("servos.sortingMotion.cycles", sorting_motion.get("cycles"), 1, 10)
    return errors


class ConfigurationService:
    def __init__(self, config_dir: Path | None = None):
        configured = os.getenv("AFDS_CONFIG_DIR")
        self.config_dir = Path(configured) if configured else (config_dir or PROJECT_ROOT / "config")
        if not self.config_dir.is_absolute():
            self.config_dir = PROJECT_ROOT / self.config_dir
        self.active_path = self.config_dir / "active_config.json"
        self.reset_path = self.config_dir / "reset_values.json"
        self.factory_path = self.config_dir / "factory_defaults.json"
        self.thresholds_path = self.config_dir / "thresholds.json"
        self.pins_path = self.config_dir / "hardware_pins.json"
        source = self.active_path if self.active_path.exists() else self.reset_path
        self._active = normalize_config(_read_json(source))
        errors = validate_config(self._active)
        if errors:
            raise ConfigurationError("; ".join(errors))

    @property
    def active(self) -> dict[str, Any]:
        return deepcopy(self._active)

    @property
    def thresholds(self) -> dict[str, Any]:
        return _read_json(self.thresholds_path)

    @property
    def pins(self) -> dict[str, Any]:
        return _read_json(self.pins_path)

    def save(self, values: dict[str, Any]) -> dict[str, Any]:
        values = normalize_config(values)
        errors = validate_config(values)
        if errors:
            raise ConfigurationError("; ".join(errors))
        values = deepcopy(values)
        temporary = self.active_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.active_path)
        self._active = values
        return self.active

    def reset(self, source: str) -> dict[str, Any]:
        path = self.factory_path if source == "factory" else self.reset_path
        return self.save(_read_json(path))

    def set_reset_baseline(self, values: dict[str, Any]) -> None:
        values = normalize_config(values)
        errors = validate_config(values)
        if errors:
            raise ConfigurationError("; ".join(errors))
        temporary = self.reset_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.reset_path)
