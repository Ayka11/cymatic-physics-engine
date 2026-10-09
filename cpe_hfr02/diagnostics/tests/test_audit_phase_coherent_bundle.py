import hashlib
import io
import json
import math
import struct
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

from cpe_hfr02.diagnostics.audit_phase_coherent_bundle import audit_bundle


def _wav_bytes(sample_rate=48000, duration=0.12, channels=1):
    frames = int(sample_rate * duration)
    values = []
    for i in range(frames):
        value = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
        values.extend([value] * channels)
    pcm = struct.pack("<" + "h" * len(values), *values)
    out = io.BytesIO()
    with wave.open(out, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(pcm)
    return out.getvalue()


def _write_bundle(path, wav=None, metadata=None):
    if metadata is None:
        metadata = {
            "experiment": "HFR-02",
            "status": "REAL_WAV_PHASE_COHERENT_REDUCED_ORDER_EXPERIMENT",
            "source_sha256": "a" * 64,
            "evidence_level": "E1",
            "phase_preserved": True,
        }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("HFR02_METADATA.json", json.dumps(metadata))
        if wav is not None:
            archive.writestr("canonical_48k_mono.wav", wav)


class PhaseCoherentBundleAuditTests(unittest.TestCase):
    def test_metadata_only_bundle_is_blocked_even_if_it_claims_real_wav(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "metadata_only.zip"
            _write_bundle(bundle)
            result = audit_bundle(bundle)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("canonical_wav_payload_missing", result["failures"])
            self.assertEqual(result["evidence_level_maximum"], "E0")
            self.assertEqual(result["gates"]["acoustic_to_force_calibration"], "BLOCKED")
            self.assertEqual(result["gates"]["spatial_physical_field_validation"], "BLOCKED")

    def test_hash_bound_pcm16_wav_passes_audio_payload_gate_only(self):
        with tempfile.TemporaryDirectory() as temp:
            wav = _wav_bytes()
            metadata = {
                "experiment": "HFR-02",
                "source_file": "source.ogg",
                "source_sha256": "b" * 64,
                "canonical_wav_file": "canonical_48k_mono.wav",
                "canonical_wav_sha256": hashlib.sha256(wav).hexdigest(),
                "evidence_level": "E1",
                "phase_preserved": True,
            }
            bundle = Path(temp) / "wav_bundle.zip"
            _write_bundle(bundle, wav=wav, metadata=metadata)
            result = audit_bundle(bundle)
            self.assertEqual(result["status"], "AUDIO_PAYLOAD_VERIFIED_E0")
            self.assertEqual(result["gates"]["canonical_wav_payload"], "PASS")
            self.assertEqual(result["gates"]["canonical_wav_sha256"], "PASS")
            self.assertEqual(result["gates"]["canonical_wav_format"], "PASS")
            self.assertEqual(result["gates"]["source_conversion_reproducibility"], "BLOCKED")
            self.assertEqual(result["evidence_level_maximum"], "E0")
            self.assertEqual(result["gates"]["acoustic_to_force_calibration"], "BLOCKED")

    def test_wav_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            wav = _wav_bytes()
            metadata = {
                "experiment": "HFR-02",
                "canonical_wav_file": "canonical_48k_mono.wav",
                "canonical_wav_sha256": "0" * 64,
            }
            bundle = Path(temp) / "bad_hash.zip"
            _write_bundle(bundle, wav=wav, metadata=metadata)
            result = audit_bundle(bundle)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("canonical_wav_sha256_mismatch", result["failures"])

    def test_non_mono_or_wrong_rate_wav_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            wav = _wav_bytes(sample_rate=44100, channels=2)
            metadata = {
                "experiment": "HFR-02",
                "canonical_wav_file": "canonical_48k_mono.wav",
                "canonical_wav_sha256": hashlib.sha256(wav).hexdigest(),
            }
            bundle = Path(temp) / "bad_format.zip"
            _write_bundle(bundle, wav=wav, metadata=metadata)
            result = audit_bundle(bundle)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("canonical_wav_sample_rate_mismatch", result["failures"])
            self.assertIn("canonical_wav_not_mono", result["failures"])


if __name__ == "__main__":
    unittest.main()
