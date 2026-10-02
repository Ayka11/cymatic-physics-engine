# CPE E2 v7.15 — Full Platform Restoration

This release preserves the earlier full CPE experimental interface and engine and restores the v7.14 scientific validation layer on top of it.

## Included
- Full experimental UI: acoustic input, tone generation, cymatic formation, stability, experiment metadata, physical plate measurement workflow and reports.
- Physics, calibration, analysis, experiment, particles and visualization modules.
- v7.04–v7.14 scientific gates: alignment validation, candidate QC, 680-candidate dataset gate, speaker balance, reproducibility, benchmark, real corpus runner and scientific validation.
- HFR-09 REAL atlas and calibration assets.
- Explicit fail-closed physical validation and end-to-end provenance bridge.
- Hugging Face ZeroGPU-compatible root launcher.

## Scientific guard
A computational PASS or physical-validation PASS does not automatically establish E5, phoneme identity or glyph identity. Real measurements, calibration, provenance and independent controls are required.

## Verification
Local release verification: `48 passed`.
