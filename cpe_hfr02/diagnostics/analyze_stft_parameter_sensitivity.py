from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import stft

from verify_stft_reproducibility import verify


CONFIGS = (
    {"nperseg": 2048, "hop": 512, "nfft": 8192},
    {"nperseg": 2048, "hop": 1024, "nfft": 8192},
    {"nperseg": 4096, "hop": 1024, "nfft": 16384},
    {"nperseg": 4096, "hop": 2048, "nfft": 16384},
    {"nperseg": 8192, "hop": 2048, "nfft": 32768},
    {"nperseg": 8192, "hop": 4096, "nfft": 32768},
)


def analyze_sensitivity(input_dir: Path, min_frequency_hz: float = 50.0,
                        max_frequency_hz: float = 8000.0) -> dict:
    verification = verify(input_dir)
    wav_path = input_dir / "canonical_48k_mono.wav"
    sr, pcm = wavfile.read(wav_path)
    if pcm.ndim != 1 or pcm.dtype != np.int16:
        raise ValueError("Expected canonical mono PCM16 WAV.")
    x = pcm.astype(np.float64) / 32768.0
    if not np.all(np.isfinite(x)) or not np.any(x):
        raise ValueError("Audio is silent or contains non-finite samples.")
    if min_frequency_hz < 0 or max_frequency_hz <= min_frequency_hz:
        raise ValueError("Require 0 <= min-frequency-hz < max-frequency-hz")

    results = []
    for config in CONFIGS:
        nperseg = config["nperseg"]
        hop = config["hop"]
        nfft = config["nfft"]
        if nperseg > x.size:
            continue
        frequencies, times, z = stft(
            x, fs=sr, window="hann", nperseg=nperseg,
            noverlap=nperseg - hop, nfft=nfft, detrend=False,
            return_onesided=True, boundary=None, padded=False,
            scaling="spectrum",
        )
        magnitude = np.abs(z)
        global_peak = float(np.max(magnitude))
        band = (frequencies >= min_frequency_hz) & (frequencies <= max_frequency_hz)
        if not np.any(band):
            raise ValueError("Requested frequency band contains no bins.")
        band_f = frequencies[band]
        band_m = magnitude[band, :]
        mean_spectrum = np.mean(band_m, axis=1)
        peak_idx = int(np.argmax(mean_spectrum))
        mean_frame_centroid = float(np.mean(
            np.sum(band_f[:, None] * band_m, axis=0)
            / np.maximum(np.sum(band_m, axis=0), np.finfo(np.float64).tiny)
        ))

        phase = np.angle(z)
        increments = np.angle(np.exp(1j * np.diff(phase, axis=1)))
        expected = 2.0 * np.pi * frequencies * (hop / sr)
        residual = np.angle(np.exp(1j * (increments - expected[:, None])))
        threshold_rows = []
        for floor_db in (-40.0, -60.0):
            supported = magnitude >= global_peak * (10.0 ** (floor_db / 20.0))
            fractions = np.mean(supported, axis=1)
            pair_support = supported[:, 1:] & supported[:, :-1]
            pair_counts = np.sum(pair_support, axis=1)
            eligible = (fractions >= 0.8) & (pair_counts >= 2)
            concentrations = []
            for i in np.flatnonzero(eligible):
                values = residual[i, pair_support[i]]
                concentrations.append(min(1.0, float(np.abs(np.mean(np.exp(1j * values))))))
            threshold_rows.append({
                "magnitude_floor_db_relative_to_global_peak": floor_db,
                "eligible_frequency_bin_count": int(np.sum(eligible)),
                "maximum_supported_frame_fraction": float(np.max(fractions)),
                "eligible_bin_concentration_summary": {
                    "count": len(concentrations),
                    "median": float(np.median(concentrations)) if concentrations else None,
                    "maximum": float(np.max(concentrations)) if concentrations else None,
                },
            })

        results.append({
            **config,
            "frame_count": int(z.shape[1]),
            "frequency_bin_spacing_hz": float(sr / nfft),
            "analysis_band_hz": [float(min_frequency_hz), float(max_frequency_hz)],
            "mean_spectrum_peak_frequency_hz": float(band_f[peak_idx]),
            "mean_spectrum_peak_magnitude": float(mean_spectrum[peak_idx]),
            "mean_frame_spectral_centroid_hz": mean_frame_centroid,
            "phase_support_sensitivity": threshold_rows,
        })

    baseline = next((r for r in results if r["nperseg"] == 4096 and r["hop"] == 1024), None)
    return {
        "status": "AUDIO_STFT_PARAMETER_SENSITIVITY_E0",
        "verification_status": verification["status"],
        "source_sha256": verification["source_sha256"],
        "canonical_wav_sha256": verification["canonical_wav_sha256"],
        "sample_rate_hz": int(sr),
        "sample_count": int(x.size),
        "duration_s": float(x.size / sr),
        "configurations_evaluated": len(results),
        "baseline_configuration": {"nperseg": 4096, "hop": 1024, "nfft": 16384},
        "baseline_result": baseline,
        "results": results,
        "interpretation": (
            "This report tests sensitivity of audio-domain STFT summary metrics to window "
            "length, hop size, and zero-padding. Changes across configurations are expected "
            "because time/frequency resolution and frame support change. It is not a spatial "
            "cymatic-field measurement, physical resonance test, or physical validation."
        ),
        "limitations": [
            "The saved baseline STFT is provenance-verified before the sensitivity analysis runs.",
            "Sensitivity configurations are recomputed from the same canonical WAV and are not compared as if their bins or frames were identical.",
            "Zero-padding increases frequency-grid density but does not create new physical information.",
            "Phase support and concentration are exploratory audio-domain statistics dependent on threshold and STFT configuration.",
            "The alternate source does not clear the HFR-06 canonical source-hash gate.",
            "No calibrated sound-pressure, force-transfer, plate-response, or particle/contact measurement is present.",
        ],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure how audio-domain STFT summaries change across analysis configurations."
    )
    parser.add_argument("--input", required=True, help="Existing HFR-02 run directory")
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    parser.add_argument("--min-frequency-hz", type=float, default=50.0)
    parser.add_argument("--max-frequency-hz", type=float, default=8000.0)
    args = parser.parse_args()
    report = analyze_sensitivity(
        Path(args.input).resolve(), args.min_frequency_hz, args.max_frequency_hz
    )
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).resolve().write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
