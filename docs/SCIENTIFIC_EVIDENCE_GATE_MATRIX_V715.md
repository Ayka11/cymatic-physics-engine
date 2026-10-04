# CPE v7.15 Scientific Evidence Gate Matrix

This matrix distinguishes implementation state from evidence readiness. A status label is not itself proof that the corresponding work was performed.

| Artifact | Current declared status | Evidence prerequisites | Interpretation until prerequisites pass |
|---|---|---|---|
| REAL_CORPUS_RUN_v713_STATUS.json | READY_FOR_REAL_CORPUS | real corpus present; real MMS-FA execution performed; source provenance recorded | BLOCKED for claims of an executed real-corpus run |
| SCIENTIFIC_VALIDATION_v714_STATUS.json | BLOCKED | real corpus; real MMS-FA execution; independent reference; explicit permission for the specific scientific accuracy claim | BLOCKED |
| REPRODUCIBILITY_MANIFEST_v708.json | BLOCKED | content-addressed inputs; all required upstream artifacts at PASS or PASS_WITH_REVIEW; no embedded failures | BLOCKED |
| V7_09_STATUS.json | IMPLEMENTED_BLOCKED_UNTIL_REAL_INPUT | real MMS-FA execution available and performed; benchmark result emitted; v7.07 and v7.08 gates passed; independent deterministic rerun | BLOCKED until all release prerequisites pass |
| CORPUS_BALANCE_QC_STATUS.json | BLOCKED | actual v7.06 dataset available; QC executed and its output/provenance recorded | BLOCKED |
| DATASET_BUILDER_STATUS.json | IMPLEMENTED_BLOCKED_UNTIL_REAL_INPUT | valid upstream v7.05 PASS based on real MMS-FA alignment; dataset emitted and validated | BLOCKED until real inputs exist |
| CANDIDATE_QC_STATUS.json | IMPLEMENTED | real upstream v7.04 alignment output; candidate QC results and provenance | implementation-only, not a candidate-selection PASS |
| ALIGNMENT_VALIDATOR_STATUS.json | IMPLEMENTED | actual MMS-FA alignment output; validation results; source/hash integrity | implementation-only, not an alignment PASS |
| MMS_FA_STATUS.json | BLOCKED | model weights available; model execution performed; execution provenance and output artifact recorded | BLOCKED |

## Explicit provenance flags required by the v7.15 UI gate

The UI gate treats each of the following as a separate, explicit Boolean evidence assertion; an absent field is not interpreted as true:

- `REAL_CORPUS_RUN_v713_STATUS.json`: `real_corpus_present`, `real_mms_fa_execution_performed`, and `source_provenance_recorded`.
- `SCIENTIFIC_VALIDATION_v714_STATUS.json`: real corpus and execution, source provenance, an independent reference, and explicit permission for the specific accuracy claim.
- `MMS_FA_STATUS.json`: model weights, model execution, execution provenance, and a recorded output artifact.
- `ALIGNMENT_VALIDATOR_STATUS.json`: fail-closed mode, real execution, alignment output, executed validation, emitted validation result, source/hash integrity, and validation provenance.
- `CANDIDATE_QC_STATUS.json`: real execution, alignment output, candidate QC execution, emitted selection, and candidate-QC provenance.
- `DATASET_BUILDER_STATUS.json`: real execution, upstream candidate-QC pass, explicit v7.05 pass, emitted dataset, and dataset provenance.
- `CORPUS_BALANCE_QC_STATUS.json`: dataset and dataset provenance, executed QC, emitted QC report, and QC provenance.
- `V7_09_STATUS.json`: real execution availability and execution, emitted benchmark, v7.07/v7.08 passes, independent deterministic rerun, and benchmark provenance.

These flags are assertions that must be backed by the named evidence artifacts and provenance records. Setting a flag to `true` without those records is not scientific validation; the UI gate is a fail-closed guard, not an independent provenance verifier for every upstream artifact.

## Gate design requirements

1. Preserve the declared status in a separate field; never silently overwrite provenance.
2. Keep implementation status separate from scientific evidence-gate status.
3. Never promote a status from IMPLEMENTED, READY, COMPLETE, or a caller-supplied label to PASS.
4. Explicit BLOCKED states and embedded failure lists are monotonic: a UI gate must not clear them.
5. Validate artifact-specific prerequisites. Do not impose one generic set of flags on unrelated artifact types.
6. Validate that an artifact is a JSON object; malformed, missing, or unreadable artifacts remain BLOCKED/UNAVAILABLE/UNREADABLE.
7. Expose failed prerequisites in the UI and test each gate with missing, false, conflicting, and passing evidence.
8. A passing software test or reproducible audio STFT is not independent physical validation. Physical claims require calibrated measurements and appropriate independent controls.

## Current audit finding

The current `app/workbench.py::_apply_evidence_gate` defines artifact-specific evidence requirements for REAL_CORPUS_RUN, SCIENTIFIC_VALIDATION, V7_09, DATASET_BUILDER, CANDIDATE_QC, ALIGNMENT_VALIDATOR, MMS_FA, and CORPUS_BALANCE_QC, and applies additional upstream and integrity checks to the reproducibility manifest. The UI gate checks the presence of explicit Boolean evidence flags; this alone does not independently verify that every upstream provenance record or scientific artifact is authentic and valid. Tests cover selected missing-evidence scenarios. Production-path generation and verification of provenance records require separate validation.
