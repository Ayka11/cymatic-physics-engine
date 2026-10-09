from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import re
import zipfile
import wave
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

SCHEMA = "CPE_HFR02_PHASE_COHERENT_BUNDLE_AUDIT_v1"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
EXPECTED_SAMPLE_RATE_HZ = 48000
MIN_SAMPLE_COUNT = 4096


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit_bundle(bundle_path: str | Path) -> dict[str, Any]:
    path = Path(bundle_path)
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "evidence_level_maximum": "E0",
        "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "bundle": {
            "name": path.name,
            "sha256": sha256_bytes(path.read_bytes()) if path.is_file() else None,
            "size_bytes": path.stat().st_size if path.is_file() else None,
        },
        "archive_entries": [],
        "gates": {
            "metadata_object": "BLOCKED",
            "canonical_wav_payload": "BLOCKED",
            "canonical_wav_sha256": "BLOCKED",
            "canonical_wav_format": "BLOCKED",
            "source_conversion_reproducibility": "BLOCKED",
            "alignment_validation": "BLOCKED",
            "acoustic_to_force_calibration": "BLOCKED",
            "spatial_physical_field_validation": "BLOCKED",
        },
        "failures": [],
        "limitations": [
            "Bundle integrity checks do not validate a physical cymatic effect.",
            "Audio-domain phase is not calibrated plate phase.",
            "Acoustic-to-force calibration and spatial physical-field validation are not performed by this tool.",
        ],
    }

    if not path.is_file():
        report["failures"].append("bundle_file_missing")
        return report

    try:
        with zipfile.ZipFile(path) as archive:
            infos = [item for item in archive.infolist() if not item.is_dir()]
            names = [item.filename for item in infos]
            for name in names:
                member = PurePosixPath(name)
                if member.is_absolute() or ".." in member.parts or "\\" in name:
                    report["failures"].append(f"unsafe_archive_path:{name}")
            if len(names) != len(set(names)):
                report["failures"].append("duplicate_archive_member_names")
            if report["failures"]:
                report["archive_entries"] = [
                    {"path": item.filename, "size_bytes": item.file_size}
                    for item in infos
                ]
                return report

            member_bytes = {item.filename: archive.read(item) for item in infos}
            report["archive_entries"] = [
                {
                    "path": item.filename,
                    "size_bytes": item.file_size,
                    "sha256": sha256_bytes(member_bytes[item.filename]),
                }
                for item in infos
            ]
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        report["failures"].append(f"invalid_zip:{type(exc).__name__}:{exc}")
        return report

    metadata_names = [
        name for name in member_bytes
        if PurePosixPath(name).name.casefold() in {
            "hfr02_metadata.json", "provenance.json", "diagnostic_report.json"
        }
    ]
    if len(metadata_names) != 1:
        report["failures"].append(
            "metadata_missing" if not metadata_names else "metadata_ambiguous"
        )
        return report

    try:
        metadata = json.loads(member_bytes[metadata_names[0]].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        report["failures"].append(f"metadata_invalid_json:{type(exc).__name__}")
        return report
    if not isinstance(metadata, dict):
        report["failures"].append("metadata_root_not_object")
        return report
    report["gates"]["metadata_object"] = "PASS"
    report["metadata_summary"] = {
        "experiment": metadata.get("experiment"),
        "declared_status": metadata.get("status"),
        "declared_source_sha256": metadata.get("source_sha256"),
        "declared_canonical_wav_file": metadata.get("canonical_wav_file"),
        "declared_canonical_wav_sha256": metadata.get("canonical_wav_sha256"),
        "declared_evidence_level": metadata.get("evidence_level"),
        "declared_phase_preserved": metadata.get("phase_preserved"),
        "declared_alignment": metadata.get("alignment"),
        "declared_analysis_sample_rate_hz": metadata.get("analysis_sample_rate_hz"),
        "declared_fft": metadata.get("fft"),
        "declared_frequency_bin_spacing_hz": metadata.get("frequency_bin_spacing_hz"),
        "declared_modal_basis": metadata.get("modal_basis"),
        "declared_retained_modes": metadata.get("retained_modes"),
        "declared_modal_cutoff_hz": metadata.get("modal_cutoff_hz"),
        "declared_spatial_grid": metadata.get("spatial_grid"),
        "declared_physical_acoustic_to_force_calibration": metadata.get("physical_acoustic_to_force_calibration"),
        "declared_particle_stage": metadata.get("particle_stage"),
    }

    wav_names = [name for name in member_bytes if name.casefold().endswith(".wav")]
    report["wav_payloads_found"] = wav_names
    if not wav_names:
        report["failures"].append("canonical_wav_payload_missing")
        report["gates"]["canonical_wav_payload"] = "BLOCKED"
        return report

    declared_wav = metadata.get("canonical_wav_file")
    if not isinstance(declared_wav, str) or not declared_wav.strip():
        report["failures"].append("canonical_wav_filename_missing")
        return report
    if declared_wav not in member_bytes or not declared_wav.casefold().endswith(".wav"):
        report["failures"].append("declared_canonical_wav_not_in_archive")
        return report
    wav_bytes = member_bytes[declared_wav]
    report["gates"]["canonical_wav_payload"] = "PASS"

    expected_wav_hash = metadata.get("canonical_wav_sha256")
    if not isinstance(expected_wav_hash, str) or SHA256_RE.fullmatch(expected_wav_hash) is None:
        report["failures"].append("canonical_wav_sha256_missing_or_invalid")
        return report
    actual_wav_hash = sha256_bytes(wav_bytes)
    report["canonical_wav"] = {
        "path": declared_wav,
        "sha256_expected": expected_wav_hash.lower(),
        "sha256_actual": actual_wav_hash,
        "size_bytes": len(wav_bytes),
    }
    if actual_wav_hash.lower() != expected_wav_hash.lower():
        report["failures"].append("canonical_wav_sha256_mismatch")
        return report
    report["gates"]["canonical_wav_sha256"] = "PASS"

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()
            compression_type = wav.getcomptype()
            raw_samples = wav.readframes(frame_count)
    except Exception as exc:
        report["failures"].append(f"canonical_wav_decode_failed:{type(exc).__name__}")
        return report

    expected_payload_bytes = frame_count * channels * sample_width
    payload_length_matches = len(raw_samples) == expected_payload_bytes
    pcm16 = np.frombuffer(raw_samples, dtype="<i2") if sample_width == 2 else np.array([], dtype=np.int16)
    non_silent = bool(pcm16.size and np.any(pcm16 != 0))
    format_record = {
        "sample_rate_hz": int(sample_rate),
        "channels": int(channels),
        "frames": int(frame_count),
        "sample_width_bytes": int(sample_width),
        "compression_type": compression_type,
        "expected_payload_bytes": int(expected_payload_bytes),
        "actual_payload_bytes": int(len(raw_samples)),
        "payload_length_matches": bool(payload_length_matches),
        "finite_samples": bool(sample_width == 2 and payload_length_matches),
        "non_silent": non_silent,
    }
    report["canonical_wav_format"] = format_record
    if sample_rate != EXPECTED_SAMPLE_RATE_HZ:
        report["failures"].append("canonical_wav_sample_rate_mismatch")
    if channels != 1:
        report["failures"].append("canonical_wav_not_mono")
    if sample_width != 2 or compression_type != "NONE":
        report["failures"].append("canonical_wav_not_pcm16")
    if frame_count < MIN_SAMPLE_COUNT:
        report["failures"].append("canonical_wav_too_short")
    if not payload_length_matches:
        report["failures"].append("canonical_wav_truncated_pcm_payload")
    if not non_silent:
        report["failures"].append("canonical_wav_silent_or_not_pcm16")

    if report["failures"]:
        return report

    report["gates"]["canonical_wav_format"] = "PASS"
    report["status"] = "AUDIO_PAYLOAD_VERIFIED_E0"
    source_file = metadata.get("source_file")
    source_hash = metadata.get("source_sha256")
    source_reproducible = (
        isinstance(source_file, str)
        and source_file in member_bytes
        and isinstance(source_hash, str)
        and SHA256_RE.fullmatch(source_hash) is not None
        and sha256_bytes(member_bytes[source_file]).lower() == source_hash.lower()
    )
    report["gates"]["source_conversion_reproducibility"] = (
        "PASS" if source_reproducible else "BLOCKED"
    )
    if not source_reproducible:
        report["failures"].append("source_payload_not_verified_for_conversion_reproduction")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed audit of a phase-coherent HFR-02 WAV bundle."
    )
    parser.add_argument("bundle", type=Path, help="ZIP bundle to audit")
    parser.add_argument("--out", type=Path, help="Optional JSON report path")
    args = parser.parse_args(argv)
    report = audit_bundle(args.bundle)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "AUDIO_PAYLOAD_VERIFIED_E0" else 2


if __name__ == "__main__":
    raise SystemExit(main())
