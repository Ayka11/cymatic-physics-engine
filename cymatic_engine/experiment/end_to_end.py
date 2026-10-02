from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class EndToEndResult:
    experiment_id: str
    source_hash: str
    calibration_hash: str
    status: str
    evidence_level: str
    stages: tuple[str, ...]
    claim_guard: dict


def _hash_obj(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            obj,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _normalize_physical_validation(pv_result: Any) -> dict[str, Any]:
    """Normalize a PhysicalValidationResult dataclass or mapping.

    The adapter deliberately accepts both forms because persisted/replayed
    validation records are JSON mappings, while in-process validation uses
    the PhysicalValidationResult dataclass.
    """
    if hasattr(pv_result, "passed"):
        level = str(getattr(pv_result, "level"))
        passed = bool(getattr(pv_result, "passed"))
        metrics = dict(getattr(pv_result, "metrics", {}))
        warnings = list(getattr(pv_result, "warnings", ()))
        provenance_hash = str(getattr(pv_result, "provenance_hash", ""))
    elif isinstance(pv_result, Mapping):
        level = str(pv_result.get("level", "UNKNOWN"))
        passed = bool(pv_result.get("passed", False))
        metrics = dict(pv_result.get("metrics", {}))
        warnings = list(pv_result.get("warnings", ()))
        provenance_hash = str(
            pv_result.get("provenance_hash", pv_result.get("validation_hash", ""))
        )
    else:
        raise TypeError(
            "pv_result must be PhysicalValidationResult or a mapping"
        )

    normalized = {
        "level": level,
        "passed": passed,
        "metrics": metrics,
        "warnings": warnings,
        "provenance_hash": provenance_hash,
    }
    return normalized


def build_end_to_end_record(
    source_hash,
    calibration_hash,
    pv_result,
    signature_hash=None,
    prototype_status="NOT_COMPUTED",
    glyph_status="NOT_COMPUTED",
    extra=None,
    validated_evidence_level=None,
):
    """Build a fail-closed end-to-end experiment record.

    A passing physical-validation result does not by itself grant E5.
    Evidence level is E0 unless an explicit, caller-supplied validated level
    is provided. This prevents an infrastructure-level PASS from becoming a
    scientific claim without the required evidence.
    """
    if not source_hash:
        raise ValueError("source_hash is required")
    if not calibration_hash:
        raise ValueError("calibration_hash is required")

    pv = _normalize_physical_validation(pv_result)

    stages = (
        "audio",
        "spectrum",
        "calibration",
        "force",
        "plate",
        "particles",
        "pattern",
        "signature",
        "prototype",
        "glyph",
        "evidence",
    )

    # Fail closed: no automatic promotion to E5.
    if validated_evidence_level is None:
        evidence = "E0"
        status = (
            "PHYSICAL_VALIDATION_PASSED_EVIDENCE_GATE_PENDING"
            if pv["passed"]
            else "PARTIAL_PHYSICAL_VALIDATION"
        )
    else:
        evidence = str(validated_evidence_level)
        if pv["passed"]:
            status = "PHYSICALLY_VALIDATED"
        else:
            # A failed PV result can never be promoted by an evidence-level
            # argument.
            evidence = "E0"
            status = "PARTIAL_PHYSICAL_VALIDATION"

    record = {
        "schema_version": "2.5.0",
        "source_hash": str(source_hash),
        "calibration_hash": str(calibration_hash),
        "pv_result": pv,
        "signature_hash": signature_hash,
        "prototype_status": prototype_status,
        "glyph_status": glyph_status,
        "stages": stages,
        "scientific_status": status,
        "evidence_level": evidence,
        "claim_guard": {
            "real_physical_chain_claim": bool(pv["passed"]),
            "phoneme_identity_claim": False,
            "glyph_identity_claim": False,
            "automatic_e5_promotion": False,
            "reason": (
                "Phoneme/glyph claims require cross-speaker discriminative "
                "evidence and controls; physical validation PASS alone does "
                "not automatically establish E5."
            ),
        },
        "extra": extra or {},
    }
    record["record_hash"] = _hash_obj(record)
    return record


def write_experiment_record(record, path):
    Path(path).write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
