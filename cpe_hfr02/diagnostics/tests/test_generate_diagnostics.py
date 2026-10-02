from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "generate_diagnostics.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_fixture(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "source.ogg"
    source.write_bytes(b"test-only-fixture-not-a-real-audio-source")
    wav_path = root / "canonical_48k_mono.wav"
    sr = 48000
    n = 12000
    samples = (0.25 * np.sin(2 * np.pi * 440 * np.arange(n) / sr))
    pcm = np.round(samples * 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    frequencies = np.arange(8193, dtype=np.float64) * (sr / 16384)
    times = np.arange(48, dtype=np.float64) * (1024 / sr)
    real = np.ones((frequencies.size, times.size), dtype=np.float64) * 0.01
    imag = np.ones_like(real) * 0.005
    np.savez_compressed(root / "complex_stft.npz",
                        frequency_hz=frequencies, time_s=times,
                        field_real=real, field_imag=imag)
    provenance = {
        "status": "ALTERNATE_SOURCE_AUDIO_STFT_COMPUTED_E0",
        "source_word": "fixture",
        "source_language": "test",
        "source_page": "https://example.invalid/test-fixture",
        "source_sha256": sha256(source),
        "canonical_wav_sha256": sha256(wav_path),
        "sample_rate_hz": sr
    }
    (root / "provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8")
    return root


class DiagnosticVisualizationTests(unittest.TestCase):
    def test_valid_fixture_generates_three_plots_and_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            out = Path(td) / "out"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root), "--out", str(out),
                 "--max-frequency", "30000"],
                capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            expected = [
                "01_audio_waveform.png",
                "02_stft_magnitude_spectrogram.png",
                "03_stft_phase.png",
                "diagnostic_report.json"
            ]
            for name in expected:
                self.assertTrue((out / name).is_file(), name)
                self.assertGreater((out / name).stat().st_size, 0, name)
            report = json.loads((out / "diagnostic_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "AUDIO_STFT_DIAGNOSTICS_GENERATED_E0")
            self.assertEqual(report["stft_shape_frequency_by_time"], [8193, 48])
            self.assertEqual(len(report["plots"]), 3)

    def test_tampered_wav_hash_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            p = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
            p["canonical_wav_sha256"] = "0" * 64
            (root / "provenance.json").write_text(json.dumps(p), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root)],
                capture_output=True, text=True, timeout=90)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("WAV hash mismatch", result.stderr)

    def test_malformed_stft_shape_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            with np.load(root / "complex_stft.npz", allow_pickle=False) as z:
                f = z["frequency_hz"]
                t = z["time_s"]
                real = z["field_real"][:, :-1]
                imag = z["field_imag"][:, :-1]
            np.savez_compressed(root / "complex_stft.npz",
                                frequency_hz=f, time_s=t,
                                field_real=real, field_imag=imag)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root)],
                capture_output=True, text=True, timeout=90)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Array shape mismatch", result.stderr)

    def test_nonfinite_stft_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            with np.load(root / "complex_stft.npz", allow_pickle=False) as z:
                f = z["frequency_hz"]
                t = z["time_s"]
                real = z["field_real"].copy()
                imag = z["field_imag"].copy()
            real[5, 5] = np.nan
            np.savez_compressed(root / "complex_stft.npz",
                                frequency_hz=f, time_s=t,
                                field_real=real, field_imag=imag)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root)],
                capture_output=True, text=True, timeout=90)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Non-finite data", result.stderr)

    def test_wrong_status_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            p = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
            p["status"] = "PHYSICAL_VALIDATION_PASSED"
            (root / "provenance.json").write_text(json.dumps(p), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root)],
                capture_output=True, text=True, timeout=90)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unexpected provenance status", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
