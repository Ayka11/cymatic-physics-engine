"""v7.08 reproducibility and provenance manifest builder.

Creates a deterministic, content-addressed chain for the CPE E2 alignment
pipeline. It never fabricates missing upstream artifacts: absent required
artifacts make the manifest BLOCKED.
"""
from __future__ import annotations
import hashlib, json, platform, re, sys
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
        try:
            data = load_json(p)
        except Exception as e:
            return {"schema": SCHEMA, "status": "BLOCKED", "reason": "invalid_json_artifact", "artifact": rel, "error": str(e)}
        if not isinstance(data, Mapping):
            return {"schema": SCHEMA, "status": "BLOCKED", "reason": "json_root_not_object", "artifact": rel}
        artifacts[name] = {"path": rel, "sha256": sha256_file(p), "status": data.get("status"), "schema": data.get("schema")}

    # Capture the exact configuration and source files that define the gates.
    tracked=[]
    for p in sorted(root.glob("config/*.json")):
        tracked.append(p)
    for p in sorted(root.glob("cymatic_engine/**/*.py")):
        tracked.append(p)

    source_hashes = {str(p.relative_to(root)).replace("\\", "/"): sha256_file(p) for p in tracked}
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

def verify_manifest_integrity(root: str | Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Verify the recorded files and chain digest; never infer validity from status labels."""
    root = Path(root).resolve()
    issues: list[str] = []

    def verify_recorded_file(label: str, rel_path: Any, expected_hash: Any) -> None:
        if not isinstance(rel_path, str) or not rel_path:
            issues.append(f"{label}:missing_path")
            return
        candidate = (root / rel_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            issues.append(f"{label}:path_outside_root")
            return
        if not candidate.is_file():
            issues.append(f"{label}:file_missing")
            return
        if not isinstance(expected_hash, str) or re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash) is None:
            issues.append(f"{label}:invalid_expected_sha256")
            return
        actual = sha256_file(candidate)
        if actual.lower() != expected_hash.lower():
            issues.append(f"{label}:sha256_mismatch")
        if label.startswith("artifact:"):
            try:
                parsed = load_json(candidate)
            except Exception:
                issues.append(f"{label}:invalid_json")
            else:
                record_key = label.split(":", 1)[1]
                record = artifacts.get(record_key) if isinstance(artifacts, Mapping) else None
                if not isinstance(parsed, Mapping):
                    issues.append(f"{label}:json_root_not_object")
                elif isinstance(record, Mapping):
                    if parsed.get("status") != record.get("status"):
                        issues.append(f"{label}:status_mismatch")
                    if parsed.get("schema") != record.get("schema"):
                        issues.append(f"{label}:schema_mismatch")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping) or not artifacts:
        issues.append("artifacts:missing_or_invalid")
    else:
        for key, rel_path in REQUIRED_ARTIFACTS.items():
            record = artifacts.get(key)
            if not isinstance(record, Mapping):
                issues.append(f"artifact:{key}:required_record_missing")
                continue
            if record.get("path") != rel_path:
                issues.append(f"artifact:{key}:required_path_mismatch")
            verify_recorded_file(f"artifact:{key}", record.get("path"), record.get("sha256"))
        for key, record in artifacts.items():
            if key not in REQUIRED_ARTIFACTS:
                if not isinstance(record, Mapping):
                    issues.append(f"artifact:{key}:invalid_record")
                    continue
                verify_recorded_file(f"artifact:{key}", record.get("path"), record.get("sha256"))

    source_hashes = manifest.get("source_hashes")
    expected_sources = {
        str(p.relative_to(root)).replace("\\", "/")
        for pattern in ("config/*.json", "cymatic_engine/**/*.py")
        for p in root.glob(pattern)
        if p.is_file()
    }
    if not isinstance(source_hashes, Mapping) or not source_hashes:
        issues.append("source_hashes:missing_or_invalid")
    else:
        recorded_sources = set(source_hashes)
        for rel_path in sorted(expected_sources - recorded_sources):
            issues.append(f"source:{rel_path}:record_missing")
        for rel_path in sorted(recorded_sources - expected_sources):
            issues.append(f"source:{rel_path}:untracked_or_missing")
        for rel_path, expected_hash in source_hashes.items():
            verify_recorded_file(f"source:{rel_path}", rel_path, expected_hash)

    expected_chain = manifest.get("chain_sha256")
    if not isinstance(expected_chain, str) or re.fullmatch(r"[0-9a-fA-F]{64}", expected_chain) is None:
        issues.append("chain_sha256:missing_or_invalid")
    else:
        # build_manifest computes the chain before appending these two metadata fields.
        chain_payload = dict(manifest)
        chain_payload.pop("chain_sha256", None)
        chain_payload.pop("scientific_evidence_level_maximum", None)
        chain_payload.pop("reproducibility_policy", None)
        actual_chain = sha256_bytes(canonical_json(chain_payload))
        if actual_chain.lower() != expected_chain.lower():
            issues.append("chain_sha256:mismatch")

    return {
        "valid": not issues,
        "status": "PASS" if not issues else "BLOCKED",
        "issues": issues,
    }

def main(argv: list[str] | None = None) -> int:
    """Build and verify the current manifest without promoting blocked evidence."""
    import argparse

    parser = argparse.ArgumentParser(description="Build the CPE v7.08 reproducibility manifest.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the root containing this package).",
    )
    parser.add_argument(
        "--output",
        default="results/REPRODUCIBILITY_MANIFEST_v708.json",
        help="Output path, absolute or relative to --root.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output

    manifest = build_manifest(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
    )
    integrity = verify_manifest_integrity(root, manifest)

    print(f"manifest_status={manifest.get('status', 'BLOCKED')}")
    print(f"integrity_status={integrity['status']}")
    print(f"manifest_path={output}")
    for failure in manifest.get("failures", []):
        print(f"evidence_failure={failure}")
    for issue in integrity["issues"]:
        print(f"integrity_issue={issue}")

    # Exit status describes whether the manifest is internally verifiable.
    # Scientific readiness remains explicit in manifest_status and is never
    # promoted by a successful file-generation operation.
    return 0 if integrity["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
