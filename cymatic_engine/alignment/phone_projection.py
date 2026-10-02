from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .validator import CANONICAL_34_PHONES, normalize_phone

SCHEMA = "CPE_PHONE_PROJECTION_v712"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def projection_hash(row: Mapping[str, Any]) -> str:
    payload = {k: v for k, v in row.items() if k != "projection_hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CharSpan:
    char_start: int
    char_end: int
    start_sample: int
    end_sample: int
    confidence: float


def _validate_char_spans(spans: Iterable[Mapping[str, Any]]) -> list[CharSpan]:
    out = []
    for i, s in enumerate(spans):
        required = {"char_start", "char_end", "start_sample", "end_sample", "confidence"}
        missing = required - set(s)
        if missing:
            raise ValueError(f"character span {i}: missing {sorted(missing)}")
        c0, c1 = int(s["char_start"]), int(s["char_end"])
        t0, t1 = int(s["start_sample"]), int(s["end_sample"])
        conf = float(s["confidence"])
        if c0 < 0 or c1 <= c0 or t0 < 0 or t1 <= t0:
            raise ValueError(f"character span {i}: invalid interval")
        if not 0.0 <= conf <= 1.0:
            raise ValueError(f"character span {i}: confidence outside [0,1]")
        out.append(CharSpan(c0, c1, t0, t1, conf))
    out.sort(key=lambda x: (x.char_start, x.char_end, x.start_sample, x.end_sample))
    for a, b in zip(out, out[1:]):
        if b.char_start < a.char_end:
            raise ValueError("character spans overlap in transcript space")
        if b.start_sample < a.end_sample:
            raise ValueError("character spans overlap in audio time")
    return out


def project_phone_spans(
    *,
    utterance_id: str,
    speaker_id: str,
    audio_file: str,
    word: str,
    normalized_word: str,
    char_spans: Iterable[Mapping[str, Any]],
    phone_map: Iterable[Mapping[str, Any]],
    source_alignment: Mapping[str, Any],
) -> dict[str, Any]:
    """Project MMS character intervals to phones using an explicit map.

    IMPORTANT: this function does NOT infer grapheme-to-phoneme mappings. The
    phone_map is an auditable external artifact and must explicitly state which
    transcript character span(s) support each phone. Ambiguous or uncovered
    mappings are rejected instead of guessed.
    """
    spans = _validate_char_spans(char_spans)
    mappings = list(phone_map)
    errors: list[str] = []
    phones: list[dict[str, Any]] = []

    if not mappings:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "PHONE_MAP_REQUIRED", "phones": []}

    for i, m in enumerate(mappings):
        for key in ("phone", "source_char_start", "source_char_end"):
            if key not in m:
                errors.append(f"map_{i}:missing_{key}")
        if errors and errors[-1].startswith(f"map_{i}:"):
            continue
        phone = normalize_phone(m["phone"])
        if phone not in CANONICAL_34_PHONES:
            errors.append(f"map_{i}:unknown_phone:{phone}")
            continue
        c0, c1 = int(m["source_char_start"]), int(m["source_char_end"])
        if c0 < 0 or c1 <= c0:
            errors.append(f"map_{i}:invalid_char_span")
            continue
        covered = [s for s in spans if s.char_start >= c0 and s.char_end <= c1]
        if not covered:
            errors.append(f"map_{i}:no_alignment_for_char_span:{c0}:{c1}")
            continue
        start = min(s.start_sample for s in covered)
        end = max(s.end_sample for s in covered)
        confidence = min(s.confidence for s in covered)
        phones.append({
            "utterance_id": utterance_id,
            "speaker_id": speaker_id,
            "audio_file": audio_file,
            "word": word,
            "normalized_word": normalized_word,
            "phone_raw": str(m["phone"]),
            "phone_normalized": phone,
            "source_char_start": c0,
            "source_char_end": c1,
            "start_sample": start,
            "end_sample": end,
            "confidence": confidence,
            "mapping_method": m.get("mapping_method", "external_explicit_map"),
            "mapping_source": m.get("mapping_source", "unspecified"),
            "source_alignment_schema": source_alignment.get("schema", "MMS_FA_ALIGNMENT"),
            "audio_sha256": source_alignment.get("audio_sha256"),
            "transcript_sha256": source_alignment.get("transcript_sha256"),
            "model_id": source_alignment.get("model_id"),
            "model_version": source_alignment.get("model_version"),
        })

    if errors:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "PHONE_MAP_INVALID", "errors": errors, "phones": []}

    phones.sort(key=lambda r: (r["start_sample"], r["end_sample"], r["phone_normalized"]))
    for a, b in zip(phones, phones[1:]):
        if b["start_sample"] < a["end_sample"]:
            return {"schema": SCHEMA, "status": "BLOCKED", "reason": "PROJECTED_PHONE_OVERLAP", "phones": []}

    for row in phones:
        row["projection_hash"] = projection_hash(row)

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "utterance_id": utterance_id,
        "phones": phones,
        "mapping_count": len(mappings),
        "projection_policy": "explicit_mapping_only_no_inference",
    }


def build_explicit_map_record(phone: str, source_char_start: int, source_char_end: int, *, mapping_source: str, mapping_method: str = "external_explicit_map") -> dict[str, Any]:
    """Create a canonical, auditable phone-map record; no inference occurs."""
    p = normalize_phone(phone)
    if p not in CANONICAL_34_PHONES:
        raise ValueError(f"phone is outside canonical 34-phone vocabulary: {phone!r}")
    if source_char_end <= source_char_start:
        raise ValueError("source_char_end must be > source_char_start")
    if not mapping_source:
        raise ValueError("mapping_source is required")
    return {
        "phone": p,
        "source_char_start": int(source_char_start),
        "source_char_end": int(source_char_end),
        "mapping_source": mapping_source,
        "mapping_method": mapping_method,
    }
