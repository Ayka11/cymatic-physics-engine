import hashlib
import json
import zipfile

from cpe_hfr02.diagnostics.audit_phase_coherent_bundle import audit_bundle


def _write_metadata_only_bundle(path):
    metadata = {
        "experiment": "HFR-02",
        "status": "REAL_WAV_PHASE_COHERENT_REDUCED_ORDER_EXPERIMENT",
        "source_sha256": "a" * 64,
        "evidence_level": "E1",
        "phase_preserved": True,
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("HFR02_METADATA.json", json.dumps(metadata))


def test_metadata_only_bundle_is_blocked_even_if_it_claims_real_wav(tmp_path):
    bundle = tmp_path / "metadata_only.zip"
    _write_metadata_only_bundle(bundle)
    result = audit_bundle(bundle)

    assert result["status"] == "BLOCKED"
    assert "canonical_wav_payload_missing" in result["failures"]
    assert result["evidence_level_maximum"] == "E0"
    assert result["gates"]["acoustic_to_force_calibration"] == "BLOCKED"
    assert result["gates"]["spatial_physical_field_validation"] == "BLOCKED"


def test_wav_hash_mismatch_fails_closed(tmp_path):
    wav = b"not-a-real-wav-payload"
    metadata = {
        "experiment": "HFR-02",
        "canonical_wav_file": "canonical_48k_mono.wav",
        "canonical_wav_sha256": "0" * 64,
    }
    bundle = tmp_path / "bad_hash.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("HFR02_METADATA.json", json.dumps(metadata))
        archive.writestr("canonical_48k_mono.wav", wav)

    result = audit_bundle(bundle)
    assert result["status"] == "BLOCKED"
    assert "canonical_wav_sha256_mismatch" in result["failures"]
