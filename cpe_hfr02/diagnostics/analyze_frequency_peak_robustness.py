from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks, stft

from verify_stft_reproducibility import verify

CONFIGS = (
    {"nperseg": 2048, "hop": 512, "nfft": 8192},
    {"nperseg": 2048, "hop": 1024, "nfft": 8192},
    {"nperseg": 4096, "hop": 1024, "nfft": 16384},
    {"nperseg": 4096, "hop": 2048, "nfft": 16384},
    {"nperseg": 8192, "hop": 2048, "nfft": 32768},
    {"nperseg": 8192, "hop": 4096, "nfft": 32768},
)
BASELINE = {"nperseg": 4096, "hop": 1024, "nfft": 16384}
DEFAULT_MIN_PEAK_DB = -30.0
DEFAULT_MAX_CANDIDATES = 12
PHASE_FLOOR_DB = -40.0
MIN_FRAME_SUPPORT = 0.8
MIN_ADJACENT_PAIRS = 2


def resolution_aware_tolerance_hz(sample_rate_hz: float, nperseg_a: int,
                                  nperseg_b: int) -> float:
    """Predeclared tolerance based on effective fs/nperseg window scales."""
    if sample_rate_hz <= 0 or nperseg_a <= 0 or nperseg_b <= 0:
        raise ValueError("Sample rate and window lengths must be positive.")
    return 0.5 * (sample_rate_hz / nperseg_a + sample_rate_hz / nperseg_b)


def _peak_rows(frequencies: np.ndarray, mean_magnitude: np.ndarray,
               global_peak: float, min_peak_db: float,
               max_candidates: int) -> list[dict]:
    if global_peak <= 0:
        return []
    indices, _ = find_peaks(mean_magnitude)
    if indices.size == 0:
        indices = np.array([int(np.argmax(mean_magnitude))])
    floor = global_peak * (10.0 ** (min_peak_db / 20.0))
    indices = [int(i) for i in indices if mean_magnitude[i] >= floor]
    indices.sort(key=lambda i: float(mean_magnitude[i]), reverse=True)
    rows = []
    for index in indices[:max_candidates]:
        magnitude = float(mean_magnitude[index])
        rows.append({
            "frequency_hz": float(frequencies[index]),
            "magnitude": magnitude,
            "magnitude_db_relative_to_configuration_global_peak": float(
                20.0 * np.log10(max(magnitude, np.finfo(float).tiny) / global_peak)
            ),
            "bin_index": index,
        })
    return rows



def _match_candidates_one_to_one(reference_candidates: list[dict],
                                 candidate_peaks: list[dict],
                                 tolerance_hz: float) -> dict[int, dict]:
    """Greedily assign peaks by nearest frequency, with no candidate reused."""
    pairs = sorted(
        (
            abs(float(candidate["frequency_hz"]) - float(reference["frequency_hz"])),
            reference_index,
            candidate_index,
        )
        for reference_index, reference in enumerate(reference_candidates)
        for candidate_index, candidate in enumerate(candidate_peaks)
        if abs(float(candidate["frequency_hz"]) - float(reference["frequency_hz"])) <= tolerance_hz
    )
    assigned: dict[int, dict] = {}
    used_candidate_indices: set[int] = set()
    for _, reference_index, candidate_index in pairs:
        if reference_index in assigned or candidate_index in used_candidate_indices:
            continue
        assigned[reference_index] = candidate_peaks[candidate_index]
        used_candidate_indices.add(candidate_index)
    return assigned

def _phase_at_frequency(z: np.ndarray, frequencies: np.ndarray, index: int,
                        hop: int, sample_rate_hz: int, global_peak: float) -> dict:
    magnitude = np.abs(z[index, :])
    threshold = global_peak * (10.0 ** (PHASE_FLOOR_DB / 20.0))
    supported = magnitude >= threshold
    frame_fraction = float(np.mean(supported)) if supported.size else 0.0
    if z.shape[1] >= 2:
        pair_support = supported[1:] & supported[:-1]
        pair_count = int(np.sum(pair_support))
        phase = np.angle(z[index, :])
        increments = np.angle(np.exp(1j * np.diff(phase)))
        expected = 2.0 * np.pi * frequencies[index] * (hop / sample_rate_hz)
        residual = np.angle(np.exp(1j * (increments - expected)))
        values = residual[pair_support]
        concentration = (
            min(1.0, float(np.abs(np.mean(np.exp(1j * values)))))
            if values.size else None
        )
    else:
        pair_count, concentration = 0, None
    eligible = frame_fraction >= MIN_FRAME_SUPPORT and pair_count >= MIN_ADJACENT_PAIRS
    return {
        "status": "AUDIO_PHASE_STATISTIC_AVAILABLE" if eligible else "INSUFFICIENT_AUDIO_PHASE_SUPPORT",
        "magnitude_floor_db_relative_to_configuration_global_peak": PHASE_FLOOR_DB,
        "supported_frame_fraction": frame_fraction,
        "valid_adjacent_frame_pair_count": pair_count,
        "residual_phase_concentration": concentration if eligible else None,
        "note": "Audio-domain phase only; not spatial phase or physical resonance evidence.",
    }


