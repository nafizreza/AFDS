from __future__ import annotations

import csv
import io
from typing import Any


CSV_COLUMNS = [
    "sample_number",
    "captured_at_utc",
    "elapsed_seconds",
    "device_millis",
    "sequence",
    "mq3",
    "mq136",
    "ch2o",
    "temperature_c",
    "humidity_percent",
    "ch2o_valid",
    "dht_valid",
]


def build_sensor_capture_csv(capture: dict[str, Any]) -> tuple[bytes, str]:
    """Render one bounded Maintenance capture as an Excel-friendly CSV download."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for index, sample in enumerate(capture.get("samples", []), start=1):
        quality = sample.get("quality") or {}
        writer.writerow({
            "sample_number": index,
            "captured_at_utc": sample.get("capturedAtUtc", ""),
            "elapsed_seconds": sample.get("elapsed", ""),
            "device_millis": sample.get("deviceMillis", ""),
            "sequence": sample.get("sequence", ""),
            "mq3": sample.get("mq3", ""),
            "mq136": sample.get("mq136", ""),
            "ch2o": sample.get("ch2o", ""),
            "temperature_c": sample.get("temperature", ""),
            "humidity_percent": sample.get("humidity", ""),
            "ch2o_valid": quality.get("ch2oValid", ""),
            "dht_valid": quality.get("dhtValid", ""),
        })
    filename = f"afds_sensor_capture_{capture['captureId']}.csv"
    return output.getvalue().encode("utf-8-sig"), filename
