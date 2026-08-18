import json
from pathlib import Path

from backend.app.classification.rfalter import ThresholdClassifier
from backend.app.domain.types import FruitCondition


ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "config" / "thresholds.json").read_text(encoding="utf-8"))


def samples(mq3=100.0, mq136=100.0, ch2o=0.02, temperature=25.0, humidity=60.0, count=5):
    return [
        {"elapsed": float(index), "mq3": mq3, "mq136": mq136, "ch2o": ch2o,
         "temperature": temperature, "humidity": humidity}
        for index in range(count)
    ]


def test_fresh_routes_safe():
    result = ThresholdClassifier(CONFIG).classify("APPLE", samples())
    assert result.condition.value == "FRESH"
    assert result.route.value == "SAFE"
    assert result.valid is True


def test_formalin_routes_unsafe_with_index():
    result = ThresholdClassifier(CONFIG).classify("MANGO", samples(ch2o=0.18))
    assert result.condition.value == "FORMALIN_CONTAMINATED"
    assert result.route.value == "UNSAFE"
    assert result.evidence["formalin"].threshold_index_percent == 100.0
    assert result.overall_confidence_percent > 50
    assert result.demo_fusion["sensor"]["weightPercent"] == 90.0
    assert result.demo_fusion["image"]["weightPercent"] == 10.0
    assert abs(
        result.demo_fusion["sensor"]["contributionPercent"]
        + result.demo_fusion["image"]["contributionPercent"]
        - result.overall_confidence_percent
    ) <= 0.1
    assert result.demo_fusion["image"]["predictedClass"] == "Mango_Formalin Contaminated"


def test_engineers_initial_peak_average_delta_and_slope_for_gas_channels():
    rows = samples(count=5)
    for index, row in enumerate(rows):
        row["ch2o"] = 0.02 + index * 0.04
    result = ThresholdClassifier(CONFIG).classify("APPLE", rows)
    features = result.engineered_features["ch2o"]
    assert features.initial == 0.02
    assert features.peak == 0.18
    assert features.average == 0.1
    assert features.delta == 0.16
    assert features.slope > 0
    assert set(result.engineered_features) == {"mq3", "mq136", "ch2o"}


def test_multiple_matches_are_inconclusive_and_fail_safe():
    result = ThresholdClassifier(CONFIG).classify("ORANGE", samples(mq3=850, mq136=800))
    assert result.condition is FruitCondition.INCONCLUSIVE
    assert result.route.value == "UNSAFE"
    assert "Multiple" in result.reasons[0]


def test_invalid_channel_fails_safe():
    bad = samples()
    bad[2]["mq3"] = None
    result = ThresholdClassifier(CONFIG).classify("APPLE", bad)
    assert result.valid is False
    assert result.condition is FruitCondition.INCONCLUSIVE
    assert result.route.value == "UNSAFE"


def test_environment_outside_profile_requires_review():
    result = ThresholdClassifier(CONFIG).classify("APPLE", samples(temperature=55))
    assert result.condition.value == "INCONCLUSIVE"
    assert result.route.value == "UNSAFE"
