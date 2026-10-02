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

## UTF-8 provenance metadata repair

The current local provenance output displayed `source_word` as mojibake (`РјР°РјР°`) instead of `мама`. This is a metadata text-encoding issue; it does not change the audio bytes or their SHA-256 values.

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
