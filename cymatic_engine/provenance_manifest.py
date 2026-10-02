"""v7.08 reproducibility and provenance manifest builder.

Creates a deterministic, content-addressed chain for the CPE E2 alignment
pipeline. It never fabricates missing upstream artifacts: absent required
artifacts make the manifest BLOCKED.
"""
from __future__ import annotations
import hashlib, json, platform, sys
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "CPE_REPRODUCIBILITY_MANIFEST_v708"
REQUIRED_ARTIFACTS = {
    "mms_fa_status": "results/MMS_FA_STATUS.json",
    "alignment_validator_status": "results/ALIGNMENT_VALIDATOR_STATUS.json",
    "candidate_qc_status": "results/CANDIDATE_QC_STATUS.json",
    "dataset_builder_status": "results/DATASET_BUILDER_STATUS.json",
    "corpus_balance_qc_status": "results/CORPUS_BALANCE_QC_STATUS.json",
}

def canonical_json(x: Any) -> bytes:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def build_manifest(root: str | Path, *, strict: bool = True) -> dict[str, Any]:
    root=Path(root)
    missing=[]; artifacts={}
    for name, rel in REQUIRED_ARTIFACTS.items():
        p=root/rel
        if not p.is_file(): missing.append(rel); continue
        try: data=load_json(p)
        except Exception as e:
            return {"schema":SCHEMA,"status":"BLOCKED","reason":"invalid_json_artifact","artifact":rel,"error":str(e)}
        artifacts[name]={"path":rel,"sha256":sha256_file(p),"status":data.get("status"),"schema":data.get("schema")}

    # Capture the exact configuration and source files that define the gates.
    tracked=[]
    for p in sorted(root.glob("config/*.json")):
        tracked.append(p)
    for p in sorted(root.glob("cymatic_engine/**/*.py")):
        tracked.append(p)
    source_hashes={str(p.relative_to(root)).replace("\\","/"):sha256_file(p) for p in tracked}

    failures=[]
    statuses={k:v.get("status") for k,v in artifacts.items()}
    if missing: failures.append("missing_required_artifacts")
    if statuses.get("mms_fa_status") == "BLOCKED":
        failures.append("mms_fa_not_executed_or_weights_unavailable")
    # v7.08 is a provenance gate: all upstream statuses must be PASS-like to
    # authorize a reproducible release. PASS_WITH_REVIEW remains review-only.
    for key in ("alignment_validator_status","candidate_qc_status","dataset_builder_status","corpus_balance_qc_status"):
        st=statuses.get(key)
        if st not in {"PASS", "PASS_WITH_REVIEW"}:
            failures.append(f"upstream_not_pass:{key}")

    env={"python":platform.python_version(),"platform":platform.platform(),"implementation":platform.python_implementation()}
    payload={"schema":SCHEMA,"release":"CPE_E2_MASTER_v7.08","artifacts":artifacts,"source_hashes":source_hashes,"environment":env,"fail_closed":True}
    payload["status"]="BLOCKED" if (strict and failures) else ("PASS" if not failures else "BLOCKED")
    payload["failures"]=failures
    payload["chain_sha256"]=sha256_bytes(canonical_json(payload))
    payload["scientific_evidence_level_maximum"]="E1"
    payload["reproducibility_policy"]={
        "content_addressed":True,
        "no_synthetic_artifacts":True,
        "no_missing_artifact_substitution":True,
        "environment_recorded":True,
        "upstream_statuses_required":["PASS","PASS_WITH_REVIEW"],
    }
    return payload
