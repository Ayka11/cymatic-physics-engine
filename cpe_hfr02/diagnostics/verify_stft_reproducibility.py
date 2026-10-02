from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import stft


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(input_dir: Path, rtol: float = 1e-7, atol: float = 1e-10) -> dict:
    provenance_path = input_dir / "provenance.json"
    wav_path = input_dir / "canonical_48k_mono.wav"
    source_path = input_dir / "source.ogg"
    stft_path = input_dir / "complex_stft.npz"
    for path in (provenance_path, wav_path, source_path, stft_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("status") != "ALTERNATE_SOURCE_AUDIO_STFT_COMPUTED_E0":
        raise ValueError("Unexpected provenance status; refusing relabel.")

    source_hash = sha256_file(source_path)
    wav_hash = sha256_file(wav_path)
    if source_hash != provenance.get("source_sha256"):
        raise ValueError("Source hash mismatch.")
    if wav_hash != provenance.get("canonical_wav_sha256"):
        raise ValueError("WAV hash mismatch.")

    sr, audio = wavfile.read(wav_path)
    if sr != 48000 or audio.ndim != 1 or audio.dtype != np.int16:
        raise ValueError("Expected 48 kHz mono PCM16 WAV.")
    x = audio.astype(np.float64) / 32768.0
    if x.size == 0 or not np.isfinite(x).all():
        raise ValueError("WAV samples are empty or non-finite.")

    config = provenance.get("stft", {})
    expected_config = {
        "window": "Hann periodic",
        "nperseg": 4096,
        "hop": 1024,
        "nfft": 16384,
        "complex_phase_preserved": True,
    }
    for key, expected in expected_config.items():
        if config.get(key) != expected:
            raise ValueError(f"Unexpected STFT provenance setting {key!r}: {config.get(key)!r}")

    frequencies, times, recomputed = stft(
        x,
        fs=sr,
        window="hann",
        nperseg=4096,
        noverlap=3072,
        nfft=16384,
        detrend=False,
        return_onesided=True,
        boundary=None,
        padded=False,
        scaling="spectrum",
    )

    with np.load(stft_path, allow_pickle=False) as archive:
        saved_f = np.asarray(archive["frequency_hz"], dtype=np.float64)
        saved_t = np.asarray(archive["time_s"], dtype=np.float64)
        saved_real = np.asarray(archive["field_real"], dtype=np.float64)
        saved_imag = np.asarray(archive["field_imag"], dtype=np.float64)

    if saved_real.ndim != 2 or saved_imag.shape != saved_real.shape:
        raise ValueError("Saved complex STFT components have invalid shapes.")
    if not all(np.isfinite(a).all() for a in (saved_f, saved_t, saved_real, saved_imag)):
        raise ValueError("Saved STFT contains non-finite values.")
    saved = saved_real + 1j * saved_imag
    if saved.shape != recomputed.shape:
        raise ValueError(f"STFT shape mismatch: saved={saved.shape}, recomputed={recomputed.shape}")
    if saved_f.shape != frequencies.shape or saved_t.shape != times.shape:
        raise ValueError("STFT axis shape mismatch.")

    frequency_axes_match = bool(np.allclose(frequencies, saved_f, rtol=0, atol=1e-10))
    time_axes_match = bool(np.allclose(times, saved_t, rtol=0, atol=1e-10))
    if not frequency_axes_match or not time_axes_match:
        raise ValueError("STFT frequency or time axis mismatch.")

    errors = np.abs(recomputed - saved)
    max_abs_error = float(np.max(errors))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    scale = max(float(np.max(np.abs(saved))), 1e-30)
    relative_max_error = float(max_abs_error / scale)
    complex_match = bool(np.allclose(recomputed, saved, rtol=rtol, atol=atol))
    if not complex_match:
        raise ValueError(
            "Complex STFT mismatch: "
            f"max_abs_error={max_abs_error:.17g}, rmse={rmse:.17g}, "
            f"relative_max_error={relative_max_error:.17g}"
        )

    return {
        "status": "STFT_REPRODUCIBILITY_VERIFIED_E0",
        "source_status": provenance["status"],
        "source_sha256": source_hash,
        "canonical_wav_sha256": wav_hash,
        "sample_rate_hz": int(sr),
        "sample_count": int(x.size),
        "saved_stft_shape": list(saved.shape),
        "recomputed_stft_shape": list(recomputed.shape),
        "frequency_axes_match": frequency_axes_match,
        "time_axes_match": time_axes_match,
        "complex_stft_match": complex_match,
        "tolerance": {"rtol": rtol, "atol": atol},
        "maximum_absolute_complex_error": max_abs_error,
        "complex_stft_rmse": rmse,
        "maximum_error_over_saved_peak": relative_max_error,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "This verifies numerical reproducibility of the audio-domain STFT only.",
            "It does not validate a spatial cymatic field or any physical effect.",
            "It does not establish acoustic-pressure or acoustic-to-force calibration.",
            "The alternate source does not clear the HFR-06 canonical source-hash gate.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Independently recompute and verify the CPE HFR-02 complex audio STFT."
    )
    parser.add_argument("--input", required=True, help="Existing HFR-02 run directory")
    parser.add_argument("--out", default=None, help="Optional verification JSON path")
    parser.add_argument("--rtol", type=float, default=1e-7)
    parser.add_argument("--atol", type=float, default=1e-10)
    args = parser.parse_args()
    if not np.isfinite(args.rtol) or not np.isfinite(args.atol) or args.rtol < 0 or args.atol < 0:
        parser.error("rtol and atol must be finite and non-negative")

    report = verify(Path(args.input).resolve(), args.rtol, args.atol)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).resolve().write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
