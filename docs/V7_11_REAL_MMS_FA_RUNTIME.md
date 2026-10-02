# CPE E2 v7.11 — Real MMS-FA Runtime

v7.11 is the first runtime layer that can perform actual inference with `torchaudio.pipelines.MMS_FA`.

The official TorchAudio MMS_FA bundle provides a multilingual forced-alignment acoustic model and tokenizer. It expects normalized/romanized text and operates at 16 kHz. The bundle's tokenizer maps normalized **characters** to model tokens; the aligner returns timestamps for those tokens.

Therefore v7.11 deliberately introduces a hard scientific boundary:

`MMS_FA character alignment != 34-phone alignment`

The pipeline refuses to pass character spans directly into the 34-phone vocabulary gate. A separately documented phone-projection layer is required. This prevents a grapheme from being silently mislabeled as a phoneme and protects the downstream 680-candidate dataset from invalid provenance.

## Runtime

`python scripts/run_mms_fa.py --audio sample.wav --text "..." --out alignment.json`

The first model load downloads/caches the MMS_FA checkpoint through TorchAudio. The model is approximately 1.2 GB according to the official tutorial's example download.

## Status semantics

- `MMS_FA alignment: PASS` means the actual acoustic alignment executed.
- `phone_projection: BLOCKED` means the result cannot yet enter the 34-phone/680-candidate pipeline.
- No synthetic or manual replacement is permitted.

## Licensing

The official MMS model weights are released under CC-BY-NC 4.0. Check the model/license terms before using the weights in a commercial deployment.
