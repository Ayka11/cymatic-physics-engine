# CPE E2 v7.08 — Reproducibility Manifest

## Purpose

v7.08 is the provenance and reproducibility gate between corpus QC and the final benchmark. It creates a content-addressed record of the exact upstream status artifacts, configuration files, Python source, and execution environment used for a release candidate.

## Chain

`REAL MMS-FA → v7.04 validator → v7.05 candidate QC → v7.06 680 dataset → v7.07 corpus/speaker QC → v7.08 manifest → v7.09 benchmark`

## Fail-closed policy

The manifest is **BLOCKED** unless all required upstream status artifacts are present and in a PASS-compatible state. MMS-FA must have actually executed with available weights. Missing artifacts are never substituted, and synthetic/manual/guessed/repaired observations are never accepted.

`PASS_WITH_REVIEW` is retained as an auditable state but does not silently erase the review condition; the final benchmark must explicitly decide whether that state is acceptable.

## Content addressing

SHA-256 hashes are recorded for required status artifacts and all `config/*.json` and `cymatic_engine/**/*.py` files. A `chain_sha256` is computed over the complete manifest payload before the hash field itself is added.

## Environment

The manifest records Python version, implementation, and platform. This is metadata for reproducibility, not a claim that two environments are binary-identical.

## Scientific status

This infrastructure remains at maximum evidence level **E1**. A reproducibility manifest does not constitute experimental validation of the Cymatic Physics Engine.
