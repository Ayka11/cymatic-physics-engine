# v7.05 — Candidate QC / Selection

v7.05 is the deterministic candidate-quality and selection stage downstream
of the v7.04 Alignment Output Validator.

```text
REAL MMS-FA
  -> v7.04 Alignment Output Validator
  -> PASS only
  -> v7.05 Candidate QC
  -> duplicate/source QC
  -> duration + confidence QC
  -> provenance QC
  -> speaker-diversity selection
  -> 34 x 20 candidate target
```

## Hard upstream gate

A v7.04 result other than `PASS` is a hard stop. v7.05 never repairs,
guesses, re-aligns, or synthesizes observations.

## Candidate QC

Each candidate must retain the MMS-FA provenance fields and `model_id == MMS_FA`.
The default thresholds are:

- confidence >= 0.60;
- duration >= 160 samples;
- duration <= 16,000 samples;
- canonical 34-phone vocabulary;
- unique source observation identity.

Rejected observations are retained only in the audit report with explicit
reasons and are never passed to selection.

## Selection

The target is exactly 20 candidates per canonical phone, i.e. 680 total.
Selection first gives distinct speakers an opportunity for representation,
then fills remaining positions subject to a maximum of 4 candidates from one
speaker for one phone. Final ordering is deterministic by confidence,
duration, speaker ID, utterance ID, start sample, and alignment hash.

If a phone cannot supply 20 eligible real observations under these constraints,
the result is `INCOMPLETE`; missing slots are reported. No synthetic or guessed
replacement is permitted.

## Scientific status

v7.05 is research-pipeline QC infrastructure. It does not increase the
scientific evidence level. Any scientific claim must remain bounded by actual
MMS-FA execution, corpus quality, and downstream experimental validation.
