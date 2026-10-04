from __future__ import annotations

import json

from app import workbench


def test_real_corpus_readiness_is_blocked_when_real_evidence_flags_are_false():
    payload = {
        "status": "READY_FOR_REAL_CORPUS",
        "real_corpus_present": False,
        "real_mms_fa_execution_performed": False,
        "synthetic_fallback": False,
    }

    result = workbench._apply_evidence_gate("REAL_CORPUS_RUN_v713_STATUS.json", payload)

    assert result["declared_status"] == "READY_FOR_REAL_CORPUS"
    assert result["status"] == "BLOCKED"
    assert result["evidence_gate"] == "BLOCKED"
    assert result["missing_evidence_flags"] == [
        "real_corpus_present",
        "real_mms_fa_execution_performed",
        "source_provenance_recorded",
    ]


def test_scientific_validation_requires_corpus_execution_and_independent_reference():
    payload = {
        "status": "COMPLETE",
        "real_corpus_present": True,
        "real_mms_fa_execution_performed": True,
        "independent_reference_present": False,
        "scientific_accuracy_claim_allowed": False,
    }

    result = workbench._apply_evidence_gate("SCIENTIFIC_VALIDATION_v714_STATUS.json", payload)

    assert result["status"] == "BLOCKED"
    assert result["missing_evidence_flags"] == [
        "source_provenance_recorded",
        "independent_reference_present",
        "scientific_accuracy_claim_allowed",
    ]


def test_explicit_blocked_status_is_not_overridden_by_true_flags():
    payload = {
        "status": "BLOCKED",
        "real_corpus_present": True,
        "real_mms_fa_execution_performed": True,
        "independent_reference_present": True,
        "scientific_accuracy_claim_allowed": True,
    }

    result = workbench._apply_evidence_gate("SCIENTIFIC_VALIDATION_v714_STATUS.json", payload)

    assert result["status"] == "BLOCKED"
    assert result["declared_status"] == "BLOCKED"


def test_status_file_applies_evidence_gate_to_repository_artifact(tmp_path, monkeypatch):
    payload = {
        "status": "READY_FOR_REAL_CORPUS",
        "real_corpus_present": False,
        "real_mms_fa_execution_performed": False,
    }
    (tmp_path / "REAL_CORPUS_RUN_v713_STATUS.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    monkeypatch.setattr(workbench, "RESULTS", tmp_path)

    result = workbench._status_file("REAL_CORPUS_RUN_v713_STATUS.json")

    assert result["status"] == "BLOCKED"
    assert "real_corpus_present" in result["missing_evidence_flags"]



def test_mms_fa_smoke_test_cannot_pass_without_provenance_and_output_artifact():
    payload = {
        "status": "PASS_WITH_REVIEW",
        "model_weights_available": True,
        "model_execution_performed": True,
    }

    result = workbench._apply_evidence_gate("MMS_FA_STATUS.json", payload)

    assert result["status"] == "BLOCKED"
    assert result["missing_evidence_flags"] == [
        "execution_provenance_recorded",
        "output_artifact_recorded",
    ]


def test_mms_fa_gate_accepts_review_status_only_when_required_evidence_is_explicit():
    payload = {
        "status": "PASS_WITH_REVIEW",
        "model_weights_available": True,
        "model_execution_performed": True,
        "execution_provenance_recorded": True,
        "output_artifact_recorded": True,
    }

    result = workbench._apply_evidence_gate("MMS_FA_STATUS.json", payload)

    assert result["status"] == "PASS_WITH_REVIEW"
    assert result["evidence_gate"] == "EVIDENCE_FLAGS_PRESENT"
    assert "missing_evidence_flags" not in result


def test_dataset_builder_requires_upstream_v705_pass_and_provenance():
    payload = {
        "status": "PASS",
        "real_mms_fa_execution_available_in_package": True,
        "real_mms_fa_execution_performed": True,
        "upstream_candidate_qc_pass": True,
        "dataset_emitted": True,
    }

    result = workbench._apply_evidence_gate("DATASET_BUILDER_STATUS.json", payload)

    assert result["status"] == "BLOCKED"
    assert result["missing_evidence_flags"] == [
        "upstream_v7_05_pass",
        "dataset_provenance_recorded",
    ]


def test_alignment_validator_requires_source_hash_integrity_and_provenance():
    payload = {
        "status": "PASS",
        "fail_closed": True,
        "real_mms_fa_execution_performed": True,
        "alignment_output_present": True,
        "validation_executed": True,
        "validation_result_emitted": True,
    }

    result = workbench._apply_evidence_gate("ALIGNMENT_VALIDATOR_STATUS.json", payload)

    assert result["status"] == "BLOCKED"
    assert result["missing_evidence_flags"] == [
        "source_hash_integrity_pass",
        "validation_provenance_recorded",
    ]
