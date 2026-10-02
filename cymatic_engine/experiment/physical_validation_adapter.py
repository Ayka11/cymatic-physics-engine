"""Explicit bridge between calibration validation and end-to-end records.

This module does not invent measurements or thresholds. Real metrics,
thresholds, and calibration provenance must be supplied by the caller.
"""

from __future__ import annotations

from typing import Any, Mapping

from cymatic_engine.calibration.validation import evaluate_physical_validation
from .end_to_end import build_end_to_end_record


def calibration_content_hash(calibration_manifest: Any) -> str:
    """Return the content hash from a CalibrationManifest-like object."""
    method = getattr(calibration_manifest, "content_hash", None)
    if not callable(method):
        raise TypeError("calibration_manifest must provide content_hash()")
    value = method()
    if not value:
        raise ValueError("calibration manifest content hash is empty")
    return str(value)


def build_validated_end_to_end_record(
    *,
    source_hash: str,
    calibration_manifest: Any,
    level: str,
    metrics: Mapping[str, float],
    thresholds: Mapping[str, float],
    warnings=(),
    signature_hash: str | None = None,
    prototype_status: str = "NOT_COMPUTED",
    glyph_status: str = "NOT_COMPUTED",
    extra: dict[str, Any] | None = None,
    validated_evidence_level: str | None = None,
) -> dict[str, Any]:
    """Run the explicit PV gate and construct the end-to-end record.

    No real measurement is created here. If inputs are missing or invalid,
    evaluate_physical_validation() returns a failed result and the end-to-end
    record remains at E0.
    """
    calibration_hash = calibration_content_hash(calibration_manifest)
    pv_result = evaluate_physical_validation(
        level=level,
        metrics=dict(metrics),
        thresholds=dict(thresholds),
        warnings=warnings,
    )
    return build_end_to_end_record(
        source_hash=source_hash,
        calibration_hash=calibration_hash,
        pv_result=pv_result,
        signature_hash=signature_hash,
        prototype_status=prototype_status,
        glyph_status=glyph_status,
        extra=extra,
        validated_evidence_level=validated_evidence_level,
    )


def build_physical_validation_record(
    source_hash: str,
    calibration_hash: str,
    level: str,
    metrics: Mapping[str, float],
    thresholds: Mapping[str, float],
    warnings=(),
) -> dict[str, Any]:
    """Compatibility entry point for the v7.15 research workbench.

    Requires explicit source/calibration hashes and never promotes evidence
    beyond the underlying physical-validation gate.
    """
    if not source_hash or not calibration_hash:
        raise ValueError("source_hash and calibration_hash are required")
    pv_result = evaluate_physical_validation(
        level=level,
        metrics=dict(metrics),
        thresholds=dict(thresholds),
        warnings=warnings,
    )
    return build_end_to_end_record(
        source_hash=str(source_hash),
        calibration_hash=str(calibration_hash),
        pv_result=pv_result,
    )
