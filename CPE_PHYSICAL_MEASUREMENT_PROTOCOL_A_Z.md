# CPE Physical Measurement Protocol A–Z

**Version:** 1.0  
**CPE:** v3.1.3  
**Purpose:** controlled physical measurement of sound-excited particle patterns for A–Z phonetic experiments.

## 1. Scientific purpose

This protocol is designed to let independent users collect **real physical measurements** that can later be compared with CPE reduced-order calculations.

The experiment tests whether repeated acoustic inputs associated with a phoneme/letter produce reproducible spatial patterns under a fixed physical setup.

**Important:** A letter is a linguistic label. The experiment does not assume that a letter has a unique physical shape. The physical pattern must be measured first.

## 2. Recommended apparatus

- Flat plate: reference starting geometry **300 × 300 mm, 1 mm steel**.
- Rigid support with repeatable boundary conditions; document whether edges are simply supported, clamped, or another configuration.
- Excitation: speaker/shaker/voice-coupled actuator. Record the exact method and mounting position.
- Audio interface or recorder, preferably **48 kHz mono WAV**.
- Camera mounted approximately normal to the plate for top-view imaging.
- Fine, dry, non-reactive particles suitable for the apparatus and local safety requirements.
- Stable lighting and vibration isolation.
- Ruler/calibration marker visible in the image when possible.

The 300 × 300 × 1 mm steel plate is the CPE reference configuration, not a universal requirement. Any deviation must be recorded.

## 3. A–Z acoustic preparation

For an English A–Z screening, record the **sound associated with the letter name**, or preferably a defined phoneme target. Do not mix these concepts.

For each target:

1. Create a stable recording of approximately **3–5 s**.
2. Use a quiet environment.
3. Keep microphone position and gain fixed.
4. Avoid clipping.
5. Save the original uncompressed WAV.
6. Record the speaker ID and utterance ID.
7. For phoneme studies, document the IPA target separately from the grapheme.

Because English letter names can contain multiple phonemes, a letter-name experiment is **not equivalent** to a single-phoneme experiment.

## 4. Physical measurement procedure

### PV-A — Setup

1. Install the plate and record dimensions, thickness, material and support condition.
2. Photograph the setup.
3. Record actuator type, location and orientation.
4. Record camera model, distance, lens and image resolution.
5. Ensure the apparatus is mechanically isolated from external vibration.

### PV-B — Particle preparation

1. Clean the plate.
2. Apply a thin, approximately uniform particle layer.
3. Record particle type and approximate amount/coverage.
4. Do not change particle type or layer procedure between comparison runs.

### PV-C — Excitation

1. Start with a low, safe excitation level.
2. For calibration, test controlled sine tones at the reference modal frequencies supplied by CPE.
3. For speech, play or produce the target recording with the same gain and actuator configuration.
4. Allow the pattern to develop before imaging.
5. Do not change the plate mounting during a comparison series.

### PV-D — Imaging

1. Capture a high-resolution top-view image.
2. Keep camera geometry fixed.
3. Include a scale marker where possible.
4. Save the original image without cropping, sharpening, contrast manipulation, or geometric warping.
5. Repeat each condition at least 3 times for an initial reproducibility check.

### PV-E — Replication

For each A–Z target, record multiple independent utterances. A stronger study should use multiple speakers and repeat the complete setup on separate sessions.

Recommended research progression:

- Pilot: ≥3 repeats per target.
- Stronger screening: ≥10 utterances per target and ≥3 speakers.
- Cross-speaker validation: ≥30 utterances per target and ≥5 speakers.
- Strong validation: ≥100 utterances per target and ≥10 speakers.

These are research design targets, not universal statistical standards.

## 5. CPE app workflow

1. Select **Real audio / speech**.
2. Upload the original WAV.
3. Enter the **grapheme/letter** as an external label.
4. Enter the **IPA phoneme** when known.
5. Select the language/locale.
6. Set the analysis duration to the steady portion of the recording.
7. Run the CPE reduced-order computation.
8. Compare the computed density with the physical photograph.
9. Save the generated Markdown report and CSV.
10. Keep the original WAV and original photograph with the experiment ID.

The CPE result is a computational reduced-order result until acoustic/electromechanical transfer calibration and physical validation are completed.

## 6. Required metadata

Record at minimum:

- experiment_id
- date/time
- operator
- speaker_id
- utterance_id
- grapheme
- IPA phoneme
- language/locale
- plate dimensions and thickness
- material
- support/boundary condition
- actuator type and position
- excitation level / amplifier setting
- microphone/recorder
- sample rate
- camera and resolution
- particle material and application method
- room/environment notes
- original WAV SHA-256
- original image SHA-256

## 7. Data integrity

Never replace an original measurement with a processed image. Keep:

`raw/` → original WAV and photograph  
`normalized/` → explicitly documented analysis copies  
`metadata/` → measurement conditions  
`results/` → CPE reports, CSV and computed patterns

CPE should not be used to manufacture missing measurements.

## 8. Controls

At minimum include:

- no-excitation control;
- repeated identical excitation;
- pure-tone modal control;
- temporal-shuffle or phase-scramble computational controls where appropriate;
- independent repeated physical measurements.

## 9. Interpretation gate

Do not call a pattern a validated “A”, “B”, etc. merely because it was recorded while that sound was played.

Evidence should progress through:

**E0** computational → **E1** technically reproducible → **E2** repeated utterance → **E3** cross-speaker → **E4** discriminative → **E5** controls validated → **E6** independent replication.

The claim level must not exceed the evidence level.

## 10. Safety

Use only apparatus, particles and excitation levels appropriate to the equipment and environment. Secure the plate and actuator. Avoid inhalation or skin exposure to unsuitable powders. Do not exceed manufacturer limits for speakers, shakers, amplifiers, cameras or electrical equipment.
