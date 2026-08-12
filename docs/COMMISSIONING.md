# Commissioning checklist

Do not run an automatic fruit cycle until all items are verified:

- Power off: inspect wiring, grounds, chamber, feeder and collection boxes.
- Verify 12 V, LM2596 5 V and XL4015 5 V rails before connecting loads.
- Confirm ESP32 ADC inputs never exceed permitted voltage.
- Verify DRV8825 current limit and bounded travel without fruit.
- Calibrate SG90 valve open/closed angles with the mechanism unloaded.
- Calibrate both MG996R home/drop angles and hold times.
- Confirm pump polarity, maximum duty and effective purge duration.
- Confirm ZE08 frame format and units; do not label unverified values as ppm.
- Set camera ROI and presence thresholds using the final chamber lighting.
- Validate the YOLO26 weights and class labels on the installed camera.
- Establish fruit-specific sensor baselines and thresholds from labeled samples.
- Save the approved values as the reset baseline.

