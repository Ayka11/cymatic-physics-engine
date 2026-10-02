"""v7.05 Candidate QC and deterministic selection.

Consumes ONLY v7.04 PASS rows. It never repairs, invents, or re-aligns data.
Rows failing candidate-level QC are excluded with an auditable reason.
Selection is deterministic and preserves MMS-FA provenance.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

from cymatic_engine.alignment.validator import CANONICAL_34_PHONES, normalize_phone

SCHEMA = "CPE_CANDIDATE_QC_v705"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def candidate_source_key(row: Mapping[str, Any]) -> str:
    """Stable source identity used to prevent duplicate candidate observations."""
    payload = {
        "audio_sha256": row.get("audio_sha256"),
        "audio_file": row.get("audio_file"),
        "utterance_id": row.get("utterance_id"),
        "start_sample": int(row["start_sample"]),
        "end_sample": int(row["end_sample"]),
        "phone": normalize_phone(row.get("phone_normalized")),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def candidate_id(phone: str, rank: int) -> str:
    return f"{phone}:{rank:02d}"


def _duration_samples(row: Mapping[str, Any]) -> int:
    return int(row["end_sample"]) - int(row["start_sample"])


def _qc_reasons(row: Mapping[str, Any], *, min_confidence: float,
                min_duration_samples: int, max_duration_samples: int | None) -> list[str]:
    reasons: list[str] = []
    phone = normalize_phone(row.get("phone_normalized"))
    if phone not in CANONICAL_34_PHONES:
        reasons.append("unknown_phone")
    try:
        confidence = float(row["confidence"])
    except (KeyError, TypeError, ValueError):
        confidence = float("nan")
    if not math.isfinite(confidence) or confidence < min_confidence:
        reasons.append("confidence_qc")
    duration = _duration_samples(row)
    if duration < min_duration_samples:
        reasons.append("duration_too_short")
    if max_duration_samples is not None and duration > max_duration_samples:
        reasons.append("duration_too_long")
    for field in ("audio_sha256", "transcript_sha256", "model_id", "model_version", "alignment_config_hash", "alignment_hash"):
        if not row.get(field):
            reasons.append("missing_provenance:" + field)
    if row.get("model_id") != "MMS_FA":
        reasons.append("model_provenance_mismatch")
    return reasons


def qc_candidates(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_validation_status: str,
    min_confidence: float = 0.60,
    min_duration_samples: int = 160,
    max_duration_samples: int | None = 16000,
) -> dict[str, Any]:
    """Run candidate-level QC. Non-PASS upstream status is a hard stop."""
    rows = [dict(r) for r in rows]
    if source_validation_status != "PASS":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "upstream_alignment_validation_not_pass",
            "rows_received": len(rows),
            "eligible_rows": [],
            "rejections": [],
        }
    if not (0 <= min_confidence <= 1):
        raise ValueError("min_confidence must be in [0,1]")
    if min_duration_samples < 1:
        raise ValueError("min_duration_samples must be >= 1")
    if max_duration_samples is not None and max_duration_samples < min_duration_samples:
        raise ValueError("max_duration_samples must be >= min_duration_samples")

    eligible: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for i, row in enumerate(rows):
        reasons = _qc_reasons(row, min_confidence=min_confidence,
                              min_duration_samples=min_duration_samples,
                              max_duration_samples=max_duration_samples)
        key = candidate_source_key(row) if not reasons else None
        if key and key in seen_keys:
            reasons.append("duplicate_source_observation")
        if reasons:
            rejections.append({"row_index": i, "utterance_id": row.get("utterance_id"), "reasons": reasons})
            continue
        seen_keys.add(key)  # type: ignore[arg-type]
        row["phone_normalized"] = normalize_phone(row["phone_normalized"])
        row["duration_samples"] = _duration_samples(row)
        row["source_key"] = key
        eligible.append(row)

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "rows_received": len(rows),
        "eligible_count": len(eligible),
        "eligible_rows": eligible,
        "rejections": rejections,
        "rejection_counts": dict(Counter(reason for r in rejections for reason in r["reasons"])),
        "config": {
            "min_confidence": min_confidence,
            "min_duration_samples": min_duration_samples,
            "max_duration_samples": max_duration_samples,
        },
    }


def select_680(
    qc_result: Mapping[str, Any],
    *,
    per_phone: int = 20,
    max_candidates_per_speaker_per_phone: int | None = 4,
    require_speaker_diversity: bool = True,
) -> dict[str, Any]:
    """Select up to 20 candidates per canonical phone, deterministically.

    The first pass enforces speaker diversity where possible; a second pass
    fills remaining slots while respecting the configured per-speaker cap.
    No row is duplicated and no synthetic slot is created.
    """
    if qc_result.get("status") != "PASS":
        return {"schema": "CPE_CANDIDATE_SELECTION_v705", "status": "BLOCKED", "reason": "candidate_qc_not_pass"}
    if per_phone != 20:
        raise ValueError("v7.05 fixed target is 20 candidates per phone")
    if max_candidates_per_speaker_per_phone is not None and max_candidates_per_speaker_per_phone < 1:
        raise ValueError("speaker cap must be >= 1 or None")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in qc_result.get("eligible_rows", []):
        p = normalize_phone(row.get("phone_normalized"))
        if p in CANONICAL_34_PHONES:
            groups[p].append(dict(row))

    def rank_key(r: Mapping[str, Any]):
        return (-float(r["confidence"]), int(r["duration_samples"]),
                str(r.get("speaker_id", "")), str(r["utterance_id"]),
                int(r["start_sample"]), str(r["alignment_hash"]))

    selected: list[dict[str, Any]] = []
    missing: dict[str, int] = {}
    speaker_counts: dict[str, Counter[str]] = {}

    for phone in CANONICAL_34_PHONES:
        ranked = sorted(groups.get(phone, []), key=rank_key)
        chosen: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        remaining = list(ranked)

        if require_speaker_diversity:
            # Round-robin over speakers gives different speakers an opportunity
            # before additional high-confidence observations from one speaker.
            by_speaker: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in ranked:
                by_speaker[str(r.get("speaker_id", ""))].append(r)
            for speaker in sorted(by_speaker):
                if len(chosen) >= per_phone:
                    break
                r = by_speaker[speaker][0]
                if max_candidates_per_speaker_per_phone is None or counts[speaker] < max_candidates_per_speaker_per_phone:
                    chosen.append(r); counts[speaker] += 1
            chosen_keys = {r["source_key"] for r in chosen}
            remaining = [r for r in ranked if r["source_key"] not in chosen_keys]

        for r in remaining:
            if len(chosen) >= per_phone:
                break
            speaker = str(r.get("speaker_id", ""))
            if max_candidates_per_speaker_per_phone is not None and counts[speaker] >= max_candidates_per_speaker_per_phone:
                continue
            chosen.append(r)
            counts[speaker] += 1

        # Stable final order is by quality after diversity has been applied.
        chosen.sort(key=rank_key)
        for rank, r in enumerate(chosen, start=1):
            out = dict(r)
            out["candidate_id"] = candidate_id(phone, rank)
            out["candidate_rank"] = rank
            selected.append(out)
        missing[phone] = max(0, per_phone - len(chosen))
        speaker_counts[phone] = counts

    complete = all(v == 0 for v in missing.values())
    status = "PASS" if complete else "INCOMPLETE"
    return {
        "schema": "CPE_CANDIDATE_SELECTION_v705",
        "status": status,
        "target_size": len(CANONICAL_34_PHONES) * per_phone,
        "selected_size": len(selected),
        "complete": complete,
        "slots": selected,
        "missing_per_phone": missing,
        "speaker_counts_per_phone": {p: dict(c) for p, c in speaker_counts.items()},
        "policy": {
            "per_phone": per_phone,
            "max_candidates_per_speaker_per_phone": max_candidates_per_speaker_per_phone,
            "require_speaker_diversity": require_speaker_diversity,
            "ranking": "confidence_desc,duration_asc,speaker_id,utterance_id,start_sample,alignment_hash",
        },
    }
