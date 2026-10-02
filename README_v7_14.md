# CPE E2 MASTER v7.14 — Scientific Validation / Release Freeze

v7.14 is the final validation gate before public release. It does not inflate the scientific claim: a reproducible software pipeline is not the same thing as independently verified phoneme-boundary accuracy.

## Current state

- v7.03–v7.13 infrastructure: implemented
- real MMS-FA corpus execution: not performed in this package
- 680 real candidates: not present
- independent reference alignment: not present
- status: **BLOCKED / release freeze not reached**
- tests: **39 passed**

## Scientific claim boundary

Without an independent reference annotation, this package may support claims about implementation, QC, provenance, determinism, and reproducibility. It must not report a phoneme-boundary accuracy score as independently validated.

## Next actual experiment

1. Provide the real WAV/transcript corpus and explicit phone-map inputs.
2. Run v7.13 on a fixed environment.
3. Build and validate the 680-candidate dataset.
4. Rerun deterministically and compare dataset hashes.
5. Provide independent reference boundaries for an evaluation subset.
6. Run v7.14 and freeze the release only if all hard gates pass.
