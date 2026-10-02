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

## Quantitative metrics added in the current utility

The JSON report now includes the following descriptive signal metrics:

- RMS normalized PCM amplitude.
- Peak absolute normalized PCM amplitude.
- Crest factor (peak divided by RMS; null for an all-zero signal).
- Count and fraction of samples at the signed PCM full-scale threshold.
- Zero-crossing rate per sample.
- Up to ten prominent local peaks from the mean STFT magnitude, expressed as frequency and relative dB.

These are signal-description metrics only. The listed spectral peaks are not automatically interpreted as phonemes, resonant modes, or evidence of physical cymatic effects.

## Validation and tests

Run the unit tests from the repository root:

```powershell
python -m pip install numpy matplotlib
python -m unittest discover -s cpe_hfr02/diagnostics/tests -v
```

The GitHub Actions workflow `.github/workflows/cpe-hfr02-diagnostics.yml` runs these tests on relevant pushes and pull requests. Tests use generated fixtures and verify software behavior; they do not validate the external recording or any physical system.

The generator checks provenance status, source/WAV SHA-256 values, PCM format, array dimensions, finite values, monotonic axes, and frequency bounds. It does **not** recompute the STFT from the WAV, so its checks do not prove that the stored arrays were derived from that WAV. That limitation is recorded in the JSON report.
