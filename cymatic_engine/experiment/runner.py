import numpy as np
from scipy.signal import find_peaks
from .sync import synchronize_channels
from cymatic_engine.calibration.modal_measurement import estimate_frf
from .models import MeasurementRecord, ExperimentResult

# Backward-compatible synthetic reference API retained from v1.9.
from .runner_legacy_impl import ExperimentManifest, run_synthetic_reference

def run_experiment_analysis(force, response, sample_rate_hz, manifest,
                            nperseg=4096, peak_prominence=None):
    f, h, coh = estimate_frf(force, response, sample_rate_hz, nperseg=nperseg)
    mag = np.abs(h)
    if peak_prominence is None:
        peak_prominence = max(float(np.max(mag))*0.05, np.finfo(float).eps)
    peaks, _ = find_peaks(mag, prominence=peak_prominence)
    warnings = []
    if len(peaks) == 0:
        warnings.append("No FRF peak detected at configured prominence.")
    if np.any(coh < 0.5):
        warnings.append("Some frequency bins have coherence below 0.5.")
    return ExperimentResult(
        frequency_hz=f, frf=h, coherence=coh,
        peak_frequencies_hz=f[peaks], delay_sec=0.0,
        metrics={"max_coherence": float(np.max(coh)), "median_coherence": float(np.median(coh))},
        warnings=tuple(warnings), manifest_hash=manifest.content_hash()
    )
