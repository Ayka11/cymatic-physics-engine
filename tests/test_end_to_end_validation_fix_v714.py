import hashlib
import json

from cymatic_engine.calibration.models import CalibrationManifest
from cymatic_engine.calibration.validation import evaluate_physical_validation
from cymatic_engine.experiment.end_to_end import build_end_to_end_record
from cymatic_engine.experiment.physical_validation_adapter import (
    build_validated_end_to_end_record,
    calibration_content_hash,
)


def manifest():
    return CalibrationManifest(
        calibration_id="CAL-TEST",
        level="PV0",
        plate_id="PLATE-TEST",
        material={"material": "test"},
        acquisition={"sample_rate_hz": 48000},
        sensor_chain={"sensor": "test"},
        excitation={"type": "test"},
        provenance={"source": "unit-test"},
    )


def test_physical_validation_requires_all_metrics():
    result = evaluate_physical_validation(
        "PV0",
        metrics={"rmse": 0.1},
        thresholds={"rmse": 0.2, "bias": 0.1},
    )
    assert result.passed is False
    assert "bias" in " ".join(result.warnings)


def test_empty_thresholds_fail_closed():
    result = evaluate_physical_validation(
        "PV0",
        metrics={"rmse": 0.1},
        thresholds={},
    )
    assert result.passed is False


def test_nonfinite_values_fail_closed():
    result = evaluate_physical_validation(
        "PV0",
        metrics={"rmse": float("nan")},
        thresholds={"rmse": 0.2},
    )
    assert result.passed is False


def test_end_to_end_accepts_physical_validation_dataclass():
    pv = evaluate_physical_validation(
        "PV0",
        metrics={"rmse": 0.1},
        thresholds={"rmse": 0.2},
    )
    record = build_end_to_end_record(
        source_hash="src",
        calibration_hash="cal",
        pv_result=pv,
    )
    assert record["pv_result"]["passed"] is True
    assert record["evidence_level"] == "E0"
    assert record["claim_guard"]["automatic_e5_promotion"] is False


def test_end_to_end_accepts_mapping():
    record = build_end_to_end_record(
        source_hash="src",
        calibration_hash="cal",
        pv_result={
            "level": "PV0",
            "passed": True,
            "metrics": {"rmse": 0.1},
            "warnings": [],
            "provenance_hash": "pvhash",
        },
    )
    assert record["pv_result"]["passed"] is True
    assert record["evidence_level"] == "E0"


def test_calibration_hash_is_integrated():
    cal = manifest()
    assert calibration_content_hash(cal) == cal.content_hash()

    record = build_validated_end_to_end_record(
        source_hash="src",
        calibration_manifest=cal,
        level="PV0",
        metrics={"rmse": 0.1},
        thresholds={"rmse": 0.2},
    )
    assert record["calibration_hash"] == cal.content_hash()


def test_failed_pv_cannot_be_promoted():
    cal = manifest()
    record = build_validated_end_to_end_record(
        source_hash="src",
        calibration_manifest=cal,
        level="PV0",
        metrics={"rmse": 0.3},
        thresholds={"rmse": 0.2},
        validated_evidence_level="E5",
    )
    assert record["evidence_level"] == "E0"
    assert record["scientific_status"] == "PARTIAL_PHYSICAL_VALIDATION"


def test_explicit_evidence_level_is_required_for_promotion():
    cal = manifest()
    record = build_validated_end_to_end_record(
        source_hash="src",
        calibration_manifest=cal,
        level="PV0",
        metrics={"rmse": 0.1},
        thresholds={"rmse": 0.2},
        validated_evidence_level="E5",
    )
    assert record["evidence_level"] == "E5"
    assert record["scientific_status"] == "PHYSICALLY_VALIDATED"


def test_record_hash_is_deterministic_for_same_record_inputs():
    cal = manifest()
    r1 = build_validated_end_to_end_record(
        source_hash="src",
        calibration_manifest=cal,
        level="PV0",
        metrics={"rmse": 0.1},
        thresholds={"rmse": 0.2},
    )
    r2 = build_validated_end_to_end_record(
        source_hash="src",
        calibration_manifest=cal,
        level="PV0",
        metrics={"rmse": 0.1},
        thresholds={"rmse": 0.2},
    )
    assert r1["record_hash"] == r2["record_hash"]
