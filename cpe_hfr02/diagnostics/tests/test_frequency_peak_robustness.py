from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_verify_stft_reproducibility import make_fixture

SCRIPT = Path(__file__).resolve().parents[1] / "analyze_frequency_peak_robustness.py"


class FrequencyPeakRobustnessTests(unittest.TestCase):
    def run_report(self, root: Path, *extra: str):
        output = root.parent / "frequency_peak_robustness.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--input", str(root), "--out", str(output), *extra],
            capture_output=True, text=True, timeout=60,
        )
        return result, output

    def test_report_tracks_peaks_and_separates_phase(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            result, output = self.run_report(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "AUDIO_STFT_FREQUENCY_PEAK_ROBUSTNESS_E0")
            self.assertEqual(report["verification_status"], "STFT_REPRODUCIBILITY_VERIFIED_E0")
            self.assertEqual(report["configurations_evaluated"], 6)
            self.assertEqual(len(report["configurations"]), 6)
            self.assertTrue(report["tracked_baseline_peaks"])
            candidate = report["tracked_baseline_peaks"][0]
            self.assertIn("configuration_coverage_fraction", candidate)
            self.assertIn("frequency_drift_peak_to_peak_hz", candidate)
            self.assertEqual(len(candidate["matches_by_configuration"]), 6)
            matched = [m for m in candidate["matches_by_configuration"] if m["match_status"] == "MATCHED"]
            self.assertTrue(matched)
            self.assertIn("magnitude", matched[0])
            self.assertIn("match_tolerance_hz", matched[0])
            self.assertIn("audio_phase_consistency", matched[0])
            self.assertIn("frequency_peak_stability", report["stability_dimensions_are_separate"])
            self.assertFalse(report["scientific_scope"]["physical_resonance_conclusion_permitted"])
            self.assertFalse(report["scientific_scope"]["spatial_cymatic_field_conclusion_permitted"])
            self.assertEqual(report["scientific_scope"]["hfr06_source_hash_gate"],
                             "REMAINS_CLOSED_FOR_ALTERNATE_SOURCE")

    def test_resolution_tolerance_uses_window_not_zero_padding(self):
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            from analyze_frequency_peak_robustness import resolution_aware_tolerance_hz
            self.assertAlmostEqual(resolution_aware_tolerance_hz(48000, 4096, 2048), 17.578125)
            self.assertGreater(resolution_aware_tolerance_hz(48000, 4096, 2048),
                               resolution_aware_tolerance_hz(48000, 4096, 8192))
        finally:
            sys.path.pop(0)

    def test_tampered_stft_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input", tamper_stft=True)
            result, _ = self.run_report(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Complex STFT mismatch", result.stderr)

    def test_invalid_peak_parameters_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_fixture(Path(td) / "input")
            result, _ = self.run_report(root, "--min-peak-db", "5")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("min-peak-db must be between", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
