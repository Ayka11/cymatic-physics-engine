# CPE E2 v7.06 — 680-Candidate Dataset Builder

v7.06 converts a **v7.05 PASS** candidate selection into a deterministic, content-addressed JSONL dataset.

## Gate

`v7.05 selection PASS + complete + exactly 680 records` is mandatory. Any other state is `BLOCKED`.

## Cardinality

- 34 canonical phones
- exactly 20 candidates per phone
- exactly 680 records total
- candidate ranks `01..20` within every phone

## Integrity

The builder rejects duplicate candidate IDs, duplicate `source_key` observations, missing provenance, wrong cardinality, and rank gaps. It does not synthesize, repair, duplicate, or re-align observations.

Each record preserves:

`audio_sha256`, `transcript_sha256`, `model_id`, `model_version`, `alignment_config_hash`, `alignment_hash`, and `source_key`.

The canonical JSONL bytes are SHA-256 hashed and the digest is stored in `DATASET_MANIFEST.json`.

## Empty/incomplete state

Because the current v7.03 package reports that real MMS-FA execution/model weights are not present, a real 680-record dataset cannot legitimately be emitted yet. The builder is therefore implemented and fail-closed; it will produce the dataset only when the upstream real MMS-FA → v7.04 → v7.05 pipeline supplies a complete PASS selection.
