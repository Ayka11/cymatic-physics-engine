# CPE E2 v7.13 — Real MMS-FA Corpus Run

v7.13 is the real-data execution layer. It does not fabricate the 680-candidate set. It executes MMS-FA on supplied WAV/transcript records and requires an explicit phone-map sidecar before phone-level observations can be emitted.

## Current release status

- v7.12 phone projection: implemented
- v7.13 corpus runner: implemented
- real corpus supplied in this package: **NO**
- real MMS-FA execution in this package: **NOT PERFORMED**
- 680-candidate dataset: **NOT CLAIMED**
- synthetic/manual fallback: **DISABLED**
- fail-closed: **ENABLED**

## Run

```bash
python scripts/run_real_corpus.py \
  --manifest path/to/manifest.jsonl \
  --output-dir results/real_corpus_v713
```

The manifest is JSONL with one utterance per line and requires `utterance_id`, `speaker_id`, `audio_file`, `transcript`, and `phone_map_file`.

The phone map is an auditable sidecar; v7.13 never guesses grapheme-to-phoneme correspondences.

## Scientific interpretation

A successful v7.13 run produces real MMS-FA observations. It is still not a scientific claim of 680 valid candidates. Those observations must pass v7.04, v7.05, v7.06, v7.07, v7.08 and v7.09 before a complete 680-candidate release can be declared.

## Tests

36 tests pass in the inherited + v7.13 suite.
