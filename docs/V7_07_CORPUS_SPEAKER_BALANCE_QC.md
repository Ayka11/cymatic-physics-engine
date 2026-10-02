# CPE E2 v7.07 — Corpus / Speaker Balance QC

v7.07 audits the completed v7.06 680-candidate dataset. It does not synthesize,
repair, re-align, delete, or re-rank observations.

## Gates
- exact 680 records and 34×20 phone cardinality
- dataset SHA-256 integrity
- unique candidate IDs and source keys
- valid 34-phone vocabulary
- speaker identity present
- global speaker count and dominance guard
- per-phone speaker count and dominance guard
- confidence range and v7.05 threshold
- positive segment duration

## Diagnostics
Duration and confidence outliers use a robust median/MAD diagnostic. Outliers
are reported for review and are **not silently removed**. This avoids turning
v7.07 into an undocumented selection mechanism.

## Status semantics
- `PASS`: all hard gates pass and no diagnostic outliers are present.
- `PASS_WITH_REVIEW`: hard gates pass but diagnostic outliers require explicit review.
- `BLOCKED`: one or more hard gates fail.

The input is never mutated. No synthetic or guessed observations are permitted.
