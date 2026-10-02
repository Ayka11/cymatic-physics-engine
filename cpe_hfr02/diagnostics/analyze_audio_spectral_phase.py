from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import stft

from verify_stft_reproducibility import verify


def wrap_phase(values: np.ndarray) -> np.ndarray:
    return np.angle(np.exp(1j * values))


def analyze(input_dir: Path, min_frequency_hz: float = 50.0,
            max_frequency_hz: float = 8000.0, phase_floor_db: float = -40.0) -> dict:
    # Fail closed: source/WAV hashes and the saved STFT must pass before analysis.
    verification = verify(input_dir)
    wav_path = input_dir / "canonical_48k_mono.wav"
    sr, pcm = wavfile.read(wav_path)
    x = pcm.astype(np.float64) / 32768.0

    frequencies, times, z = stft(
        x, fs=sr, window="hann", nperseg=4096, noverlap=3072,
        nfft=16384, detrend=False, return_onesided=True,
        boundary=None, padded=False, scaling="spectrum",
    )
    magnitude = np.abs(z)
    global_peak = float(np.max(magnitude))
    if not np.isfinite(global_peak) or global_peak <= 0:
        raise ValueError("STFT is silent or non-finite; refusing spectral analysis.")

    band = (frequencies >= min_frequency_hz) & (frequencies <= max_frequency_hz)
    if not np.any(band):
        raise ValueError("Requested frequency band contains no STFT bins.")
    fb = frequencies[band]
    mb = magnitude[band, :]
    eps = np.finfo(np.float64).tiny

    frames = []
    for j, time_s in enumerate(times):
        column = mb[:, j]
        peak_idx = int(np.argmax(column))
        power_sum = float(np.sum(column ** 2))
        centroid = float(np.sum(fb * column) / max(float(np.sum(column)), eps))
        geometric = float(np.exp(np.mean(np.log(np.maximum(column, eps)))))
        arithmetic = float(np.mean(column))
        flatness = float(geometric / max(arithmetic, eps))
        frames.append({
            "frame_index": j,
            "time_s": float(time_s),
            "band_peak_frequency_hz": float(fb[peak_idx]),
            "band_peak_magnitude": float(column[peak_idx]),
            "band_peak_relative_db_to_global_peak": float(
                20.0 * np.log10(max(float(column[peak_idx]), eps) / global_peak)
            ),
            "spectral_centroid_hz": centroid,
            "spectral_flatness": flatness,
            "band_magnitude_l2": float(np.sqrt(power_sum)),
        })

    # Audio-domain phase-increment diagnostic. Remove the expected phase advance
    # for each FFT frequency before calculating circular concentration. Only
    # bins above the stated global-relative magnitude floor in >=80% of frames
    # are included; this is not a spatial phase or physical-field measurement.
    threshold = global_peak * (10.0 ** (phase_floor_db / 20.0))
    supported = magnitude >= threshold
    support_fraction = np.mean(supported, axis=1)
    phase = np.angle(z)
    phase_increment = wrap_phase(np.diff(phase, axis=1))
    expected_advance = 2.0 * np.pi * frequencies * (1024.0 / sr)
    residual = wrap_phase(phase_increment - expected_advance[:, None])
    pair_supported = supported[:, 1:] & supported[:, :-1]
    phase_rows = []
    for i, f_hz in enumerate(frequencies):
        valid = pair_supported[i]
        if support_fraction[i] >= 0.8 and int(np.sum(valid)) >= 2:
            vals = residual[i, valid]
            concentration = float(np.abs(np.mean(np.exp(1j * vals))))
            phase_rows.append({
                "frequency_hz": float(f_hz),
                "supported_frame_fraction": float(support_fraction[i]),
                "phase_increment_residual_circular_concentration": concentration,
                "valid_frame_pairs": int(np.sum(valid)),
            })
    phase_rows.sort(
        key=lambda item: (item["phase_increment_residual_circular_concentration"], item["frequency_hz"]),
        reverse=True,
    )

    # Report threshold sensitivity separately from the primary phase result.
    # This makes a zero-eligible-bin outcome auditable without silently relaxing
    # the configured threshold used for phase_rows.
    phase_support_sensitivity = []
    for floor_db in (-20.0, -30.0, -40.0, -50.0, -60.0):
        floor = global_peak * (10.0 ** (floor_db / 20.0))
        support = magnitude >= floor
        fractions = np.mean(support, axis=1)
        adjacent_pairs = support[:, 1:] & support[:, :-1]
        frame_supported_count = int(np.sum(fractions >= 0.8))
        pair_eligible_count = int(np.sum(
            (fractions >= 0.8) & (np.sum(adjacent_pairs, axis=1) >= 2)
        ))
        phase_support_sensitivity.append({
            "magnitude_floor_db_relative_to_global_peak": floor_db,
            "frequency_bins_meeting_frame_support": frame_supported_count,
            "frequency_bins_meeting_frame_and_pair_support": pair_eligible_count,
            "maximum_supported_frame_fraction": float(np.max(fractions)),
        })

    return {
        "status": "AUDIO_SPECTRAL_PHASE_REPORT_E0",
        "verification_status": verification["status"],
        "source_sha256": verification["source_sha256"],
        "canonical_wav_sha256": verification["canonical_wav_sha256"],
        "sample_rate_hz": int(sr),
        "sample_count": int(x.size),
        "duration_s": float(x.size / sr),
        "stft": {
            "window": "periodic Hann",
            "nperseg": 4096,
            "hop": 1024,
            "nfft": 16384,
            "frequency_bin_spacing_hz": float(sr / 16384),
            "frames": int(z.shape[1]),
            "frequency_bins": int(z.shape[0]),
            "analysis_band_hz": [float(min_frequency_hz), float(max_frequency_hz)],
        },
        "summary": {
            "global_stft_peak_magnitude": global_peak,
            "mean_band_spectral_centroid_hz": float(np.mean([r["spectral_centroid_hz"] for r in frames])),
            "frame_count": len(frames),
        },
        "frame_metrics": frames,
        "audio_domain_phase_diagnostic": {
            "magnitude_floor_db_relative_to_global_peak": float(phase_floor_db),
            "minimum_supported_frame_fraction": 0.8,
            "eligible_frequency_bin_count": len(phase_rows),
            "support_sensitivity": phase_support_sensitivity,
            "support_sensitivity_note": (
                "Counts show how eligibility changes at diagnostic magnitude floors. "
                "The configured phase-floor-dB value alone determines the primary "
                "highest_concentration_bins; sensitivity counts do not replace it."
            ),
            "highest_concentration_bins": phase_rows[:20],
            "interpretation": (
                "Descriptive phase-increment consistency of the audio STFT after removing "
                "expected frequency-dependent frame advance. Not spatial phase, not a "
                "cymatic-field measurement, and not physical validation."
            ),
        },
        "limitations": [
            "This report is computed from the alternate-source audio WAV after the reproducibility gate passes.",
            "Frame peaks and centroids are descriptive audio-spectrum metrics, not phoneme labels or calibrated formants.",
            "Phase metrics are audio-domain diagnostics and depend on windowing, hop size, and the magnitude threshold.",
            "No calibrated sound-pressure, force-transfer, plate-response, or particle/contact measurement is present.",
            "The alternate source does not clear the HFR-06 canonical source-hash gate.",
        ],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a provenance-gated audio spectral and phase diagnostic report."
    )
    parser.add_argument("--input", required=True, help="Existing HFR-02 run directory")
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    parser.add_argument("--min-frequency-hz", type=float, default=50.0)
    parser.add_argument("--max-frequency-hz", type=float, default=8000.0)
    parser.add_argument("--phase-floor-db", type=float, default=-40.0)
    args = parser.parse_args()
    if not all(np.isfinite(v) for v in (
        args.min_frequency_hz, args.max_frequency_hz, args.phase_floor_db
    )):
        parser.error("frequency bounds and phase floor must be finite")
    if args.min_frequency_hz < 0 or args.max_frequency_hz <= args.min_frequency_hz:
        parser.error("Require 0 <= min-frequency-hz < max-frequency-hz")
    if args.phase_floor_db >= 0:
        parser.error("phase-floor-db must be negative relative to the global peak")

    report = analyze(
        Path(args.input).resolve(), args.min_frequency_hz,
        args.max_frequency_hz, args.phase_floor_db,
    )
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).resolve().write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