def analyze_frequency_peak_robustness(
    input_dir: Path, min_frequency_hz: float = 50.0,
    max_frequency_hz: float = 8000.0, min_peak_db: float = DEFAULT_MIN_PEAK_DB,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> dict:
    # Fail closed before computing any cross-configuration metrics.
    verification = verify(input_dir)
    sample_rate, pcm = wavfile.read(input_dir / "canonical_48k_mono.wav")
    if pcm.ndim != 1 or pcm.dtype != np.int16:
        raise ValueError("Expected canonical mono PCM16 WAV.")
    audio = pcm.astype(np.float64) / 32768.0
    if not np.all(np.isfinite(audio)) or not np.any(audio):
        raise ValueError("Audio is silent or contains non-finite samples.")
    if min_frequency_hz < 0 or max_frequency_hz <= min_frequency_hz:
        raise ValueError("Require 0 <= min-frequency-hz < max-frequency-hz.")
    if not -120.0 <= min_peak_db <= 0.0:
        raise ValueError("min-peak-db must be between -120 and 0 dB.")
    if not 1 <= max_candidates <= 100:
        raise ValueError("max-candidates must be between 1 and 100.")

    evaluated = []
    for config in CONFIGS:
        nperseg, hop, nfft = config["nperseg"], config["hop"], config["nfft"]
        if nperseg > audio.size:
            continue
        frequencies, _, z = stft(
            audio, fs=sample_rate, window="hann", nperseg=nperseg,
            noverlap=nperseg - hop, nfft=nfft, detrend=False,
            return_onesided=True, boundary=None, padded=False, scaling="spectrum",
        )
        magnitude = np.abs(z)
        band = (frequencies >= min_frequency_hz) & (frequencies <= max_frequency_hz)
        if not np.any(band):
            raise ValueError("Requested frequency band contains no FFT bins.")
        band_indices = np.flatnonzero(band)
        band_mean = np.mean(magnitude[band, :], axis=1)
        candidates = _peak_rows(
            frequencies[band], band_mean, float(np.max(band_mean)),
            min_peak_db, max_candidates,
        )
        for candidate in candidates:
            candidate["fft_bin_index"] = int(band_indices[int(candidate.pop("bin_index"))])
        evaluated.append({
            **config, "frame_count": int(z.shape[1]),
            "frequency_grid_spacing_hz": float(sample_rate / nfft),
            "effective_window_resolution_scale_hz": float(sample_rate / nperseg),
            "candidates": candidates, "_frequencies": frequencies, "_z": z,
            "_global_peak": float(np.max(magnitude)),
        })

    baseline = next((row for row in evaluated if
                     all(row[k] == BASELINE[k] for k in BASELINE)), None)
    if baseline is None:
        raise ValueError("Baseline STFT configuration could not be evaluated.")

    assignments_by_configuration = []
    tolerances_by_configuration = []
    for row in evaluated:
        tolerance = resolution_aware_tolerance_hz(
            sample_rate, BASELINE["nperseg"], row["nperseg"]
        )
        assignments_by_configuration.append(
            _match_candidates_one_to_one(baseline["candidates"], row["candidates"], tolerance)
        )
        tolerances_by_configuration.append(tolerance)

    tracked = []
    for reference_index, reference in enumerate(baseline["candidates"]):
        rank = reference_index + 1
        reference_hz = reference["frequency_hz"]
        matches = []
        for config_index, row in enumerate(evaluated):
            tolerance = tolerances_by_configuration[config_index]
            nearest = assignments_by_configuration[config_index].get(reference_index)
            if nearest is None or abs(nearest["frequency_hz"] - reference_hz) > tolerance:
                matches.append({
                    "configuration_index": config_index, "nperseg": row["nperseg"],
                    "hop": row["hop"], "nfft": row["nfft"],
                    "match_status": "NO_MATCH_WITHIN_PREDECLARED_TOLERANCE",
                    "match_tolerance_hz": float(tolerance),
                })
                continue
            bin_index = int(nearest["fft_bin_index"])
            matches.append({
                "configuration_index": config_index, "nperseg": row["nperseg"],
                "hop": row["hop"], "nfft": row["nfft"], "match_status": "MATCHED",
                "match_tolerance_hz": float(tolerance),
                "frequency_hz": nearest["frequency_hz"],
                "frequency_delta_from_baseline_hz": float(nearest["frequency_hz"] - reference_hz),
                "magnitude": nearest["magnitude"],
                "magnitude_db_relative_to_configuration_global_peak":
                    nearest["magnitude_db_relative_to_configuration_global_peak"],
                "audio_phase_consistency": _phase_at_frequency(
                    row["_z"], row["_frequencies"], bin_index, row["hop"],
                    sample_rate, row["_global_peak"],
                ),
            })
        matched = [m for m in matches if m["match_status"] == "MATCHED"]
        values = [m["frequency_hz"] for m in matched]
        tracked.append({
            "candidate_id": f"baseline_peak_{rank:02d}",
            "baseline_frequency_hz": reference_hz,
            "baseline_magnitude": reference["magnitude"],
            "baseline_magnitude_db_relative_to_configuration_global_peak":
                reference["magnitude_db_relative_to_configuration_global_peak"],
            "configuration_coverage_count": len(matched),
            "configuration_count": len(evaluated),
            "configuration_coverage_fraction": len(matched) / len(evaluated) if evaluated else 0.0,
            "frequency_drift_peak_to_peak_hz": float(max(values) - min(values)) if values else None,
            "maximum_absolute_frequency_delta_from_baseline_hz": (
                float(max(abs(m["frequency_delta_from_baseline_hz"]) for m in matched))
                if matched else None
            ),
            "matches_by_configuration": matches,
        })

    return {
        "status": "AUDIO_STFT_FREQUENCY_PEAK_ROBUSTNESS_E0",
        "verification_status": verification["status"],
        "source_sha256": verification["source_sha256"],
        "canonical_wav_sha256": verification["canonical_wav_sha256"],
        "sample_rate_hz": int(sample_rate), "sample_count": int(audio.size),
        "duration_s": float(audio.size / sample_rate),
        "analysis_band_hz": [float(min_frequency_hz), float(max_frequency_hz)],
        "peak_detection": {
            "source_of_candidates": "local maxima in mean STFT magnitude spectrum",
            "minimum_peak_level_db_relative_to_configuration_global_peak": float(min_peak_db),
            "maximum_baseline_candidates": int(max_candidates),
            "baseline_configuration": BASELINE,
            "matching_tolerance_rule": (
                "0.5 * (sample_rate_hz / baseline_nperseg + sample_rate_hz / candidate_nperseg); "
                "uses effective window resolution scales, not zero-padded FFT grid spacing"
            ),
        },
        "configurations_evaluated": len(evaluated),
        "configurations": [{
            "nperseg": row["nperseg"], "hop": row["hop"], "nfft": row["nfft"],
            "frame_count": row["frame_count"],
            "frequency_grid_spacing_hz": row["frequency_grid_spacing_hz"],
            "effective_window_resolution_scale_hz": row["effective_window_resolution_scale_hz"],
            "mean_spectrum_candidates": row["candidates"],
        } for row in evaluated],
        "tracked_baseline_peaks": tracked,
        "stability_dimensions_are_separate": {
            "frequency_peak_stability": "Coverage and frequency drift across STFT configurations; no composite score.",
            "audio_phase_consistency_stability": (
                "Per-configuration residual audio-phase concentration with explicit support; "
                "not combined with frequency drift."
            ),
        },
        "scientific_scope": {
            "evidence_domain": "audio-only numerical analysis",
            "physical_resonance_conclusion_permitted": False,
            "spatial_cymatic_field_conclusion_permitted": False,
            "hfr06_source_hash_gate": "REMAINS_CLOSED_FOR_ALTERNATE_SOURCE",
            "reason": (
                "Verified audio STFT and parameter robustness do not constitute calibrated "
                "sound-pressure, force-transfer, plate-response, or particle/contact measurements."
            ),
        },
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Track audio STFT candidate peaks across configurations.")
    parser.add_argument("--input", required=True, help="Existing HFR-02 run directory")
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    parser.add_argument("--min-frequency-hz", type=float, default=50.0)
    parser.add_argument("--max-frequency-hz", type=float, default=8000.0)
    parser.add_argument("--min-peak-db", type=float, default=DEFAULT_MIN_PEAK_DB)
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    args = parser.parse_args()
    report = analyze_frequency_peak_robustness(
        Path(args.input).resolve(), args.min_frequency_hz, args.max_frequency_hz,
        args.min_peak_db, args.max_candidates,
    )
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).resolve().write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
