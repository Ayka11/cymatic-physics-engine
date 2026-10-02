from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

import numpy as np
from scipy.signal import stft

SCRIPT = Path(__file__).resolve().parents[1] / "verify_stft_reproducibility.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_fixture(root: Path, tamper_stft: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "source.ogg"
    source.write_bytes(b"fixture-source-bytes-not-a-real-recording")
    wav_path = root / "canonical_48k_mono.wav"
    sr = 48000
    n = 52663
    samples = 0.25 * np.sin(2 * np.pi * 440 * np.arange(n) / sr)
    pcm = np.round(samples * 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    x = pcm.astype(np.float64) / 32768.0
    f, t, z = stft(
        x, fs=sr, window="hann", nperseg=4096, noverlap=3072,
        nfft=16384, detrend=False, return_onesided=True,
        boundary=None, padded=False, scaling="spectrum",
    )
    if tamper_stft:
        z = z.copy()
        z[10, 10] += 0.01
    np.savez_compressed(
        root / "complex_stft.npz",
        frequency_hz=f, time_s=t, field_real=z.real, field_imag=z.imag,
    )
    provenance = {
        "status": "ALTERNATE_SOURCE_AUDIO_STFT_COMPUTED_E0",
        "source_word": "fixture",
        "source_language": "test",
        "source_sha256": sha256(source),
        "canonical_wav_sha256": sha256(wav_path),
        "stft": {
            "window": "Hann periodic",
            "nperseg": 4096,
            "hop": 1024,
            "nfft": 16384,
            "frequency_bin_spacing_hz": sr / 16384,
            "complex_phase_preserved": True,
            "frames": len(t),
            "frequency_bins": len(f),
        },
    }
    (root / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return root


class STFTReproducibilityTests(unittest.TestCase):
    def test_exact_recomputation_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            output = Path(td) / "verification.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root), "--out", str(output)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "STFT_REPRODUCIBILITY_VERIFIED_E0")
            self.assertTrue(report["complex_stft_match"])
            self.assertEqual(report["maximum_absolute_complex_error"], 0.0)
            self.assertEqual(report["complex_stft_rmse"], 0.0)

    def test_modified_stft_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input", tamper_stft=True)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Complex STFT mismatch", result.stderr)

    def test_wav_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            p = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
            p["canonical_wav_sha256"] = "0" * 64
            (root / "provenance.json").write_text(json.dumps(p), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("WAV hash mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
