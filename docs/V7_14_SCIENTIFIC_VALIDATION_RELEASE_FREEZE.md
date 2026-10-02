# v7.14 — Scientific Validation / Release Freeze

v7.14 is the final scientific gate before public release. It deliberately separates **pipeline validation** from **scientific accuracy claims**.

## Hard gates

- completed v7.09 benchmark;
- 680 records / 34 phones × 20 candidates;
- confidence and positive-duration checks;
- speaker coverage;
- v7.08 provenance manifest PASS;
- deterministic dataset hash on rerun;
- no synthetic/manual candidates.

## Scientific boundary

Internal QC does **not** establish that phone boundaries are accurate. To claim alignment accuracy, supply an independent reference annotation (e.g. expert/human boundaries) and run an explicit agreement/error analysis. Without that reference, the release may demonstrate a reproducible pipeline and candidate dataset, but must not report an accuracy score as if independently validated.

## Release policy

`PASS` means the computational release gates pass and an independent reference is present. `PASS_WITH_REVIEW` means computational gates pass but the scientific-reference requirement remains unresolved. `BLOCKED` means at least one hard gate failed.
