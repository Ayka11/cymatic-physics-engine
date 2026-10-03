import json

from app.research.integration import ScientificResearchController


def test_research_status_panel_applies_fail_closed_evidence_gates(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "REAL_CORPUS_RUN_v713_STATUS.json").write_text(
        json.dumps({
            "status": "READY_FOR_REAL_CORPUS",
            "real_corpus_present": False,
            "real_mms_fa_execution_performed": False,
        }),
        encoding="utf-8",
    )
    (results / "SCIENTIFIC_VALIDATION_v714_STATUS.json").write_text(
        json.dumps({
            "status": "COMPLETE",
            "real_corpus_present": True,
            "real_mms_fa_execution_performed": True,
            "independent_reference_present": False,
            "scientific_accuracy_claim_allowed": False,
        }),
        encoding="utf-8",
    )

    controller = ScientificResearchController(root=tmp_path)
    statuses = {item.name: item for item in controller.get_status()}

    assert statuses["Real Corpus"].status == "BLOCKED"
    assert "real_corpus_present" in statuses["Real Corpus"].detail
    assert statuses["Scientific Validation"].status == "BLOCKED"
    assert "independent_reference_present" in statuses["Scientific Validation"].detail
    assert "scientific_accuracy_claim_allowed" in statuses["Scientific Validation"].detail
    assert statuses["Release Gate"].status == "BLOCKED"
