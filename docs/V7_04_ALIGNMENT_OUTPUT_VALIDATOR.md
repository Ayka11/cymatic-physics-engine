# v7.04 — Alignment Output Validator

## Purpose

v7.04 is the fail-closed quality gate immediately downstream of the real
MMS-FA production adapter (v7.03). It validates **alignment output**, not
model presence.

```text
MMS-FA output
  -> phone normalization
  -> canonical 34-phone vocabulary gate
  -> boundary consistency
  -> confidence / QC
  -> provenance integrity
  -> 34 x 20 = 680 candidate pool
```

## Canonical phone vocabulary

34 phones are fixed and ordered:

`æ ɑ ɛ ɪ i ʌ ə u ʊ ɔ oʊ aɪ eɪ p b t d k g f v s z ʃ ʒ θ ð h m n l r w j`

No phone outside this vocabulary can enter the candidate pool.

## Validation rules

1. Required alignment fields must be present.
2. `phone_raw` is deterministically normalized and must agree with
   `phone_normalized`.
3. The normalized phone must be one of the canonical 34 phones.
4. `start_sample >= 0`, `end_sample > start_sample`.
5. Intervals may touch (`end == next start`) but may not overlap within an
   utterance.
6. When WAV metadata is supplied, both interval endpoints must be within the
   actual WAV sample range.
7. Optional `start_sec` / `end_sec` must equal sample boundaries divided by
   the actual WAV sample rate.
8. Confidence must be finite and in `[0,1]`, and must meet the v7.04 default
   QC threshold of `0.60`.
9. Required provenance is mandatory: audio hash, transcript hash, MMS-FA
   model identity/version, alignment config hash, and alignment hash.
10. `model_id` must be `MMS_FA` and `alignment_hash` must verify against the
    canonical row payload.
11. Any violation changes the result to `BLOCKED`; no partial acceptance is
    emitted.
12. Manual, guessed, or synthetic alignments remain forbidden.

## Candidate pool

The downstream pool is fixed at **34 phones × 20 segments = 680 candidates**.
Candidates are selected deterministically within each phone by confidence
(descending), duration (ascending), then stable identifiers. v7.04 does not
invent missing candidates: the pool reports missing slots until real validated
MMS-FA observations fill them.

## Scientific status

The validator does not upgrade evidence level. v7.03/v7.04 remain execution
and QC infrastructure; scientific evidence remains bounded by the actual
MMS-FA model execution and validated corpus/experiment.
