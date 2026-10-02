from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile


KNOWN_MOJIBAKE = "РјР°РјР°"
CORRECT_WORD = "мама"
EXPECTED_STATUS = "ALTERNATE_SOURCE_AUDIO_STFT_COMPUTED_E0"


def repair(path: Path, apply: bool = False) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    original_bytes = path.read_bytes()
    document = json.loads(original_bytes.decode("utf-8"))

    if document.get("status") != EXPECTED_STATUS:
        raise ValueError("Unexpected provenance status; refusing to edit metadata.")
    if document.get("source_language") != "Russian":
        raise ValueError("Expected source_language='Russian'; refusing to guess.")
    word = document.get("source_word")
    if word == CORRECT_WORD:
        return {"status": "NO_CHANGE_NEEDED", "source_word": word, "applied": False}
    if word != KNOWN_MOJIBAKE:
        raise ValueError(
            f"Unrecognized source_word {word!r}; refusing automatic correction."
        )

    old_source_hash = document.get("source_sha256")
    old_wav_hash = document.get("canonical_wav_sha256")
    document["source_word"] = CORRECT_WORD
    updated_bytes = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    # Verify this metadata-only edit preserves recorded binary hashes.
    checked = json.loads(updated_bytes.decode("utf-8"))
    if checked.get("source_sha256") != old_source_hash:
        raise RuntimeError("Source hash metadata unexpectedly changed.")
    if checked.get("canonical_wav_sha256") != old_wav_hash:
        raise RuntimeError("WAV hash metadata unexpectedly changed.")

    result = {
        "status": "METADATA_ENCODING_REPAIR_PREVIEW" if not apply else "METADATA_ENCODING_REPAIRED",
        "source_word_before": word,
        "source_word_after": CORRECT_WORD,
        "source_sha256_unchanged": checked.get("source_sha256") == old_source_hash,
        "canonical_wav_sha256_unchanged": checked.get("canonical_wav_sha256") == old_wav_hash,
        "applied": apply,
        "path": str(path),
    }
    if apply:
        # Atomic replacement: write a UTF-8 temporary file in the same directory, then replace.
        fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(updated_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safely correct a known Russian source_word mojibake value in CPE provenance JSON."
    )
    parser.add_argument("--provenance", required=True, help="Path to provenance.json")
    parser.add_argument("--apply", action="store_true", help="Write the metadata-only correction; default is preview")
    args = parser.parse_args()
    result = repair(Path(args.provenance).resolve(), apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
