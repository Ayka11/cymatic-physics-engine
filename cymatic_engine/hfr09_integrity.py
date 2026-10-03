from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_integration_manifest(
    repo_root: Path,
    manifest_path: Path,
) -> list[dict]:
    """Audit declared assets without modifying source files."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assets = manifest.get("assets")

    if not isinstance(assets, dict):
        return [{"code": "INVALID_ASSETS_MAP", "path": str(manifest_path)}]

    issues = []
    declared_wav_hashes = defaultdict(list)

    if manifest.get("asset_count") != len(assets):
        issues.append({
            "code": "ASSET_COUNT_MISMATCH",
            "declared": manifest.get("asset_count"),
            "actual": len(assets),
        })

    for relative_path, expected_hash in assets.items():
        path = repo_root / Path(relative_path)
        expected = str(expected_hash).lower()

        # Audit declared WAV hashes even when a declared file is missing.
        if path.suffix.lower() == ".wav":
            declared_wav_hashes[expected].append(relative_path)

        if not path.is_file():
            issues.append({
                "code": "MISSING_ASSET",
                "path": relative_path,
            })
            continue

        actual_hash = sha256_file(path)
        expected = str(expected_hash).lower()

        if actual_hash.lower() != expected:
            normalized_match = False

            # Permit only CRLF/LF representation differences in JSON.
            if path.suffix.lower() == ".json":
                normalized = path.read_bytes().replace(b"\r\n", b"\n")
                normalized_hash = hashlib.sha256(normalized).hexdigest()
                normalized_match = normalized_hash.lower() == expected

            if not normalized_match:
                issues.append({
                    "code": "ASSET_HASH_MISMATCH",
                    "path": relative_path,
                    "expected": expected,
                    "actual": actual_hash,
                })

    # A duplicate declared hash is a review blocker, even if one file is missing.
    for digest, paths in declared_wav_hashes.items():
        if len(paths) > 1:
            issues.append({
                "code": "DUPLICATE_DECLARED_WAV_HASH",
                "sha256": digest,
                "paths": sorted(paths),
            })

    return issues


def audit_letter_audio_manifest(
    audio_root: Path,
    csv_path: Path,
) -> list[dict]:
    """Check file existence and identical audio across distinct IPA labels."""
    issues = []
    by_hash = defaultdict(list)

    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"ipa_from_atlas", "file"}

        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            return [{
                "code": "INVALID_LETTER_CSV_SCHEMA",
                "columns": reader.fieldnames,
            }]

        for row in reader:
            label = (row.get("ipa_from_atlas") or "").strip()
            filename = (row.get("file") or "").strip()

            if not label or not filename:
                issues.append({
                    "code": "INCOMPLETE_LETTER_ROW",
                    "row": row,
                })
                continue

            path = audio_root / filename
            if not path.is_file():
                issues.append({
                    "code": "MISSING_LETTER_AUDIO",
                    "ipa": label,
                    "file": filename,
                })
                continue

            by_hash[sha256_file(path)].append({
                "ipa": label,
                "file": filename,
            })

    for digest, rows in by_hash.items():
        labels = {row["ipa"] for row in rows}
        if len(labels) > 1:
            issues.append({
                "code": "DUPLICATE_AUDIO_ACROSS_IPA_LABELS",
                "sha256": digest,
                "rows": rows,
            })

    return issues


def main() -> int:
    # Keep IPA symbols printable in Windows consoles using legacy encodings.
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    root = Path(__file__).resolve().parents[1]

    manifest_path = root / "results/HFR09_ATLAS_INTEGRATION_v714.json"
    letter_csv = root / "assets/hfr09/AZ_letter_test_manifest.csv"
    audio_root = root / "assets/hfr09/audio"

    issues = []
    issues.extend(audit_integration_manifest(root, manifest_path))
    issues.extend(audit_letter_audio_manifest(audio_root, letter_csv))

    print(json.dumps({
        "audit": "HFR09_ASSET_INTEGRITY",
        "issue_count": len(issues),
        "status": "PASS" if not issues else "BLOCKED",
        "issues": issues,
        "fail_closed": True,
    }, ensure_ascii=False, indent=2))

    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
