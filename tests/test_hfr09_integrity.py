import csv
import hashlib
import json
from pathlib import Path

from cymatic_engine.hfr09_integrity import (
    audit_audio_tree,
    audit_integration_manifest,
    audit_letter_audio_manifest,
    audit_vowel_formant_targets,
)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_letter_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["letter", "ipa_from_atlas", "file"]
        )
        writer.writeheader()
        writer.writerows(rows)


def test_detects_identical_audio_for_distinct_ipa_labels(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "M.wav").write_bytes(b"same-audio")
    (audio / "N.wav").write_bytes(b"same-audio")

    csv_path = tmp_path / "letters.csv"
    write_letter_csv(csv_path, [
        {"letter": "M", "ipa_from_atlas": "/ɛm/", "file": "M.wav"},
        {"letter": "N", "ipa_from_atlas": "/ɛn/", "file": "N.wav"},
    ])

    issues = audit_letter_audio_manifest(audio, csv_path)

    assert any(
        issue["code"] == "DUPLICATE_AUDIO_ACROSS_IPA_LABELS"
        for issue in issues
    )


def test_reports_missing_letter_audio(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    csv_path = tmp_path / "letters.csv"
    write_letter_csv(csv_path, [
        {"letter": "M", "ipa_from_atlas": "/ɛm/", "file": "missing.wav"},
    ])

    issues = audit_letter_audio_manifest(audio, csv_path)

    assert any(issue["code"] == "MISSING_LETTER_AUDIO" for issue in issues)


def test_accepts_distinct_audio_for_distinct_ipa_labels(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "M.wav").write_bytes(b"audio-M")
    (audio / "N.wav").write_bytes(b"audio-N")

    csv_path = tmp_path / "letters.csv"
    write_letter_csv(csv_path, [
        {"letter": "M", "ipa_from_atlas": "/ɛm/", "file": "M.wav"},
        {"letter": "N", "ipa_from_atlas": "/ɛn/", "file": "N.wav"},
    ])

    assert audit_letter_audio_manifest(audio, csv_path) == []


def test_manifest_detects_missing_asset_and_bad_hash(tmp_path):
    root = tmp_path
    (root / "present.wav").write_bytes(b"present")
    manifest_path = root / "manifest.json"
    write_json(manifest_path, {
        "asset_count": 2,
        "assets": {
            "present.wav": "0" * 64,
            "missing.wav": "1" * 64,
        },
    })

    issues = audit_integration_manifest(root, manifest_path)
    codes = {issue["code"] for issue in issues}

    assert "ASSET_HASH_MISMATCH" in codes
    assert "MISSING_ASSET" in codes


def test_manifest_accepts_json_crlf_lf_only_difference(tmp_path):
    root = tmp_path
    json_asset = root / "asset.json"
    json_asset.write_bytes(b'{\r\n  "ok": true\r\n}\r\n')
    expected = hashlib.sha256(
        b'{\n  "ok": true\n}\n'
    ).hexdigest()

    manifest_path = root / "manifest.json"
    write_json(manifest_path, {
        "asset_count": 1,
        "assets": {"asset.json": expected},
    })

    issues = audit_integration_manifest(root, manifest_path)

    assert not any(
        issue["code"] == "ASSET_HASH_MISMATCH"
        for issue in issues
    )


def test_manifest_flags_duplicate_declared_wav_hashes(tmp_path):
    root = tmp_path
    (root / "M.wav").write_bytes(b"same")
    (root / "N.wav").write_bytes(b"same")
    digest = hashlib.sha256(b"same").hexdigest()

    manifest_path = root / "manifest.json"
    write_json(manifest_path, {
        "asset_count": 2,
        "assets": {"M.wav": digest, "N.wav": digest},
    })

    issues = audit_integration_manifest(root, manifest_path)

    assert any(
        issue["code"] == "DUPLICATE_DECLARED_WAV_HASH"
        for issue in issues
    )


def test_flags_duplicate_declared_hash_when_one_wav_is_missing(tmp_path):
    root = tmp_path
    (root / "vowel_e.wav").write_bytes(b"vowel-e")
    digest = hashlib.sha256(b"vowel-e").hexdigest()

    manifest_path = root / "manifest.json"
    write_json(manifest_path, {
        "asset_count": 2,
        "assets": {
            "vowel_e.wav": digest,
            "vowel_?.wav": digest,
        },
    })

    issues = audit_integration_manifest(root, manifest_path)
    codes = {issue["code"] for issue in issues}

    assert "MISSING_ASSET" in codes
    assert "DUPLICATE_DECLARED_WAV_HASH" in codes



def test_audio_tree_detects_identical_wav_content(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir(parents=True)

    (audio / "first.wav").write_bytes(b"identical-audio")
    (audio / "second.wav").write_bytes(b"identical-audio")

    issues = audit_audio_tree(audio)

    duplicates = [
        issue for issue in issues
        if issue["code"] == "DUPLICATE_AUDIO_CONTENT"
    ]
    assert len(duplicates) == 1


def test_audio_tree_accepts_unique_wav_content(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir(parents=True)

    (audio / "first.wav").write_bytes(b"audio-one")
    (audio / "second.wav").write_bytes(b"audio-two")

    assert audit_audio_tree(audio) == []


def test_formant_audit_detects_duplicate_vowel_targets(tmp_path):
    csv_path = tmp_path / "formants.csv"
    csv_path.write_text(
        "sound,type,target_F1_Hz,target_F2_Hz,target_F3_Hz\n"
        "e,vowel,530,1840,2480\n"
        "ɛ,vowel,530,1840,2480\n",
        encoding="utf-8",
    )

    issues = audit_vowel_formant_targets(csv_path)

    duplicates = [
        issue for issue in issues
        if issue["code"] == "DUPLICATE_VOWEL_FORMANT_TARGETS"
    ]
    assert len(duplicates) == 1
    assert duplicates[0]["labels"] == ["e", "ɛ"]


def test_audio_tree_paths_are_relative_to_audio_root(tmp_path):
    audio = tmp_path / "custom" / "audio"
    audio.mkdir(parents=True)

    (audio / "first.wav").write_bytes(b"same")
    (audio / "second.wav").write_bytes(b"same")

    issues = audit_audio_tree(audio)

    duplicate = next(
        issue for issue in issues
        if issue["code"] == "DUPLICATE_AUDIO_CONTENT"
    )

    assert duplicate["paths"] == ["first.wav", "second.wav"]


def test_formant_audit_rejects_non_finite_and_non_positive_values(
    tmp_path,
):
    csv_path = tmp_path / "formants.csv"
    csv_path.write_text(
        "sound,type,target_F1_Hz,target_F2_Hz,target_F3_Hz\n"
        "e,vowel,NaN,1840,2480\n"
        "i,vowel,300,inf,2500\n"
        "u,vowel,0,900,2200\n"
        ",vowel,400,1500,2500\n",
        encoding="utf-8",
    )

    issues = audit_vowel_formant_targets(csv_path)

    invalid = [
        issue for issue in issues
        if issue["code"] == "INVALID_FORMANT_TARGET"
    ]

    assert len(invalid) == 4


def test_formant_audit_rejects_invalid_csv_schema(tmp_path):
    csv_path = tmp_path / "formants.csv"
    csv_path.write_text(
        "sound,type,target_F1_Hz\n"
        "e,vowel,530\n",
        encoding="utf-8",
    )

    issues = audit_vowel_formant_targets(csv_path)

    assert len(issues) == 1
    assert issues[0]["code"] == "INVALID_FORMANT_TARGETS_SCHEMA"
