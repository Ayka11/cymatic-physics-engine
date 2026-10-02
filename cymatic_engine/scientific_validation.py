"""v7.14 Scientific Validation / Release Freeze gate.

This module distinguishes software/reproducibility validation from scientific
claims. It cannot declare phoneme alignment scientifically accurate without an
independent reference annotation. The release gate is therefore fail-closed.
"""
from __future__ import annotations
import hashlib, json, math, platform, statistics, sys
from collections import Counter
from typing import Any, Mapping, Sequence
from cymatic_engine.alignment.validator import CANONICAL_34_PHONES

SCHEMA = "CPE_SCIENTIFIC_VALIDATION_v714"

def canonical_json(x: Any) -> bytes:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

def sha256_json(x: Any) -> str:
    return hashlib.sha256(canonical_json(x)).hexdigest()

def _percentile(xs: Sequence[float], q: float) -> float | None:
    if not xs: return None
    a = sorted(xs); pos = (len(a)-1)*q; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    return a[lo] if lo == hi else a[lo] + (a[hi]-a[lo])*(pos-lo)

def _bootstrap_mean_ci(xs: Sequence[float], seed: int = 714, n: int = 1000) -> dict[str, float | None]:
    # Deterministic lightweight bootstrap using an LCG; no external dependency.
    if not xs: return {"mean": None, "ci95_low": None, "ci95_high": None}
    state = seed & 0xFFFFFFFF
    means=[]; m=len(xs)
    for _ in range(n):
        total=0.0
        for _ in range(m):
            state=(1664525*state+1013904223)&0xFFFFFFFF
            total += xs[state % m]
        means.append(total/m)
    return {"mean": statistics.fmean(xs), "ci95_low": _percentile(means, .025), "ci95_high": _percentile(means, .975)}

def validate_science(dataset: Mapping[str, Any], qc: Mapping[str, Any], manifest: Mapping[str, Any], benchmark: Mapping[str, Any], *, independent_reference_present: bool = False, rerun_hash: str | None = None) -> dict[str, Any]:
    failures=[]; warnings=[]; checks=[]
    def check(name, passed, detail=None, hard=True):
        item={"name":name,"status":"PASS" if passed else ("FAIL" if hard else "REVIEW"),"detail":detail}
        checks.append(item)
        if not passed:
            (failures if hard else warnings).append(name)
    records=list(dataset.get("records", []))
    conf=[]; durations=[]; speakers=Counter(); phones=Counter()
    for r in records:
        try:
            conf.append(float(r["confidence"])); durations.append(int(r["end_sample"])-int(r["start_sample"]))
            speakers[str(r.get("speaker_id"))]+=1; phones[str(r.get("phone_normalized"))]+=1
        except Exception: failures.append("malformed_record")
    check("benchmark_pass", benchmark.get("status")=="PASS", benchmark.get("status"))
    check("dataset_680", len(records)==680, len(records))
    check("34_phone_complete", set(phones)==set(CANONICAL_34_PHONES) and all(phones[p]==20 for p in CANONICAL_34_PHONES), dict(phones))
    check("confidence_floor", bool(conf) and min(conf)>=.60, min(conf) if conf else None)
    check("positive_durations", bool(durations) and min(durations)>0, min(durations) if durations else None)
    check("speaker_minimum", len(speakers)>=5, len(speakers))
    check("provenance_manifest_pass", manifest.get("status")=="PASS", manifest.get("status"))
    check("deterministic_rerun", rerun_hash is not None and dataset.get("dataset_sha256")==rerun_hash, {"dataset":dataset.get("dataset_sha256"),"rerun":rerun_hash})
    # Scientific validity cannot be inferred from internal QC alone.
    check("independent_reference_alignment", independent_reference_present, "No independent human/reference alignment supplied", hard=False)
    check("real_mms_fa_evidence", dataset.get("real_mms_fa_execution_performed", False) is True, "Dataset metadata does not prove a real MMS-FA run", hard=False)
    if conf:
        conf_stats={"min":min(conf),"p25":_percentile(conf,.25),"median":statistics.median(conf),"p75":_percentile(conf,.75),"max":max(conf),"mean":statistics.fmean(conf),"bootstrap_mean_95":_bootstrap_mean_ci(conf)}
    else: conf_stats={"min":None}
    dur_stats={"min":min(durations) if durations else None,"p25":_percentile(durations,.25),"median":statistics.median(durations) if durations else None,"p75":_percentile(durations,.75),"max":max(durations) if durations else None}
    evidence = "E2_candidate_dataset_validated" if not failures and dataset.get("real_mms_fa_execution_performed") else "E1_pipeline_validated_only"
    return {
        "schema":SCHEMA,"version":"v7.14","status":"PASS" if not failures and not warnings else ("PASS_WITH_REVIEW" if not failures else "BLOCKED"),
        "failures":sorted(set(failures)),"review_items":sorted(set(warnings)),"checks":checks,
        "metrics":{"n":len(records),"phones":dict(phones),"speakers":{"count":len(speakers),"max":max(speakers.values()) if speakers else None},"confidence":conf_stats,"duration_samples":dur_stats},
        "scientific_interpretation":{"independent_reference_present":independent_reference_present,"claim_boundary":"Internal QC and reproducibility do not establish phoneme-boundary accuracy; an independent reference annotation is required for accuracy claims.","evidence_level":evidence},
        "release_freeze":{"frozen":not failures and independent_reference_present,"requires_real_mms_fa":True,"requires_independent_reference_for_scientific_accuracy_claims":True,"synthetic_allowed":False,"manual_allowed":False},
        "environment":{"python":platform.python_version(),"platform":platform.platform(),"argv_python":sys.version.split()[0]},
        "input_hash":sha256_json({"dataset":dataset.get("dataset_sha256"),"benchmark":benchmark.get("dataset_sha256"),"manifest":manifest.get("manifest_hash")}),
    }
