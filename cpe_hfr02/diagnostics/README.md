# CPE HFR-02 Diagnostic Visualization — E0

This artifact documents the diagnostic visualization stage for the alternate Russian «мама» recording processed in E0.

## Status

`AUDIO_STFT_DIAGNOSTICS_GENERATED_E0`

Source processing status:

`ALTERNATE_SOURCE_AUDIO_STFT_COMPUTED_E0`

## Recorded source hashes

- Source OGG SHA-256: `1eefeebaf93a8cf5cf4929c2d8e5be58349ee0ef6699ce34259cfe615d99b0a1`
- Canonical 48 kHz mono WAV SHA-256: `fa3d9019aacf86c67cffd2413d39e919bc30d65b7f0e1442acba1dbb9732c2af`

## Complex STFT

- Frequency bins: 8193
- Time frames: 48
- Array shape: `(8193, 48)` for both real and imaginary parts
- Complex phase preserved: yes
- Numerical finiteness: verified
- Nonzero imaginary component: verified

## Diagnostic plots

The visualization utility generates:

1. `01_audio_waveform.png` — canonical audio waveform.
2. `02_stft_magnitude_spectrogram.png` — relative-dB STFT magnitude.
3. `03_stft_phase.png` — complex STFT phase with low-magnitude bins masked.
4. `diagnostic_report.json` — provenance-linked hashes and plot metadata.

The utility validates the source and WAV hashes and the expected complex-array structure before generating plots.

## Scientific scope

These figures are audio-domain diagnostics. They are not measurements of a spatial cymatic plate field.

Relative STFT magnitude is not calibrated sound-pressure level. STFT phase is audio-domain phase, not a spatial plate-field phase map.

This stage does not establish acoustic-pressure calibration, acoustic-to-force transfer calibration, plate response, or particle/contact validation.

The alternate recording does not clear the separate HFR-06 canonical source-hash gate.

## Local generation

Use the accompanying `generate_diagnostics.py` script with the existing CPE HFR-02 Russian Mama run directory.