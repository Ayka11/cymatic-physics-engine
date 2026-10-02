# v7.12 — Deterministic Character→Phone Projection Engine

## Purpose

v7.11 MMS-FA produces character/token-level time spans. v7.12 converts those spans to the canonical 34-phone representation **only when an explicit, auditable character→phone map is supplied**.

The engine intentionally does **not** infer pronunciation from spelling and does not silently use rules such as `a → æ`. This prevents a grapheme/token alignment from being mislabeled as a phoneme alignment.

## Contract

Input:

- MMS-FA character spans with transcript character offsets and sample boundaries;
- an explicit phone map containing `phone`, `source_char_start`, `source_char_end`, `mapping_source`;
- MMS-FA provenance.

Output:

- projected phone intervals;
- inherited minimum confidence across source character spans;
- source/model/audio/transcript provenance;
- deterministic `projection_hash` per phone record.

## Fail-closed conditions

The projection is `BLOCKED` when:

- the phone map is absent;
- a phone is outside the canonical 34-phone vocabulary;
- a mapping points to uncovered transcript characters;
- projected phone intervals overlap;
- required provenance is absent upstream.

No synthetic or guessed phone is emitted.

## Scientific rationale

Forced alignment produces token/character timing from a model vocabulary; a separate pronunciation representation is required before claiming phone-level timing. The projection layer makes that dependency explicit and auditable.
