# CPE HFR-02 Diagnostic Visualization — E0

This artifact documents diagnostic visualization and reproducibility checks for the alternate Russian «мама» recording processed in E0.

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

## Diagnostic plots

The visualization utility generates:

1. `01_audio_waveform.png` — canonical audio waveform.
2. `02_stft_magnitude_spectrogram.png` — relative-dB STFT magnitude.
3. `03_stft_phase.png` — complex STFT phase with low-magnitude bins masked.
4. `diagnostic_report.json` — provenance-linked hashes and plot metadata.

The generator validates source and WAV hashes, PCM format, and complex-array structure before generating plots. It produces descriptive audio metrics, not physical validation.

## Independent STFT reproducibility verification

Install the dependencies and run the independent verifier against an existing run directory:

```powershell
python -m pip install numpy scipy
python cpe_hfr02/diagnostics/verify_stft_reproducibility.py --input "C:\path\to\CPE_HFR02_RussianMama_Run" --out "C:\path\to\stft_verification_report.json"
```

The verifier checks source and WAV hashes against provenance, requires the recorded E0 status and expected STFT settings, recomputes the complex STFT from the canonical PCM16 WAV, and compares frequency axes, time axes, matrix shape, real and imaginary values, and complex error under explicit numerical tolerances. A mismatch exits with an error rather than producing a verified status.

A successful report uses status `STFT_REPRODUCIBILITY_VERIFIED_E0`. This means only that the stored audio-domain STFT is numerically reproducible from the WAV under the specified settings. It does not establish spatial cymatic structure or a physical effect.

## Quantitative spectral and audio-domain phase report

After the independent STFT verifier passes, generate frame-level spectral metrics and a carefully scoped audio-domain phase diagnostic:

```powershell
python cpe_hfr02/diagnostics/analyze_audio_spectral_phase.py --input "C:\path\to\CPE_HFR02_RussianMama_Run" --out "C:\path\to\audio_spectral_phase_report.json"
```

The report contains per-frame band peak frequency and magnitude, spectral centroid, spectral flatness, and an audio-domain phase-increment residual concentration for frequency bins that meet an explicit relative-magnitude support threshold. The script calls the reproducibility verifier first and refuses to analyze if source/WAV hashes or the saved complex STFT fail validation.

Phase concentration is descriptive and depends on the selected STFT settings and magnitude threshold. The report now includes a threshold-sensitivity table at −20, −30, −40, −50, and −60 dB relative to the global STFT peak, counting bins that meet frame-support and adjacent-pair criteria. These counts explain why the primary configured threshold may yield zero eligible bins; they do not silently change the primary result. Each sensitivity row also reports up to 20 eligible frequency bins with their frame-support fraction, valid adjacent-frame pair count, and circular concentration of the residual audio-phase increments. These are exploratory threshold-specific diagnostics only; the primary `highest_concentration_bins` remains controlled solely by `--phase-floor-db`. The phase values are not spatial phase, not a physical resonance measurement, and not evidence of a cymatic effect. The report preserves the HFR-06 gate limitation.

## UTF-8 provenance metadata repair

The original local provenance output had displayed `source_word` as mojibake (`РјР°РјР°`). The current run now reports `source_word: мама` and the repair utility correctly returns `NO_CHANGE_NEEDED`; no edit is necessary. This was a metadata-only encoding issue and did not change audio bytes or their SHA-256 values.

Preview the narrowly scoped repair first:

```powershell
python cpe_hfr02/diagnostics/repair_provenance_encoding.py --provenance "C:\path\to\CPE_HFR02_RussianMama_Run\provenance.json"
```

Only if the preview reports the expected correction, apply it:

```powershell
python cpe_hfr02/diagnostics/repair_provenance_encoding.py --provenance "C:\path\to\CPE_HFR02_RussianMama_Run\provenance.json" --apply
```

The tool only corrects the exact known mojibake value for Russian-language E0 provenance, refuses unknown values or unexpected status, and changes no audio or STFT files. It atomically writes UTF-8 JSON and preserves both recorded source-hash fields.

## Quantitative metrics

The diagnostic report includes RMS normalized PCM amplitude, peak absolute normalized PCM amplitude, crest factor, clipping count/fraction, zero-crossing rate per sample, and up to ten prominent local peaks from mean STFT magnitude. These are descriptive signal features, not phoneme labels or evidence of physical resonance.

## Scientific scope and limitations

- Audio STFT diagnostics are not measurements of a spatial cymatic plate field.
- Relative STFT magnitude is not calibrated sound-pressure level.
- STFT phase is audio-domain phase, not a spatial plate-field phase map.
- This stage does not establish acoustic-pressure calibration, acoustic-to-force transfer calibration, plate response, or particle/contact validation.
- The alternate recording does not clear the separate HFR-06 canonical source-hash gate.

## Tests

Run the unit tests from the repository root:

```powershell
python -m pip install numpy matplotlib scipy
python -m unittest discover -s cpe_hfr02/diagnostics/tests -v
```

The GitHub Actions workflow runs these tests on relevant pushes and pull requests. Tests use generated fixtures and verify software behavior; they do not validate the external recording or any physical system.


## STFT parameter sensitivity

Run the parameter-sensitivity report after the baseline provenance/reproducibility gate passes:

```powershell
python cpe_hfr02/diagnostics/analyze_stft_parameter_sensitivity.py --input "C:\\path\\to\\CPE_HFR02_RussianMama_Run" --out "C:\\path\\to\\stft_parameter_sensitivity.json"
```

The report recomputes the audio STFT from the same canonical WAV across six predeclared configurations (window lengths 2048, 4096, and 8192 samples, with two hop sizes per length). It records frame count, frequency-grid spacing, mean-spectrum peak frequency, mean frame spectral centroid, and phase-support summaries at −40 and −60 dB. The 4096/1024/16384 configuration is included as the baseline for comparison.

Interpretation cautions:
- Frequency-grid spacing and frame support change with configuration; values from different configurations are not interchangeable measurements.
- Zero-padding makes the sampled frequency grid denser but does not add physical information.
- A peak or phase statistic that changes with the configuration should be reported as parameter-sensitive, not promoted as a physical resonance.
- The tool first verifies the stored baseline STFT against provenance and the canonical WAV. That gate is a software/reproducibility check, not physical validation.
- The alternate-source HFR-06 gate remains closed; physical cymatic claims require separately calibrated spatial measurements.
