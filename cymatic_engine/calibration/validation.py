from .models import PhysicalValidationResult
import hashlib
import json
import math


def evaluate_physical_validation(
    level: str,
    metrics: dict[str, float],
    thresholds: dict[str, float],
    warnings=(),
):
    """Evaluate physical validation with strict fail-closed semantics.

    Every threshold key must have a finite metric and finite threshold.
    Missing, non-finite, or empty validation inputs cannot produce PASS.
    """
    metrics = dict(metrics or {})
    thresholds = dict(thresholds or {})

    required = set(thresholds)
    missing = sorted(required - set(metrics))

    invalid = []
    for key in required:
        try:
            metric_value = float(metrics[key])
            threshold_value = float(thresholds[key])
            if not math.isfinite(metric_value) or not math.isfinite(threshold_value):
                invalid.append(key)
        except (KeyError, TypeError, ValueError):
            invalid.append(key)

    if not thresholds:
        passed = False
        eval_warnings = list(warnings) + [
            "No validation thresholds supplied; physical validation is BLOCKED."
        ]
    elif missing:
        passed = False
        eval_warnings = list(warnings) + [
            "Missing required validation metrics: " + ", ".join(missing)
        ]
    elif invalid:
        passed = False
        eval_warnings = list(warnings) + [
            "Non-finite or invalid validation metric/threshold: "
            + ", ".join(sorted(set(invalid)))
        ]
    else:
        passed = all(
            float(metrics[k]) <= float(thresholds[k])
            for k in thresholds
        )
        eval_warnings = list(warnings)

    payload = json.dumps(
        {
            "level": level,
            "metrics": metrics,
            "thresholds": thresholds,
            "passed": passed,
            "warnings": eval_warnings,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    h = hashlib.sha256(payload).hexdigest()

    return PhysicalValidationResult(
        level,
        passed,
        metrics,
        tuple(eval_warnings),
        h,
    )
