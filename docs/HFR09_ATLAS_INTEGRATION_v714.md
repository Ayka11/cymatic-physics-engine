# HFR-09-REAL Atlas Integration into CPE E2 v7.14

## Integrated assets

- `assets/hfr09/CPE_HFR09_AZ_CYMATIC_ATLAS.png`
- `assets/hfr09/CPE_HFR09_AZ_UNIQUE_GLYPHS.png`
- `assets/hfr09/F1_F2_CALIBRATION.png`
- `assets/hfr09/vowel_formant_targets.csv`
- `assets/hfr09/FORMANT_LOCK_VERIFICATION.json`
- `assets/hfr09/CALIBRATION_MANIFEST.json`
- `assets/hfr09/audio/*.wav`

## Interpretation boundary

The atlas and glyphs are visualization/symbolization assets. They do not replace measured human-speech data. The calibration audio is synthetic source-filter material used to test deterministic acoustic reconstruction behavior.

The unique glyph layer is a candidate writing representation. Its scientific distinctiveness should be tested quantitatively against acoustic feature vectors and independent speech observations rather than assumed from visual appearance.

## HF integration

`app.py` exposes three tabs:

- Cymatic Atlas
- Unique Glyphs
- Acoustic Calibration

The application also displays the v7.03–v7.14 pipeline status and preserves the fail-closed scientific gate.
