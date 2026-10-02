# CPE E2 v7.14 — End-to-End Validation Integration Fix

## Purpose

This patch connects the existing calibration physical-validation layer to the
end-to-end experiment record without weakening the scientific evidence gate.

## Changes

- `PhysicalValidationResult.passed` is now handled correctly.
- Dataclass and JSON-mapping validation results are both supported.
- Calibration provenance is integrated through `CalibrationManifest.content_hash()`.
- `evaluate_physical_validation()` is fail-closed:
  - missing metrics => FAIL;
  - empty thresholds => FAIL;
  - NaN/Inf/invalid values => FAIL.
- A physical-validation PASS does **not** automatically become E5.
- E5 (or another evidence level) requires an explicit validated evidence-level
  input from a caller that has actually established the required evidence.
- Failed physical validation can never be promoted by the requested evidence
  level.
- No measurements, thresholds, phoneme labels, glyph identities, or other
  scientific observations are fabricated.

## Scientific status

The synthetic reference experiment remains a reduced-order computational
reference. This patch does not convert synthetic data into physical evidence.

The real physical chain still requires real measurements, calibration,
provenance, controls, and the project's defined evidence criteria.

## Test coverage

The new tests cover:

1. missing validation metrics;
2. empty thresholds;
3. non-finite values;
4. dataclass input;
5. mapping input;
6. calibration hash integration;
7. failed-PV promotion blocking;
8. explicit evidence-level promotion;
9. deterministic record hashing.
