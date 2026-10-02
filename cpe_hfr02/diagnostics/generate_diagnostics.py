from __future__ import annotations

import argparse
import hashlib
import json
import math
import wave
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def spectral_peak_summary(frequency_hz: np.ndarray, magnitude: np.ndarray,
                          max_frequency_hz: float, count: int = 10) -> list[dict]:
    """Return prominent local peaks in mean STFT magnitude; descriptive, not phoneme labels."""
    mean_magnitude = np.mean(magnitude, axis=1)
    eligible = np.flatnonzero((frequency_hz > 0) & (frequency_hz <= max_frequency_hz))
    if eligible.size < 3:
        return []
    candidates = eligible[
        (mean_magnitude[eligible] >= mean_magnitude[eligible - 1]) &
        (mean_magnitude[eligible] > mean_magnitude[eligible + 1])
    ]
    if candidates.size == 0:
        candidates = eligible
    ranked = candidates[np.argsort(mean_magnitude[candidates])[::-1]][:count]
    reference = max(float(np.max(mean_magnitude[eligible])), np.finfo(float).tiny)
    return [
        {
            "frequency_hz": float(frequency_hz[i]),
            "mean_magnitude_relative_db": float(20 * np.log10(
                max(float(mean_magnitude[i]), np.finfo(float).tiny) / reference
            )),
        }
        for i in ranked
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate E0 audio-domain CPE diagnostics.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--max-frequency", type=float, default=8000.0)
    args = parser.parse_args()
    if not math.isfinite(args.max_frequency) or args.max_frequency <= 0:
        raise ValueError("--max-frequency must be a finite positive number.")

    source_dir = Path(args.input).resolve()
    output_dir = Path(args.out).resolve() if args.out else source_dir / "diagnostics"
    provenance_path = source_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("status") != "ALTERNATE_SOURCE_AUDIO_STFT_COMPUTED_E0":
        raise ValueError("Unexpected provenance status; refusing relabel.")

    wav_path = source_dir / "canonical_48k_mono.wav"
    source_audio_path = source_dir / "source.ogg"
    stft_path = source_dir / "complex_stft.npz"
    for path in (wav_path, source_audio_path, stft_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    with wave.open(str(wav_path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()
        raw_samples = wav_file.readframes(frame_count)
        samples = np.frombuffer(raw_samples, dtype="<i2").astype(np.float64) / 32768.0

    if (sample_rate, channels, sample_width) != (48000, 1, 2):
        raise ValueError("Expected 48 kHz mono PCM16.")
    if frame_count == 0 or samples.size == 0:
        raise ValueError("Audio WAV is empty.")
    if samples.size != frame_count:
        raise ValueError("WAV frame count does not match decoded sample count.")

    with np.load(stft_path, allow_pickle=False) as archive:
        frequency_hz = np.asarray(archive["frequency_hz"], dtype=np.float64)
        time_s = np.asarray(archive["time_s"], dtype=np.float64)
        real = np.asarray(archive["field_real"], dtype=np.float64)
        imaginary = np.asarray(archive["field_imag"], dtype=np.float64)

    if frequency_hz.ndim != 1 or time_s.ndim != 1 or not frequency_hz.size or not time_s.size:
        raise ValueError("Frequency and time axes must be non-empty 1D arrays.")
    if real.ndim != 2 or imaginary.ndim != 2 or real.shape != imaginary.shape:
        raise ValueError("Complex STFT components must be matching 2D arrays.")
    if real.shape != (frequency_hz.size, time_s.size):
        raise ValueError("Array shape mismatch.")
    if not all(np.isfinite(array).all() for array in (samples, frequency_hz, time_s, real, imaginary)):
        raise ValueError("Non-finite data.")
    if np.any(np.diff(frequency_hz) <= 0) or np.any(np.diff(time_s) <= 0):
        raise ValueError("Frequency and time axes must be strictly increasing.")
    if frequency_hz.size < 2:
        raise ValueError("At least two frequency bins are required.")
    if frequency_hz[0] < 0 or frequency_hz[-1] > sample_rate / 2 + 1e-6:
        raise ValueError("Frequency axis is outside the valid Nyquist range.")
    if not np.any(real != 0) and not np.any(imaginary != 0):
        raise ValueError("Complex STFT contains only zeros.")
    if not np.any(imaginary != 0):
        raise ValueError("Imaginary component is zero.")

    actual_wav_hash = sha256_file(wav_path)
    actual_source_hash = sha256_file(source_audio_path)
    if actual_wav_hash != provenance.get("canonical_wav_sha256"):
        raise ValueError("WAV hash mismatch.")
    if actual_source_hash != provenance.get("source_sha256"):
        raise ValueError("Source hash mismatch.")

    output_dir.mkdir(parents=True, exist_ok=True)
    magnitude = np.hypot(real, imaginary)
    phase = np.arctan2(imaginary, real)
    max_frequency = min(args.max_frequency, float(frequency_hz[-1]))
    frequency_mask = frequency_hz <= max_frequency
    if np.count_nonzero(frequency_mask) < 2:
        raise ValueError("Frequency limit selects fewer than two bins.")

    magnitude_db = 20 * np.log10(np.maximum(magnitude[frequency_mask], np.finfo(float).tiny))
    magnitude_db -= float(np.max(magnitude_db))
    waveform_time = np.arange(samples.size, dtype=np.float64) / sample_rate

    fig, ax = plt.subplots(figsize=(12, 4.8), constrained_layout=True)
    ax.plot(waveform_time, samples, linewidth=0.65)
    ax.set_title("Russian «мама» — canonical audio waveform (E0)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Normalized PCM amplitude")
    ax.grid(True, alpha=0.25)
    fig.savefig(output_dir / "01_audio_waveform.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    mesh = ax.pcolormesh(time_s, frequency_hz[frequency_mask], magnitude_db,
                         shading="auto", cmap="magma", vmin=-80, vmax=0)
    ax.set_title("Audio STFT magnitude — relative dB (not calibrated sound pressure)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    fig.colorbar(mesh, ax=ax, label="Relative magnitude (dB; peak = 0 dB)")
    fig.savefig(output_dir / "02_stft_magnitude_spectrogram.png", dpi=160)
    plt.close(fig)

    relative_db = 20 * np.log10(np.maximum(magnitude[frequency_mask], np.finfo(float).tiny))
    phase_masked = np.ma.masked_where(
        relative_db < float(np.max(relative_db)) - 50, phase[frequency_mask]
    )
    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    mesh = ax.pcolormesh(time_s, frequency_hz[frequency_mask], phase_masked,
                         shading="auto", cmap="twilight", vmin=-math.pi, vmax=math.pi)
    ax.set_title("Complex STFT phase (low-magnitude bins masked; audio-domain only)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    fig.colorbar(mesh, ax=ax, label="Phase (rad)")
    fig.savefig(output_dir / "03_stft_phase.png", dpi=160)
    plt.close(fig)

    rms = float(np.sqrt(np.mean(np.square(samples))))
    peak_amplitude = float(np.max(np.abs(samples)))
    clipping_threshold = 32767 / 32768
    clipping_count = int(np.count_nonzero(np.abs(samples) >= clipping_threshold))
    metrics = {
        "rms_normalized_pcm": rms,
        "peak_absolute_normalized_pcm": peak_amplitude,
        "crest_factor": float(peak_amplitude / rms) if rms > 0 else None,
        "clipping_sample_count": clipping_count,
        "clipping_sample_fraction": float(clipping_count / samples.size),
        "zero_crossing_rate_per_sample": float(
            np.count_nonzero(np.signbit(samples[1:]) != np.signbit(samples[:-1]))
            / max(samples.size - 1, 1)
        ),
        "spectral_peaks": spectral_peak_summary(
            frequency_hz, magnitude, max_frequency, count=10
        ),
    }

    report = {
        "status": "AUDIO_STFT_DIAGNOSTICS_GENERATED_E0",
        "source_status": provenance["status"],
        "source_sha256": actual_source_hash,
        "canonical_wav_sha256": actual_wav_hash,
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_format": "PCM_S16LE",
        "duration_s": float(samples.size / sample_rate),
        "sample_count": int(samples.size),
        "stft_shape_frequency_by_time": list(real.shape),
        "frequency_bin_spacing_hz": float(frequency_hz[1] - frequency_hz[0]),
        "analysis_max_frequency_hz": float(max_frequency),
        "quantitative_metrics": metrics,
        "plots": [
            "01_audio_waveform.png",
            "02_stft_magnitude_spectrogram.png",
            "03_stft_phase.png",
        ],
        "limitations": [
            "Audio STFT diagnostics only; not a measured spatial cymatic field.",
            "Relative magnitude is not calibrated sound pressure level (SPL).",
            "Phase is audio-domain phase, not spatial plate-field phase.",
            "STFT arrays are shape- and provenance-checked but are not recomputed from the WAV by this script.",
            "No acoustic/force/plate/particle calibration or physical validation.",
            "Alternate source does not clear the HFR-06 source-hash gate.",
            "Spectral peaks are descriptive signal features, not phoneme labels or evidence of physical resonance.",
        ],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "diagnostic_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
