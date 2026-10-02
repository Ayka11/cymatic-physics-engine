"""v7.06 deterministic 680-candidate dataset builder.

Consumes ONLY a v7.05 PASS selection containing exactly 680 real observations.
No synthesis, duplication, repair, re-alignment, or slot fabrication is allowed.
The emitted dataset preserves provenance and is content-addressed by SHA-256.
"""
from __future__ import annotations
import hashlib, json
from collections import Counter
from typing import Any, Mapping, Iterable
from cymatic_engine.alignment.validator import CANONICAL_34_PHONES

SCHEMA = "CPE_680_CANDIDATE_DATASET_v706"
REQUIRED = ("candidate_id","candidate_rank","phone_normalized","utterance_id","speaker_id","audio_file","start_sample","end_sample","confidence","alignment_hash","audio_sha256","transcript_sha256","model_id","model_version","alignment_config_hash","source_key")

def canonical_json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def normalize_slot(r: Mapping[str, Any]) -> dict[str, Any]:
    missing=[k for k in REQUIRED if k not in r or r[k] in (None, "")]
    if missing: raise ValueError("missing_required_fields:"+",".join(missing))
    return {
      "candidate_id": str(r["candidate_id"]), "candidate_rank": int(r["candidate_rank"]),
      "phone_normalized": str(r["phone_normalized"]), "utterance_id": str(r["utterance_id"]),
      "speaker_id": str(r["speaker_id"]), "audio_file": str(r["audio_file"]),
      "start_sample": int(r["start_sample"]), "end_sample": int(r["end_sample"]),
      "confidence": float(r["confidence"]), "alignment_hash": str(r["alignment_hash"]),
      "audio_sha256": str(r["audio_sha256"]), "transcript_sha256": str(r["transcript_sha256"]),
      "model_id": str(r["model_id"]), "model_version": str(r["model_version"]),
      "alignment_config_hash": str(r["alignment_config_hash"]), "source_key": str(r["source_key"]),
    }

def build_dataset(selection: Mapping[str, Any], *, expected_per_phone: int=20) -> dict[str, Any]:
    if selection.get("schema") != "CPE_CANDIDATE_SELECTION_v705":
        return {"schema":SCHEMA,"status":"BLOCKED","reason":"wrong_selection_schema"}
    if selection.get("status") != "PASS" or not selection.get("complete"):
        return {"schema":SCHEMA,"status":"BLOCKED","reason":"selection_not_complete_pass"}
    slots=list(selection.get("slots", []))
    if len(slots) != 680 or selection.get("selected_size") != 680:
        return {"schema":SCHEMA,"status":"BLOCKED","reason":"selection_size_not_680","received":len(slots)}
    try: rows=[normalize_slot(r) for r in slots]
    except ValueError as e: return {"schema":SCHEMA,"status":"BLOCKED","reason":str(e)}
    ids=[r["candidate_id"] for r in rows]
    if len(set(ids)) != 680: return {"schema":SCHEMA,"status":"BLOCKED","reason":"duplicate_candidate_id"}
    counts=Counter(r["phone_normalized"] for r in rows)
    if set(counts) != set(CANONICAL_34_PHONES) or any(counts[p] != expected_per_phone for p in CANONICAL_34_PHONES):
        return {"schema":SCHEMA,"status":"BLOCKED","reason":"phone_cardinality_violation","phone_counts":dict(counts)}
    for p in CANONICAL_34_PHONES:
        ranks=sorted(r["candidate_rank"] for r in rows if r["phone_normalized"]==p)
        if ranks != list(range(1,expected_per_phone+1)):
            return {"schema":SCHEMA,"status":"BLOCKED","reason":"rank_sequence_violation","phone":p}
    # Enforce no duplicate source observation inside final dataset.
    keys=[r["source_key"] for r in rows]
    if len(set(keys)) != len(keys): return {"schema":SCHEMA,"status":"BLOCKED","reason":"duplicate_source_key"}
    rows.sort(key=lambda r:(CANONICAL_34_PHONES.index(r["phone_normalized"]),r["candidate_rank"]))
    body="".join(canonical_json(r)+"\n" for r in rows).encode("utf-8")
    dataset_sha256=hashlib.sha256(body).hexdigest()
    manifest={"schema":SCHEMA,"status":"PASS","dataset_sha256":dataset_sha256,"record_count":680,"phones":list(CANONICAL_34_PHONES),"per_phone":expected_per_phone,"source_schema":selection.get("schema"),"provenance_policy":"real_MMS_FA_only; no_synthetic_or_duplicate_observations"}
    return {"schema":SCHEMA,"status":"PASS","record_count":680,"dataset_sha256":dataset_sha256,"manifest":manifest,"records":rows,"phone_counts":dict(counts)}
