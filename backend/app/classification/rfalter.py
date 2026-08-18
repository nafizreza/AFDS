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
GAS_CHANNELS = ("mq3", "mq136", "ch2o")


@dataclass(frozen=True)
class EngineeredFeatures:
    initial: float
    peak: float
    average: float
    final: float
    delta: float
    slope: float
    duration_seconds: float
    sample_count: int


@dataclass(frozen=True)
class ThresholdEvidence:
    channel: str
    raw_mean: float
    baseline: float
    adjusted_mean: float
    feature_score: float
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
    engineered_features: dict[str, EngineeredFeatures]
    overall_confidence_percent: float
    confidence_basis: str
    demo_fusion: dict[str, Any]
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

    @staticmethod
    def _engineer(values: list[float], timestamps: list[float]) -> EngineeredFeatures:
        initial = values[0]
        final = values[-1]
        average = fmean(values)
        elapsed = [stamp - timestamps[0] for stamp in timestamps]
        duration = max(0.0, elapsed[-1])
        mean_time = fmean(elapsed)
        denominator = sum((stamp - mean_time) ** 2 for stamp in elapsed)
        slope = 0.0 if denominator == 0 else sum(
            (stamp - mean_time) * (value - average) for stamp, value in zip(elapsed, values)
        ) / denominator
        return EngineeredFeatures(
            initial=round(initial, 6),
            peak=round(max(values), 6),
            average=round(average, 6),
            final=round(final, 6),
            delta=round(final - initial, 6),
            slope=round(slope, 6),
            duration_seconds=round(duration, 3),
            sample_count=len(values),
        )

    @staticmethod
    def _feature_score(features: EngineeredFeatures, baseline: float, threshold: float) -> float:
        initial = max(0.0, features.initial - baseline)
        peak = max(0.0, features.peak - baseline)
        average = max(0.0, features.average - baseline)
        final = max(0.0, features.final - baseline)
        level_score = 0.10 * initial + 0.25 * peak + 0.45 * average + 0.20 * final
        trend_signal = 0.10 * max(0.0, features.delta) + 0.05 * max(
            0.0, features.slope * features.duration_seconds
        )
        # Dynamic evidence may strengthen a level response, but it cannot
        # dominate a condition without a commissioned level threshold.
        return level_score + min(max(0.0, threshold * 0.15), trend_signal)

    @staticmethod
    def _demo_fusion(fruit_type: str, condition: FruitCondition, overall: float) -> dict[str, Any]:
        image_class = f"{fruit_type.title()}_{condition.value.replace('_', ' ').title()}"
        sensor_contribution = round(overall * 0.90, 1)
        image_contribution = round(overall - sensor_contribution, 1)
        return {
            "mode": "DEMONSTRATION",
            "overallConfidencePercent": round(overall, 1),
            "sensor": {
                "layer": 2,
                "name": "Sensor data model",
                "source": "rfalter.py engineered-feature screening",
                "weightPercent": 90.0,
                "contributionPercent": sensor_contribution,
                "demo": True,
            },
            "image": {
                "layer": 3,
                "name": "Fruit image classification",
                "source": "rfalter.py derived image-model placeholder",
                "weightPercent": 10.0,
                "contributionPercent": image_contribution,
                "predictedClass": image_class,
                "snapshotUrl": None,
                "demo": True,
            },
            "formula": "Overall demo confidence is split into 90% sensor-data and 10% image-processing contributions.",
        }

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
        timestamps: list[float] = []
        previous_timestamp: float | None = None
        try:
            for index, sample in enumerate(rows):
                timestamp = self._number(sample.get("elapsed", index), f"sample[{index}].elapsed")
                if previous_timestamp is not None and timestamp < previous_timestamp:
                    raise ValueError("Sensor timestamps are out of order")
                previous_timestamp = timestamp
                timestamps.append(timestamp)
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
        engineered = {channel: self._engineer(values[channel], timestamps) for channel in GAS_CHANNELS}
        evidence: dict[str, ThresholdEvidence] = {}
        mapping = {
            "formalin": FruitCondition.FORMALIN_CONTAMINATED,
            "carbide": FruitCondition.CALCIUM_CARBIDE_CONTAMINATED,
            "rotten": FruitCondition.ROTTEN,
        }
        matches: list[tuple[float, FruitCondition, str]] = []
        response_ratios: list[float] = []
        for name, condition in mapping.items():
            rule = profile[name]
            channel = rule["channel"]
            features = engineered[channel]
            mean = features.average
            base = float(baseline.get(channel, 0.0)) if rule.get("baselineAdjusted", False) else 0.0
            adjusted = max(0.0, mean - base)
            threshold = float(rule["threshold"])
            score = self._feature_score(features, base, threshold)
            ratio = score / threshold if threshold > 0 else 0.0
            response_ratios.append(ratio)
            matched = score >= threshold
            evidence[name] = ThresholdEvidence(
                channel=channel,
                raw_mean=round(mean, 6),
                baseline=round(base, 6),
                adjusted_mean=round(adjusted, 6),
                feature_score=round(score, 6),
                threshold=threshold,
                threshold_index_percent=round(min(100.0, max(0.0, ratio * 100.0)), 1),
                matched=matched,
            )
            if matched:
                matches.append((ratio, condition, name))

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
        if condition == FruitCondition.FRESH:
            proximity = max(response_ratios, default=0.0)
            overall_confidence = max(55.0, min(99.0, 100.0 - proximity * 45.0))
        elif condition == FruitCondition.INCONCLUSIVE:
            overall_confidence = 50.0
        else:
            _, _, matched_name = max(matches, key=lambda item: item[0])
            matched_rule = profile[matched_name]
            score = evidence[matched_name].feature_score
            threshold = float(matched_rule["threshold"])
            danger = float(matched_rule.get("danger", threshold * 1.5))
            span = max(danger - threshold, threshold * 0.1)
            overall_confidence = 55.0 + 44.0 * min(1.0, max(0.0, (score - threshold) / span))
        overall_confidence = round(overall_confidence, 1)
        return ThresholdResult(
            condition=condition,
            route=route,
            fruit_type=fruit_type.upper(),
            valid=True,
            quality="VALID" if condition != FruitCondition.INCONCLUSIVE else "REVIEW_REQUIRED",
            profile_version=str(self.config.get("profileVersion", "unknown")),
            commissioned=bool(self.config.get("commissioned", False)),
            evidence=evidence,
            engineered_features=engineered,
            overall_confidence_percent=overall_confidence,
            confidence_basis="Heuristic engineered-feature screening score; not a calibrated probability.",
            demo_fusion=self._demo_fusion(fruit_type, condition, overall_confidence),
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
            engineered_features={},
            overall_confidence_percent=0.0,
            confidence_basis="No confidence is reported for invalid sensor input.",
            demo_fusion=self._demo_fusion(fruit_type, FruitCondition.INCONCLUSIVE, 0.0),
            reasons=(reason,),
            disclaimer=str(self.config.get("disclaimer", "Threshold-relative research screening only.")),
        )
