from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "repair_provenance_encoding.py"


def make_provenance(path: Path, word: str = "РјР°РјР°") -> dict:
    document = {
        "status": "ALTERNATE_SOURCE_AUDIO_STFT_COMPUTED_E0",
        "source_word": word,
        "source_language": "Russian",
        "source_sha256": "a" * 64,
        "canonical_wav_sha256": "b" * 64,
        "stft": {"nperseg": 4096},
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return document


class ProvenanceEncodingRepairTests(unittest.TestCase):
    def test_preview_does_not_modify_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "provenance.json"
            make_provenance(path)
            before = path.read_bytes()
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--provenance", str(path)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(path.read_bytes(), before)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "METADATA_ENCODING_REPAIR_PREVIEW")
            self.assertFalse(report["applied"])

    def test_apply_changes_only_word_and_preserves_hash_fields(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "provenance.json"
            before = make_provenance(path)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--provenance", str(path), "--apply"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            after = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(after["source_word"], "мама")
            self.assertEqual(after["source_sha256"], before["source_sha256"])
            self.assertEqual(after["canonical_wav_sha256"], before["canonical_wav_sha256"])
            self.assertEqual(after["stft"], before["stft"])
            self.assertEqual(json.loads(result.stdout)["status"], "METADATA_ENCODING_REPAIRED")

    def test_unknown_word_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "provenance.json"
            make_provenance(path, word="unknown")
            before = path.read_bytes()
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--provenance", str(path), "--apply"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unrecognized source_word", result.stderr)
            self.assertEqual(path.read_bytes(), before)

    def test_wrong_status_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "provenance.json"
            document = make_provenance(path)
            document["status"] = "PHYSICAL_VALIDATION_PASSED"
            path.write_text(json.dumps(document), encoding="utf-8")
            before = path.read_bytes()
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--provenance", str(path), "--apply"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unexpected provenance status", result.stderr)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
