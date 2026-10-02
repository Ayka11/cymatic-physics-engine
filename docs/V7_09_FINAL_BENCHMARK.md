# CPE E2 v7.09 — Final Benchmark

v7.09 is the final pre-release gate. It validates a completed real-MMS-FA
680-candidate dataset, v7.07 corpus QC, and a PASS v7.08 reproducibility
manifest. It does not create, repair, re-rank, or synthesize candidates.

## Release gates

- 680 records exactly
- all 34 canonical phones
- exactly 20 candidates per phone, ranks 01–20
- candidate/source uniqueness
- confidence in [0,1] and minimum 0.60
- positive sample duration
- speaker count and dominance constraints
- dataset SHA-256 integrity
- v7.07 PASS or PASS_WITH_REVIEW
- v7.08 PASS and fail-closed provenance
- deterministic dataset hash on an independent rerun
- no manual, guessed, synthetic, repaired, or duplicated fallback

A single failed gate produces `BLOCKED`.

## Evidence status

The release package intentionally contains no fabricated 680-record result.
Until real MMS-FA weights are executed against real WAV/transcript inputs, the
benchmark remains blocked. Evidence level therefore remains E1.
