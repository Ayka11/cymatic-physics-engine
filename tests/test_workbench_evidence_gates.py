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
