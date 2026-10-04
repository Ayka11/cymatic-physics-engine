from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_integration_manifest(repo_root: Path, manifest_path: Path) -> list[dict]:
    """Audit declared assets without modifying source files."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        return [{"code": "INVALID_ASSETS_MAP", "path": str(manifest_path)}]

    issues = []
    declared_wav_hashes = defaultdict(list)
    if manifest.get("asset_count") != len(assets):
        issues.append({"code": "ASSET_COUNT_MISMATCH", "declared": manifest.get("asset_count"), "actual": len(assets)})

    for relative_path, expected_hash in assets.items():
        path = repo_root / Path(relative_path)
        expected = str(expected_hash).lower()
        if path.suffix.lower() == ".wav":
            declared_wav_hashes[expected].append(relative_path)
        if not path.is_file():
            issues.append({"code": "MISSING_ASSET", "path": relative_path})
            continue

        actual_hash = sha256_file(path)
        if actual_hash.lower() != expected:
            normalized_match = False
            if path.suffix.lower() == ".json":
                normalized = path.read_bytes().replace(b"\r\n", b"\n")
                normalized_match = hashlib.sha256(normalized).hexdigest().lower() == expected
            if not normalized_match:
                issues.append({"code": "ASSET_HASH_MISMATCH", "path": relative_path, "expected": expected, "actual": actual_hash})

    for digest, paths in declared_wav_hashes.items():
        if len(paths) > 1:
            issues.append({"code": "DUPLICATE_DECLARED_WAV_HASH", "sha256": digest, "paths": sorted(paths)})
    return issues


def audit_letter_audio_manifest(audio_root: Path, csv_path: Path) -> list[dict]:
    """Check file existence and identical audio across distinct IPA labels."""
    issues = []
    by_hash = defaultdict(list)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"ipa_from_atlas", "file"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            return [{"code": "INVALID_LETTER_CSV_SCHEMA", "columns": reader.fieldnames}]

        for row in reader:
            label = (row.get("ipa_from_atlas") or "").strip()
            filename = (row.get("file") or "").strip()
            if not label or not filename:
                issues.append({"code": "INCOMPLETE_LETTER_ROW", "row": row})
                continue
            path = audio_root / filename
            if not path.is_file():
                issues.append({"code": "MISSING_LETTER_AUDIO", "ipa": label, "file": filename})
                continue
            by_hash[sha256_file(path)].append({"ipa": label, "file": filename})

    for digest, rows in by_hash.items():
        if len({row["ipa"] for row in rows}) > 1:
            issues.append({"code": "DUPLICATE_AUDIO_ACROSS_IPA_LABELS", "sha256": digest, "rows": rows})
    return issues


def audit_audio_tree(audio_root: Path) -> list[dict]:
    """Find exact duplicate WAV content across the complete audio tree."""
    audio_root = Path(audio_root).resolve()
    if not audio_root.is_dir():
        return [{"code": "AUDIO_ROOT_NOT_FOUND", "path": str(audio_root)}]

    by_hash = defaultdict(list)
    for path in sorted(audio_root.rglob("*")):
        if path.is_file() and path.suffix.lower() == ".wav":
            by_hash[sha256_file(path)].append(path.relative_to(audio_root).as_posix())

    return [
        {"code": "DUPLICATE_AUDIO_CONTENT", "sha256": digest, "paths": sorted(paths)}
        for digest, paths in by_hash.items() if len(paths) > 1
    ]


def audit_vowel_formant_targets(csv_path: Path) -> list[dict]:
    """Flag identical formant targets assigned to distinct vowel labels."""
    issues = []
    by_targets = defaultdict(list)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"sound", "type", "target_F1_Hz", "target_F2_Hz", "target_F3_Hz"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            return [{"code": "INVALID_FORMANT_TARGETS_SCHEMA", "columns": reader.fieldnames}]

        for row in reader:
            if (row.get("type") or "").strip().lower() != "vowel":
                continue
            label = (row.get("sound") or "").strip()
            try:
                targets = tuple(float(row[key]) for key in ("target_F1_Hz", "target_F2_Hz", "target_F3_Hz"))
            except (TypeError, ValueError):
                issues.append({"code": "INVALID_FORMANT_TARGET", "row": row})
                continue
            if not label or not all(math.isfinite(value) and value > 0 for value in targets):
                issues.append({"code": "INVALID_FORMANT_TARGET", "row": row})
                continue
            by_targets[targets].append(label)

    for targets, labels in by_targets.items():
        unique_labels = sorted(set(labels))
        if len(unique_labels) > 1:
            issues.append({"code": "DUPLICATE_VOWEL_FORMANT_TARGETS", "targets_F1_F2_F3_Hz": targets, "labels": unique_labels})
    return issues


def main() -> int:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "results/HFR09_ATLAS_INTEGRATION_v714.json"
    letter_csv = root / "assets/hfr09/AZ_letter_test_manifest.csv"
    audio_root = root / "assets/hfr09/audio"
    formant_csv = root / "assets/hfr09/vowel_formant_targets.csv"

    issues = []
    issues.extend(audit_integration_manifest(root, manifest_path))
    issues.extend(audit_letter_audio_manifest(audio_root, letter_csv))
    issues.extend(audit_audio_tree(audio_root))
    issues.extend(audit_vowel_formant_targets(formant_csv))

    blocker_codes = {
        "INVALID_ASSETS_MAP", "ASSET_COUNT_MISMATCH", "MISSING_ASSET",
        "ASSET_HASH_MISMATCH", "DUPLICATE_DECLARED_WAV_HASH",
        "INVALID_LETTER_CSV_SCHEMA", "INCOMPLETE_LETTER_ROW",
        "MISSING_LETTER_AUDIO", "DUPLICATE_AUDIO_ACROSS_IPA_LABELS",
        "DUPLICATE_AUDIO_CONTENT", "INVALID_FORMANT_TARGET",
        "INVALID_FORMANT_TARGETS_SCHEMA", "AUDIO_ROOT_NOT_FOUND",
    }
    review_codes = {"DUPLICATE_VOWEL_FORMANT_TARGETS"}
    blockers = [item for item in issues if item["code"] in blocker_codes]
    reviews = [item for item in issues if item["code"] in review_codes]
    unclassified = [item for item in issues if item["code"] not in blocker_codes | review_codes]
    blocked = bool(blockers or unclassified)

    classified_issues = []
    for issue in issues:
        code = issue["code"]
        severity = "BLOCKER" if code in blocker_codes else "REVIEW" if code in review_codes else "UNCLASSIFIED"
        classified_issues.append({**issue, "severity": severity})

    status = "BLOCKED" if blocked else "REVIEW_REQUIRED" if reviews else "PASS"
    print(json.dumps({
        "audit": "HFR09_ASSET_INTEGRITY",
        "status": status,
        "issue_count": len(issues),
        "blocker_detection_count": len(blockers),
        "review_count": len(reviews),
        "unclassified_count": len(unclassified),
        "fail_closed": True,
        "issues": classified_issues,
    }, ensure_ascii=False, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
