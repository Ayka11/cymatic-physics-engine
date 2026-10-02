from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_verify_stft_reproducibility import make_fixture

SCRIPT = Path(__file__).resolve().parents[1] / "analyze_stft_parameter_sensitivity.py"


class STFTParameterSensitivityTests(unittest.TestCase):
    def test_valid_fixture_reports_all_configurations(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            output = Path(td) / "sensitivity.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root), "--out", str(output)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "AUDIO_STFT_PARAMETER_SENSITIVITY_E0")
            self.assertEqual(report["verification_status"], "STFT_REPRODUCIBILITY_VERIFIED_E0")
            self.assertEqual(report["configurations_evaluated"], 6)
            self.assertEqual(len(report["results"]), 6)
            baseline = report["baseline_result"]
            self.assertEqual(baseline["nperseg"], 4096)
            self.assertEqual(baseline["hop"], 1024)
            self.assertEqual(baseline["nfft"], 16384)
            for row in report["results"]:
                self.assertGreater(row["frame_count"], 0)
                self.assertGreater(row["frequency_bin_spacing_hz"], 0)
                self.assertTrue(50 <= row["mean_spectrum_peak_frequency_hz"] <= 8000)
                self.assertEqual(
                    [item["magnitude_floor_db_relative_to_global_peak"]
                     for item in row["phase_support_sensitivity"]],
                    [-40.0, -60.0],
                )
                for item in row["phase_support_sensitivity"]:
                    self.assertGreaterEqual(item["eligible_frequency_bin_count"], 0)
                    summary = item["eligible_bin_concentration_summary"]
                    self.assertEqual(summary["count"], item["eligible_frequency_bin_count"])
                    if summary["count"]:
                        self.assertGreaterEqual(summary["median"], 0.0)
                        self.assertLessEqual(summary["median"], 1.0)
                        self.assertGreaterEqual(summary["maximum"], 0.0)
                        self.assertLessEqual(summary["maximum"], 1.0)
            self.assertIn("not a spatial", report["interpretation"].lower())
            self.assertTrue(any("HFR-06" in x for x in report["limitations"]))

    def test_tampered_saved_stft_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input", tamper_stft=True)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(root)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Complex STFT mismatch", result.stderr)

    def test_invalid_frequency_band_rejected(self):
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
