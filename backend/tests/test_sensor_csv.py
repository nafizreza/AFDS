import csv
import io

from backend.app.services.sensor_csv import CSV_COLUMNS, build_sensor_capture_csv


def test_sensor_capture_csv_contains_timestamped_sensor_and_quality_data():
    content, filename = build_sensor_capture_csv({
        "captureId": "20260819T120000Z-ABC123",
        "samples": [{
            "capturedAtUtc": "2026-08-19T12:00:01+00:00",
            "elapsed": 1.002,
            "deviceMillis": 4500,
            "sequence": 8,
            "mq3": 101.2,
            "mq136": 88.4,
            "ch2o": 0.031,
            "temperature": 27.5,
            "humidity": 61.0,
            "quality": {"ch2oValid": True, "dhtValid": True},
        }],
    })

    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    assert filename == "afds_sensor_capture_20260819T120000Z-ABC123.csv"
    assert list(rows[0]) == CSV_COLUMNS
    assert rows[0]["captured_at_utc"] == "2026-08-19T12:00:01+00:00"
    assert rows[0]["mq3"] == "101.2"
    assert rows[0]["temperature_c"] == "27.5"
    assert rows[0]["ch2o_valid"] == "True"
