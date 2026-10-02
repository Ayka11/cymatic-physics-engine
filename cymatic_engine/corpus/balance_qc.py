"""v7.07 Corpus / Speaker Balance QC.

Audits a completed v7.06 680-candidate dataset. This stage does not alter,
repair, synthesize, or re-rank records. It produces an auditable QC report and
is fail-closed for structural/provenance violations.
"""
from __future__ import annotations
import hashlib, json, math, statistics
from collections import Counter
from typing import Any, Mapping, Iterable
from cymatic_engine.alignment.validator import CANONICAL_34_PHONES

SCHEMA = "CPE_CORPUS_BALANCE_QC_v707"
DATASET_SCHEMA = "CPE_680_CANDIDATE_DATASET_v706"

def canonical_json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None, "median": None, "stdev": None}
    return {"n": len(values), "min": min(values), "max": max(values),
            "mean": statistics.fmean(values), "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0}

def _mad_outliers(values: list[float], z: float = 3.5) -> list[int]:
    if len(values) < 7:
        return []
    med = statistics.median(values)
    deviations = [abs(v-med) for v in values]
    mad = statistics.median(deviations)
    if mad == 0:
        return []
    scale = 1.4826 * mad
    return [i for i,v in enumerate(values) if abs(v-med)/scale > z]

def _entropy(counts: Counter[str]) -> float:
    n = sum(counts.values())
    if n == 0: return 0.0
    return -sum((c/n)*math.log(c/n) for c in counts.values())

def audit_dataset(dataset: Mapping[str, Any], *,
                  min_speakers_global: int = 5,
                  max_global_speaker_share: float = 0.40,
                  min_speakers_per_phone: int = 2,
                  max_phone_speaker_share: float = 0.50,
                  min_confidence: float = 0.60) -> dict[str, Any]:
    """Audit a v7.06 PASS dataset without modifying records."""
    base = {"schema": SCHEMA, "status": "BLOCKED"}
    if dataset.get("schema") != DATASET_SCHEMA:
        return {**base, "reason": "wrong_dataset_schema"}
    if dataset.get("status") != "PASS":
        return {**base, "reason": "dataset_not_pass"}
    records = list(dataset.get("records", []))
    if len(records) != 680 or dataset.get("record_count") != 680:
        return {**base, "reason": "record_count_not_680", "record_count": len(records)}
    if dataset.get("dataset_sha256"):
        body = "".join(canonical_json(r)+"\n" for r in records).encode()
        if hashlib.sha256(body).hexdigest() != dataset["dataset_sha256"]:
            return {**base, "reason": "dataset_hash_mismatch"}

    failures=[]
    phone_counts=Counter(str(r.get("phone_normalized")) for r in records)
    speaker_counts=Counter(str(r.get("speaker_id")) for r in records)
    phone_speakers={p:Counter() for p in CANONICAL_34_PHONES}
    durations=[]; confidences=[]
    seen_source=set(); seen_ids=set()
    for i,r in enumerate(records):
        p=str(r.get("phone_normalized")); s=str(r.get("speaker_id"))
        if p not in CANONICAL_34_PHONES: failures.append((i,"unknown_phone"))
        if not s: failures.append((i,"missing_speaker_id"))
        if r.get("candidate_id") in seen_ids: failures.append((i,"duplicate_candidate_id"))
        seen_ids.add(r.get("candidate_id"))
        if r.get("source_key") in seen_source: failures.append((i,"duplicate_source_key"))
        seen_source.add(r.get("source_key"))
        phone_speakers.setdefault(p,Counter())[s]+=1
        try:
            d=int(r["end_sample"])-int(r["start_sample"]); c=float(r["confidence"])
            if d <= 0: failures.append((i,"nonpositive_duration"))
            if not (0 <= c <= 1): failures.append((i,"confidence_out_of_range"))
            if c < min_confidence: failures.append((i,"confidence_below_threshold"))
            durations.append(float(d)); confidences.append(c)
        except (KeyError,TypeError,ValueError):
            failures.append((i,"invalid_numeric_fields"))

    if set(phone_counts) != set(CANONICAL_34_PHONES) or any(phone_counts[p] != 20 for p in CANONICAL_34_PHONES):
        failures.append((-1,"phone_cardinality_violation"))
    if len(speaker_counts) < min_speakers_global:
        failures.append((-1,"insufficient_global_speaker_count"))
    global_share=max(speaker_counts.values())/680 if speaker_counts else 1.0
    if global_share > max_global_speaker_share:
        failures.append((-1,"global_speaker_dominance"))
    per_phone=[]
    for p in CANONICAL_34_PHONES:
        sc=phone_speakers[p]
        if len(sc) < min_speakers_per_phone: failures.append((-1,f"insufficient_speakers:{p}"))
        share=max(sc.values())/20 if sc else 1.0
        if share > max_phone_speaker_share: failures.append((-1,f"phone_speaker_dominance:{p}"))
        per_phone.append({"phone":p,"speaker_count":len(sc),"max_speaker_share":share,"speaker_counts":dict(sc)})

    dur_out=_mad_outliers(durations); conf_out=_mad_outliers(confidences)
    # Outliers are diagnostic, not automatic failure: they require review rather than silent deletion.
    review_required=bool(dur_out or conf_out)
    status="PASS_WITH_REVIEW" if not failures and review_required else ("PASS" if not failures else "BLOCKED")
    return {**base, "status":status, "record_count":680,
            "global": {"speaker_count":len(speaker_counts),"max_speaker_share":global_share,"speaker_entropy":_entropy(speaker_counts)},
            "phone_counts":dict(phone_counts), "speaker_counts":dict(speaker_counts),
            "per_phone":per_phone, "duration_samples":_stats(durations), "confidence":_stats(confidences),
            "diagnostics":{"duration_mad_outlier_indices":dur_out,"confidence_mad_outlier_indices":conf_out,"review_required":review_required},
            "failures":[{"record_index":i,"reason":r} for i,r in failures],
            "policy":{"min_speakers_global":min_speakers_global,"max_global_speaker_share":max_global_speaker_share,
                       "min_speakers_per_phone":min_speakers_per_phone,"max_phone_speaker_share":max_phone_speaker_share,
                       "min_confidence":min_confidence,"outlier_method":"MAD; diagnostic-only"}}
