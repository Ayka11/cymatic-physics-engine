from __future__ import annotations

import json
from pathlib import Path

from cymatic_engine.provenance_manifest import (
    canonical_json,
    sha256_bytes,
    sha256_file,
    verify_manifest_integrity,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _valid_manifest(root: Path) -> dict:
    artifact_path = root / "results" / "sample.json"
    source_path = root / "config" / "sample.json"
    _write_json(artifact_path, {"status": "PASS", "schema": "sample-v1"})
    _write_json(source_path, {"enabled": True})
    payload = {
        "schema": "CPE_REPRODUCIBILITY_MANIFEST_v708",
        "release": "test",
        "artifacts": {
            "sample": {
                "path": "results/sample.json",
                "sha256": sha256_file(artifact_path),
                "status": "PASS",
                "schema": "sample-v1",
            }
        },
        "source_hashes": {"config/sample.json": sha256_file(source_path)},
        "environment": {"python": "3.x"},
        "fail_closed": True,
        "status": "PASS",
        "failures": [],
    }
    payload["chain_sha256"] = sha256_bytes(canonical_json(payload))
    payload["scientific_evidence_level_maximum"] = "E1"
    payload["reproducibility_policy"] = {"content_addressed": True}
    return payload


def test_manifest_integrity_accepts_matching_files_and_chain(tmp_path: Path):
    manifest = _valid_manifest(tmp_path)
    result = verify_manifest_integrity(tmp_path, manifest)
    assert result == {"valid": True, "status": "PASS", "issues": []}


def test_manifest_integrity_detects_changed_artifact(tmp_path: Path):
    manifest = _valid_manifest(tmp_path)
    _write_json(tmp_path / "results" / "sample.json", {"status": "PASS", "schema": "sample-v1", "changed": True})
    result = verify_manifest_integrity(tmp_path, manifest)
    assert result["valid"] is False
    assert "artifact:sample:sha256_mismatch" in result["issues"]


def test_manifest_integrity_detects_changed_source(tmp_path: Path):
    manifest = _valid_manifest(tmp_path)
    _write_json(tmp_path / "config" / "sample.json", {"enabled": False})
    result = verify_manifest_integrity(tmp_path, manifest)
    assert result["valid"] is False
    assert "source:config/sample.json:sha256_mismatch" in result["issues"]


def test_manifest_integrity_detects_tampered_chain(tmp_path: Path):
    manifest = _valid_manifest(tmp_path)
    manifest["status"] = "PASS_WITH_REVIEW"
    result = verify_manifest_integrity(tmp_path, manifest)
    assert result["valid"] is False
    assert "chain_sha256:mismatch" in result["issues"]


def test_manifest_integrity_rejects_paths_outside_root(tmp_path: Path):
    manifest = _valid_manifest(tmp_path)
    manifest["source_hashes"] = {"../outside.txt": "0" * 64}
    # Recompute the chain so the path traversal check is tested independently.
    chain_payload = dict(manifest)
    chain_payload.pop("chain_sha256", None)
    chain_payload.pop("scientific_evidence_level_maximum", None)
    chain_payload.pop("reproducibility_policy", None)
    manifest["chain_sha256"] = sha256_bytes(canonical_json(chain_payload))
    result = verify_manifest_integrity(tmp_path, manifest)
    assert result["valid"] is False
    assert "source:../outside.txt:path_outside_root" in result["issues"]
