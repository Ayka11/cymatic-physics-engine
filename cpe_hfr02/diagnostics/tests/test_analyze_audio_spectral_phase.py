from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_verify_stft_reproducibility import make_fixture

SCRIPT = Path(__file__).resolve().parents[1] / "analyze_audio_spectral_phase.py"


class AudioSpectralPhaseReportTests(unittest.TestCase):
    def test_valid_fixture_generates_descriptive_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            output = Path(td) / "spectral_phase.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root), "--out", str(output)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "AUDIO_SPECTRAL_PHASE_REPORT_E0")
            self.assertEqual(report["verification_status"], "STFT_REPRODUCIBILITY_VERIFIED_E0")
            self.assertEqual(report["summary"]["frame_count"], 48)
            self.assertEqual(len(report["frame_metrics"]), 48)
            self.assertIn("not spatial phase", report["audio_domain_phase_diagnostic"]["interpretation"].lower())
            self.assertIn("does not clear the HFR-06", " ".join(report["limitations"]))

    def test_tampered_saved_stft_fails_before_analysis(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input", tamper_stft=True)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Complex STFT mismatch", result.stderr)

    def test_invalid_frequency_range_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root),
                 "--min-frequency-hz", "8000", "--max-frequency-hz", "50"],
                capture_output=True, text=True, timeout=60,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Require 0 <= min-frequency-hz", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
