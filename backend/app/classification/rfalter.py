"""Transparent threshold-based fruit condition screening.

The percentage fields are threshold-relative indices. They are not chemical
concentration measurements and must never be presented as laboratory ppm/%.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Any, Iterable

from ..domain.types import FruitCondition, Route


REQUIRED_CHANNELS = ("mq3", "mq136", "ch2o", "temperature", "humidity")


@dataclass(frozen=True)
class ThresholdEvidence:
    channel: str
    raw_mean: float
    baseline: float
    adjusted_mean: float
    threshold: float
    threshold_index_percent: float
    matched: bool


@dataclass(frozen=True)
class ThresholdResult:
    condition: FruitCondition
    route: Route
    fruit_type: str
    valid: bool
    quality: str
    profile_version: str
    commissioned: bool
    evidence: dict[str, ThresholdEvidence]
    reasons: tuple[str, ...]
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["condition"] = self.condition.value
        result["route"] = self.route.value
        return result


class ThresholdClassifier:
    def __init__(self, threshold_config: dict[str, Any]):
        self.config = threshold_config

    @staticmethod
    def _number(value: Any, label: str) -> float:
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} is not numeric")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"{label} is not finite")
        return value

    def classify(
        self,
        fruit_type: str,
        samples: Iterable[dict[str, Any]],
        baseline: dict[str, float] | None = None,
    ) -> ThresholdResult:
        rows = list(samples)
        reasons: list[str] = []
        if not rows:
            return self._invalid(fruit_type, "No sensor samples were received")

        values: dict[str, list[float]] = {name: [] for name in REQUIRED_CHANNELS}
        previous_timestamp: float | None = None
        try:
            for index, sample in enumerate(rows):
                timestamp = self._number(sample.get("elapsed", index), f"sample[{index}].elapsed")
                if previous_timestamp is not None and timestamp < previous_timestamp:
                    raise ValueError("Sensor timestamps are out of order")
                previous_timestamp = timestamp
                for channel in REQUIRED_CHANNELS:
                    values[channel].append(self._number(sample.get(channel), f"sample[{index}].{channel}"))
        except ValueError as exc:
            return self._invalid(fruit_type, str(exc))

        profile = self.config.get("profiles", {}).get(
            fruit_type.upper(), self.config.get("profiles", {}).get("DEFAULT", {})
        )
        if not profile:
            return self._invalid(fruit_type, "No compatible threshold profile")

        environment = profile.get("environment", {})
        temperature = fmean(values["temperature"])
        humidity = fmean(values["humidity"])
        if not environment.get("temperatureMin", -math.inf) <= temperature <= environment.get("temperatureMax", math.inf):
            reasons.append("Temperature is outside the commissioned range")
        if not environment.get("humidityMin", -math.inf) <= humidity <= environment.get("humidityMax", math.inf):
            reasons.append("Humidity is outside the commissioned range")

        baseline = baseline or {}
        evidence: dict[str, ThresholdEvidence] = {}
        mapping = {
            "formalin": FruitCondition.FORMALIN_CONTAMINATED,
            "carbide": FruitCondition.CALCIUM_CARBIDE_CONTAMINATED,
            "rotten": FruitCondition.ROTTEN,
        }
        matches: list[tuple[float, FruitCondition]] = []
        for name, condition in mapping.items():
            rule = profile[name]
            channel = rule["channel"]
            mean = fmean(values[channel])
            base = float(baseline.get(channel, 0.0)) if rule.get("baselineAdjusted", False) else 0.0
            adjusted = max(0.0, mean - base)
            threshold = float(rule["threshold"])
            ratio = adjusted / threshold if threshold > 0 else 0.0
            matched = adjusted >= threshold
            evidence[name] = ThresholdEvidence(
                channel=channel,
                raw_mean=round(mean, 6),
                baseline=round(base, 6),
                adjusted_mean=round(adjusted, 6),
                threshold=threshold,
                threshold_index_percent=round(min(100.0, max(0.0, ratio * 100.0)), 1),
                matched=matched,
            )
            if matched:
                matches.append((ratio, condition))

        if reasons:
            condition = FruitCondition.INCONCLUSIVE
        elif len(matches) > 1:
            condition = FruitCondition.INCONCLUSIVE
            reasons.append("Multiple condition thresholds matched")
        elif matches:
            condition = max(matches, key=lambda item: item[0])[1]
            reasons.append(f"{condition.value} threshold matched")
        else:
            condition = FruitCondition.FRESH
            reasons.append("All condition indices are below their thresholds")

        route = Route.SAFE if condition == FruitCondition.FRESH else Route.UNSAFE
        return ThresholdResult(
            condition=condition,
            route=route,
            fruit_type=fruit_type.upper(),
            valid=True,
            quality="VALID" if condition != FruitCondition.INCONCLUSIVE else "REVIEW_REQUIRED",
            profile_version=str(self.config.get("profileVersion", "unknown")),
            commissioned=bool(self.config.get("commissioned", False)),
            evidence=evidence,
            reasons=tuple(reasons),
            disclaimer=str(self.config.get("disclaimer", "Threshold-relative research screening only.")),
        )

    def _invalid(self, fruit_type: str, reason: str) -> ThresholdResult:
        return ThresholdResult(
            condition=FruitCondition.INCONCLUSIVE,
            route=Route.UNSAFE,
            fruit_type=fruit_type.upper(),
            valid=False,
            quality="INVALID",
            profile_version=str(self.config.get("profileVersion", "unknown")),
            commissioned=bool(self.config.get("commissioned", False)),
            evidence={},
            reasons=(reason,),
            disclaimer=str(self.config.get("disclaimer", "Threshold-relative research screening only.")),
        )

