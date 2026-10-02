# v7.13 — Real MMS-FA Corpus Run

v7.13 is the execution layer that runs real WAV + transcript manifest entries through MMS-FA and then requires an explicit, auditable phone-map sidecar before producing phone-level observations.

## Input manifest

JSONL, one record per utterance:

```json
{"utterance_id":"u001","speaker_id":"spk01","audio_file":"audio/u001.wav","transcript":"cat","phone_map_file":"maps/u001.jsonl"}
```

The phone-map file must contain explicit records with `phone`, `source_char_start`, `source_char_end`, `mapping_source`, and optionally `mapping_method`.

## Fail-closed rules

- no empty manifests;
- no missing speaker/utterance/audio/transcript fields;
- no missing phone-map sidecar;
- no synthetic alignment;
- no guessed grapheme-to-phoneme mapping;
- any MMS-FA runtime error blocks that utterance;
- projected output is written only from validated explicit mappings.

v7.13 does not claim that 680 candidates exist. The downstream v7.04–v7.09 gates must still be run on the resulting real observations.
