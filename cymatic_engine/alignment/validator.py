"""v7.04 Alignment Output Validator.

Fail-closed validation of real MMS-FA output before it can enter the
34-phone / 680-segment candidate-selection stage.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

CANONICAL_34_PHONES = (
    "æ", "ɑ", "ɛ", "ɪ", "i", "ʌ", "ə", "u", "ʊ", "ɔ", "oʊ", "aɪ", "eɪ",
    "p", "b", "t", "d", "k", "g", "f", "v", "s", "z", "ʃ", "ʒ", "θ", "ð", "h",
    "m", "n", "l", "r", "w", "j",
)
PHONE_ALIASES = {
    "sh": "ʃ", "zh": "ʒ", "th": "θ", "dh": "ð",
    "schwa": "ə", "aɪ": "aɪ", "eɪ": "eɪ", "oʊ": "oʊ",
}
REQUIRED_FIELDS = (
    "utterance_id", "speaker_id", "audio_file", "start_sample", "end_sample",
    "phone_raw", "phone_normalized", "confidence",
)
PROVENANCE_FIELDS = (
    "audio_sha256", "transcript_sha256", "model_id", "model_version",
    "alignment_config_hash", "alignment_hash",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _alignment_hash_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k != "alignment_hash"}


def expected_alignment_hash(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_alignment_hash_payload(row)).encode("utf-8")).hexdigest()


def normalize_phone(raw: Any) -> str:
    if raw is None:
        return ""
    p = str(raw).strip().lower()
    # Unicode whitespace/formatting cleanup without changing IPA symbols.
    p = " ".join(p.split())
    return PHONE_ALIASES.get(p, p)


@dataclass(frozen=True)
class WAVInfo:
    sample_rate: int
    n_samples: int

    @property
    def duration_sec(self) -> float:
        return self.n_samples / self.sample_rate


def read_wav_info(path: str | Path) -> WAVInfo:
    import wave
    with wave.open(str(path), "rb") as wf:
        return WAVInfo(sample_rate=wf.getframerate(), n_samples=wf.getnframes())


def _error(code: str, row_index: int, detail: str = "") -> str:
    return f"row_{row_index}:{code}" + (f":{detail}" if detail else "")


def validate_alignment_output(
    rows: Iterable[Mapping[str, Any]],
    *,
    wav_info: Mapping[str, WAVInfo] | None = None,
    min_confidence: float = 0.60,
    require_transcript_sha256: bool = True,
    require_hash_integrity: bool = True,
    require_model_id: str = "MMS_FA",
) -> dict[str, Any]:
    """Validate MMS-FA output. Any error => BLOCKED (fail closed).

    Boundary units are samples. If optional start_sec/end_sec are present,
    they are checked against samples and the WAV sample rate.
    """
    rows = list(rows)
    errors: list[str] = []
    warnings: list[str] = []
    seen_uids: set[str] = set()
    intervals: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    accepted: list[dict[str, Any]] = []

    if not (0.0 <= min_confidence <= 1.0):
        raise ValueError("min_confidence must be in [0,1]")

    for i, original in enumerate(rows):
        r = dict(original)
        missing = [k for k in REQUIRED_FIELDS if k not in r or r[k] in (None, "")]
        if missing:
            errors.append(_error("missing_fields", i, ",".join(missing)))
            continue

        uid = str(r["utterance_id"])
        if uid in seen_uids:
            # Duplicate utterance IDs are allowed only if they represent
            # distinct phones; interval collisions are checked separately.
            pass
        seen_uids.add(uid)

        raw = str(r["phone_raw"])
        normalized = normalize_phone(r["phone_normalized"])
        if not normalized:
            normalized = normalize_phone(raw)
        if normalized not in CANONICAL_34_PHONES:
            errors.append(_error("unknown_phone", i, normalized or raw))

        if normalize_phone(raw) != normalized:
            # phone_normalized must be the deterministic normalization of raw.
            errors.append(_error("phone_normalization_mismatch", i, f"raw={raw!r},normalized={normalized!r}"))

        try:
            start = int(r["start_sample"])
            end = int(r["end_sample"])
        except (TypeError, ValueError):
            errors.append(_error("invalid_sample_boundary", i))
            continue
        if start < 0 or end < 0 or end <= start:
            errors.append(_error("invalid_interval", i, f"{start}:{end}"))

        conf = r["confidence"]
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            errors.append(_error("invalid_confidence", i))
            conf = -1.0
        if not math.isfinite(conf) or not 0.0 <= conf <= 1.0:
            errors.append(_error("confidence_out_of_range", i, str(conf)))
        elif conf < min_confidence:
            errors.append(_error("confidence_below_threshold", i, str(conf)))

        for field in PROVENANCE_FIELDS:
            if field not in r or r[field] in (None, ""):
                errors.append(_error("missing_provenance", i, field))
        if r.get("model_id") != require_model_id:
            errors.append(_error("model_provenance_mismatch", i, str(r.get("model_id"))))

        if require_hash_integrity and r.get("alignment_hash"):
            if r["alignment_hash"] != expected_alignment_hash(r):
                errors.append(_error("alignment_hash_mismatch", i))

        audio_file = r.get("audio_file")
        info = wav_info.get(audio_file) if wav_info else None
        if info:
            if end > info.n_samples:
                errors.append(_error("wav_boundary_violation", i, f"end={end},n_samples={info.n_samples}"))
            if start > info.n_samples:
                errors.append(_error("wav_boundary_violation", i, f"start={start},n_samples={info.n_samples}"))
            if "start_sec" in r:
                try:
                    if not math.isclose(float(r["start_sec"]), start / info.sample_rate, rel_tol=0, abs_tol=1e-6):
                        errors.append(_error("start_sec_mismatch", i))
                except (TypeError, ValueError):
                    errors.append(_error("invalid_start_sec", i))
            if "end_sec" in r:
                try:
                    if not math.isclose(float(r["end_sec"]), end / info.sample_rate, rel_tol=0, abs_tol=1e-6):
                        errors.append(_error("end_sec_mismatch", i))
                except (TypeError, ValueError):
                    errors.append(_error("invalid_end_sec", i))

        intervals[uid].append((start, end, i))
        accepted.append(r)

    # Sort per utterance and reject any positive-length overlap. Touching
    # boundaries (end == next start) are valid.
    for uid, ints in intervals.items():
        ints.sort()
        for prev, cur in zip(ints, ints[1:]):
            if cur[0] < prev[1]:
                errors.append(_error("overlapping_intervals", cur[2], f"utterance_id={uid},prev_row={prev[2]}"))

    # Fail closed on absent WAV metadata when a local WAV is expected.
    if wav_info is not None:
        for i, r in enumerate(rows):
            if r.get("audio_file") not in wav_info:
                errors.append(_error("wav_metadata_missing", i, str(r.get("audio_file"))))

    status = "PASS" if not errors else "BLOCKED"
    return {
        "schema": "CPE_MMS_FA_ALIGNMENT_VALIDATED_v704",
        "status": status,
        "rows_received": len(rows),
        "rows_validated": len(accepted),
        "errors": errors,
        "warnings": warnings,
        "phone_vocabulary": list(CANONICAL_34_PHONES),
        "phone_counts": dict(Counter(r.get("phone_normalized") for r in accepted if r.get("phone_normalized") in CANONICAL_34_PHONES)),
        "min_confidence": min_confidence,
        "fail_closed": True,
        "accepted_rows": accepted if status == "PASS" else [],
    }


def build_680_candidate_pool(validated_rows: Iterable[Mapping[str, Any]], *, per_phone: int = 20) -> dict[str, Any]:
    """Create the deterministic 34 x 20 candidate pool from validated rows.

    The pool is a selection stage, not a second validation stage. Candidates
    are ranked by confidence (descending), then duration (ascending), then
    stable IDs. A slot is populated at most once.
    """
    rows = list(validated_rows)
    if len(CANONICAL_34_PHONES) * per_phone != 680:
        raise ValueError("v7.04 pool must remain 34 x 20 = 680 candidates")
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        p = normalize_phone(r.get("phone_normalized"))
        if p in CANONICAL_34_PHONES:
            groups[p].append(r)

    slots = []
    for phone in CANONICAL_34_PHONES:
        ranked = sorted(
            groups.get(phone, []),
            key=lambda r: (-float(r["confidence"]), int(r["end_sample"]) - int(r["start_sample"]),
                           str(r["utterance_id"]), int(r["start_sample"])),
        )
        for rank, r in enumerate(ranked[:per_phone], start=1):
            slots.append({
                "candidate_id": f"{phone}:{rank:02d}",
                "phone": phone,
                "rank": rank,
                "utterance_id": r["utterance_id"],
                "speaker_id": r["speaker_id"],
                "audio_file": r["audio_file"],
                "start_sample": int(r["start_sample"]),
                "end_sample": int(r["end_sample"]),
                "confidence": float(r["confidence"]),
                "alignment_hash": r["alignment_hash"],
            })
    return {
        "schema": "CPE_CANDIDATE_POOL_34x20_v704",
        "pool_size": len(slots),
        "target_size": 680,
        "complete": len(slots) == 680,
        "slots": slots,
        "missing_per_phone": {p: max(0, per_phone - len(groups.get(p, []))) for p in CANONICAL_34_PHONES},
        "selection_policy": "confidence_desc,duration_asc,stable_id",
    }
