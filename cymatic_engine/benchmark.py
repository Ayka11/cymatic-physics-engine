"""v7.09 Final Benchmark / release gate.

The benchmark validates a *completed* v7.06 dataset plus v7.07 QC and v7.08
provenance manifest. It never fabricates observations. It is deterministic and
fail-closed. Diagnostic metrics are separated from release-gating checks.
"""
from __future__ import annotations
import hashlib, json, math, platform, statistics, sys
from collections import Counter
from typing import Any, Mapping
from cymatic_engine.alignment.validator import CANONICAL_34_PHONES

SCHEMA = "CPE_FINAL_BENCHMARK_v709"
DATASET_SCHEMA = "CPE_680_CANDIDATE_DATASET_v706"
QC_SCHEMA = "CPE_CORPUS_BALANCE_QC_v707"
MANIFEST_SCHEMA = "CPE_REPRODUCIBILITY_MANIFEST_v708"


def canonical_json(x: Any) -> bytes:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def dataset_hash(records: list[Mapping[str, Any]]) -> str:
    body = b"".join(canonical_json(r) + b"\n" for r in records)
    return hashlib.sha256(body).hexdigest()


def _entropy(c: Counter[str]) -> float:
    n = sum(c.values())
    return -sum((v/n)*math.log(v/n) for v in c.values()) if n else 0.0


def benchmark(dataset: Mapping[str, Any], qc: Mapping[str, Any], manifest: Mapping[str, Any], *, deterministic_rerun_hash: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def check(name: str, passed: bool, detail: Any = None):
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    check("dataset_schema", dataset.get("schema") == DATASET_SCHEMA)
    check("dataset_pass", dataset.get("status") == "PASS")
    records = list(dataset.get("records", []))
    check("record_count_680", len(records) == 680, len(records))
    check("dataset_hash_integrity", len(records) == 680 and dataset.get("dataset_sha256") == dataset_hash(records))

    phones = [str(r.get("phone_normalized")) for r in records]
    counts = Counter(phones)
    check("34_phone_coverage", set(counts) == set(CANONICAL_34_PHONES), sorted(set(CANONICAL_34_PHONES)-set(counts)))
    check("20_candidates_per_phone", set(counts) == set(CANONICAL_34_PHONES) and all(counts[p] == 20 for p in CANONICAL_34_PHONES), dict(counts))
    ids = [r.get("candidate_id") for r in records]
    keys = [r.get("source_key") for r in records]
    check("candidate_id_uniqueness", len(ids) == len(set(ids)))
    check("source_key_uniqueness", len(keys) == len(set(keys)))
    ranks_ok = all(sorted(int(r.get("candidate_rank", -1)) for r in records if r.get("phone_normalized") == p) == list(range(1,21)) for p in CANONICAL_34_PHONES)
    check("rank_01_20_per_phone", ranks_ok)

    conf=[]; dur=[]; speakers=Counter(); malformed=0
    for r in records:
        try:
            c=float(r["confidence"]); d=int(r["end_sample"])-int(r["start_sample"])
            if not (0 <= c <= 1) or d <= 0: malformed += 1
            conf.append(c); dur.append(d); speakers[str(r.get("speaker_id"))] += 1
        except Exception:
            malformed += 1
    check("numeric_alignment_fields", malformed == 0, malformed)
    check("confidence_threshold", bool(conf) and min(conf) >= 0.60, min(conf) if conf else None)
    check("global_speaker_cap", bool(speakers) and max(speakers.values())/680 <= 0.40, max(speakers.values())/680 if speakers else None)
    check("speaker_count", len(speakers) >= 5, len(speakers))

    check("corpus_qc_schema", qc.get("schema") == QC_SCHEMA)
    check("corpus_qc_status", qc.get("status") in {"PASS", "PASS_WITH_REVIEW"}, qc.get("status"))
    check("repro_manifest_schema", manifest.get("schema") == MANIFEST_SCHEMA)
    check("repro_manifest_pass", manifest.get("status") == "PASS", manifest.get("status"))
    check("fail_closed_manifest", manifest.get("fail_closed") is True)

    current_hash = dataset.get("dataset_sha256")
    if deterministic_rerun_hash is not None:
        check("deterministic_dataset_hash", current_hash == deterministic_rerun_hash, {"current": current_hash, "rerun": deterministic_rerun_hash})
    else:
        check("deterministic_dataset_hash", False, "rerun_required_not_supplied")

    failures=[c["name"] for c in checks if c["status"] == "FAIL"]
    metrics={
        "confidence": {"min": min(conf) if conf else None, "max": max(conf) if conf else None, "mean": statistics.fmean(conf) if conf else None, "median": statistics.median(conf) if conf else None},
        "duration_samples": {"min": min(dur) if dur else None, "max": max(dur) if dur else None, "mean": statistics.fmean(dur) if dur else None, "median": statistics.median(dur) if dur else None},
        "speaker": {"count": len(speakers), "entropy": _entropy(speakers), "max_share": max(speakers.values())/680 if speakers else None},
    }
    return {
        "schema": SCHEMA,
        "release": "CPE_E2_MASTER_v7.09",
        "status": "PASS" if not failures else "BLOCKED",
        "failures": failures,
        "checks": checks,
        "metrics": metrics,
        "dataset_sha256": current_hash,
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "implementation": platform.python_implementation(), "argv_python": sys.version.split()[0]},
        "release_policy": {"real_mms_fa_only": True, "synthetic_candidates_allowed": False, "manual_candidates_allowed": False, "requires_v708_manifest_pass": True, "requires_deterministic_rerun": True},
        "scientific_evidence_level_maximum": "E1",
    }
