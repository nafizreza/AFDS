import json
from pathlib import Path

from backend.app.classification.rfalter import ThresholdClassifier


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


def test_multiple_matches_are_inconclusive_and_fail_safe():
    result = ThresholdClassifier(CONFIG).classify("ORANGE", samples(mq3=850, mq136=800))
    assert result.condition.value == "INCONCLUSIVE"
    assert result.route.value == "UNSAFE"
    assert "Multiple" in result.reasons[0]


def test_invalid_channel_fails_safe():
    bad = samples()
    bad[2]["mq3"] = None
    result = ThresholdClassifier(CONFIG).classify("APPLE", bad)
    assert result.valid is False
    assert result.condition.value == "INCONCLUSIVE"
    assert result.route.value == "UNSAFE"


def test_environment_outside_profile_requires_review():
    result = ThresholdClassifier(CONFIG).classify("APPLE", samples(temperature=55))
    assert result.condition.value == "INCONCLUSIVE"
    assert result.route.value == "UNSAFE"

