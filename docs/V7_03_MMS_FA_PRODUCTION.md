# v7.03 — MMS-FA Production Adapter

Production boundary for forced alignment. The adapter requires actual MMS-FA
weights and validated corpus/transcript inputs. It records sample boundaries,
normalized phones, confidence and cryptographic provenance. Manual alignment,
synthetic alignment and guessed boundaries are forbidden. This component
defines the execution contract; it does not claim model execution without
the actual weights and corpus.

## v7.04 interface note

Alignment records may include `start_sec`/`end_sec` only when an explicit `sample_rate` is supplied to `make_alignment_record`; seconds are derived as samples / sample rate. v7.04 independently validates those values against the actual WAV metadata.
