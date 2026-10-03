from __future__ import annotations

import json
from pathlib import Path

import app.workbench as workbench
from app.workbench import _apply_evidence_gate


def test_implementation_label_is_not_release_pass():
    result = _apply_evidence_gate(
        "ALIGNMENT_VALIDATOR_STATUS.json",
        {"status": "IMPLEMENTED", "fail_closed": True},
    )
    assert result["declared_status"] == "IMPLEMENTED"
    assert result["status"] == "BLOCKED"
    assert result["evidence_gate"] == "BLOCKED"


def test_mms_fa_requires_weights_execution_and_passing_status():
    result = _apply_evidence_gate(
        "MMS_FA_STATUS.json",
        {"status": "PASS", "model_weights_available": True, "model_execution_performed": False},
    )
    assert result["status"] == "BLOCKED"
    assert "model_execution_performed" in result["missing_evidence_flags"]


def test_manifest_failures_cannot_be_overridden_by_top_level_pass():
    result = _apply_evidence_gate(
        "REPRODUCIBILITY_MANIFEST_v708.json",
        {
            "status": "PASS",
            "fail_closed": True,
            "failures": ["mms_fa_not_executed"],
            "artifacts": {"mms_fa_status": {"status": "BLOCKED"}},
            "reproducibility_policy": {"upstream_statuses_required": ["PASS", "PASS_WITH_REVIEW"]},
        },
    )
    assert result["status"] == "BLOCKED"
    assert result["evidence_gate"] == "BLOCKED"
    assert "failures_empty" in result["missing_evidence_flags"]
    assert "upstream_pass:mms_fa_status" in result["missing_evidence_flags"]


def test_manifest_without_content_hash_records_cannot_pass_gate():
    result = _apply_evidence_gate(
        "REPRODUCIBILITY_MANIFEST_v708.json",
        {
            "status": "PASS",
            "fail_closed": True,
            "failures": [],
            "artifacts": {"mms_fa_status": {"status": "PASS_WITH_REVIEW"}},
            "reproducibility_policy": {"upstream_statuses_required": ["PASS", "PASS_WITH_REVIEW"]},
        },
    )
    assert result["status"] == "BLOCKED"
    assert result["evidence_gate"] == "BLOCKED"
    assert any(flag.startswith("integrity:") for flag in result["missing_evidence_flags"])


def test_explicit_blocked_is_monotonic_even_if_flags_are_true():
    result = _apply_evidence_gate(
        "MMS_FA_STATUS.json",
        {"status": "BLOCKED", "model_weights_available": True, "model_execution_performed": True},
    )
    assert result["status"] == "BLOCKED"
    assert result["declared_status"] == "BLOCKED"


def test_unknown_artifact_is_not_relabelled_as_scientific_pass():
    payload = {"status": "IMPLEMENTED", "note": "implementation exists"}
    result = _apply_evidence_gate("UNREGISTERED_STATUS.json", payload)
    assert result["status"] == "IMPLEMENTED"
    assert result["declared_status"] == "IMPLEMENTED"


def test_release_pipeline_stages_require_emitted_outputs_not_only_implementation():
    cases = [
        ("V7_09_STATUS.json", {
            "status": "PASS",
            "real_mms_fa_execution_available_in_package": True,
            "real_mms_fa_execution_performed": True,
            "benchmark_result_emitted": True,
            "v707_pass": True,
            "v708_manifest_pass": True,
            "independent_deterministic_rerun_pass": False,
        }, "independent_deterministic_rerun_pass"),
        ("DATASET_BUILDER_STATUS.json", {
            "status": "PASS",
            "real_mms_fa_execution_available_in_package": True,
            "real_mms_fa_execution_performed": True,
            "upstream_candidate_qc_pass": True,
            "dataset_emitted": False,
        }, "dataset_emitted"),
        ("CANDIDATE_QC_STATUS.json", {
            "status": "PASS",
            "real_mms_fa_execution_available_in_package": True,
            "real_mms_fa_execution_performed": True,
            "alignment_output_present": True,
            "candidate_qc_executed": True,
            "selection_emitted": False,
        }, "selection_emitted"),
        ("ALIGNMENT_VALIDATOR_STATUS.json", {
            "status": "PASS",
            "fail_closed": True,
            "real_mms_fa_execution_performed": True,
            "alignment_output_present": True,
            "validation_executed": True,
            "validation_result_emitted": False,
        }, "validation_result_emitted"),
        ("CORPUS_BALANCE_QC_STATUS.json", {
            "status": "PASS",
            "dataset_present": True,
            "qc_executed": True,
            "qc_report_emitted": False,
        }, "qc_report_emitted"),
    ]
    for name, payload, missing_flag in cases:
        result = _apply_evidence_gate(name, payload)
        assert result["status"] == "BLOCKED", name
        assert missing_flag in result["missing_evidence_flags"], name


def test_readiness_milestone_requires_flags_even_when_milestone_label_is_allowed():
    result = _apply_evidence_gate(
        "REAL_CORPUS_RUN_v713_STATUS.json",
        {
            "status": "READY_FOR_REAL_CORPUS",
            "real_corpus_present": True,
            "real_mms_fa_execution_performed": False,
        },
    )
    assert result["status"] == "BLOCKED"
    assert "real_mms_fa_execution_performed" in result["missing_evidence_flags"]



def test_manifest_cannot_pass_when_real_upstream_files_fail_stage_gates(tmp_path, monkeypatch):
    upstream = {
        "MMS_FA_STATUS.json": {"status": "PASS"},
        "ALIGNMENT_VALIDATOR_STATUS.json": {"status": "PASS"},
        "CANDIDATE_QC_STATUS.json": {"status": "PASS"},
        "DATASET_BUILDER_STATUS.json": {"status": "PASS"},
        "CORPUS_BALANCE_QC_STATUS.json": {"status": "PASS"},
    }
    for filename, payload in upstream.items():
        (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(workbench, "RESULTS", tmp_path)
    monkeypatch.setattr(
        workbench,
        "verify_manifest_integrity",
        lambda root, manifest: {"valid": True, "status": "PASS", "issues": []},
    )
    manifest = {
        "status": "PASS",
        "fail_closed": True,
        "failures": [],
        "artifacts": {
            "mms_fa_status": {"status": "PASS"},
            "alignment_validator_status": {"status": "PASS"},
            "candidate_qc_status": {"status": "PASS"},
            "dataset_builder_status": {"status": "PASS"},
            "corpus_balance_qc_status": {"status": "PASS"},
        },
        "reproducibility_policy": {
            "upstream_statuses_required": ["PASS", "PASS_WITH_REVIEW"],
        },
    }
    result = _apply_evidence_gate("REPRODUCIBILITY_MANIFEST_v708.json", manifest)
    assert result["status"] == "BLOCKED"
    assert result["evidence_gate"] == "BLOCKED"
    assert any(
        flag.startswith("upstream_evidence_gate:")
        for flag in result["missing_evidence_flags"]
    )
