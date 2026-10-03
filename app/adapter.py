from app.audio.preprocess import prepare_for_cpe
import hashlib, io, json, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

from cymatic_engine.experiment.runner import run_synthetic_reference
from cymatic_engine.audio.profile import read_wav, profile_from_samples
from cymatic_engine.physics.modal import PlateModel
from cymatic_engine.physics.audio_to_modal import prescribed_audio_modal_response
from cymatic_engine.physics.reconstruction import reconstruct_modal_stft
from cymatic_engine.physics.plate_sequence import reconstruct_sequence
from cymatic_engine.particles.dynamics import ParticleConfig, run_particle_sequence, run_particles_on_intensity
from cymatic_engine.analysis.stability import analyze_stability
from cymatic_engine.analysis.signature import cymatic_signature
from .state import REFERENCE_CONFIG, validate_public_request




# Reference modal frequencies for the fixed 0.30 m × 0.30 m steel plate.
# These are protocol values calculated from the reference plate model; they are
# not universal frequencies and should be re-derived if the plate changes.
REFERENCE_MODAL_TESTS_HZ = {
    "f11 — 53.318 Hz": 53.31829013,
    "f12 — 133.296 Hz": 133.29572533,
    "f22 — 213.273 Hz": 213.27316100,
    "f13 — 266.591 Hz": 266.59145065,
    "f23 — 346.569 Hz": 346.56888585,
    "f14 — 453.205 Hz": 453.20546611,
    "f24 — 533.183 Hz": 533.18290130,
}


def generate_modal_test_wav(frequency_hz, duration_sec, amplitude=0.25, fade_sec=0.5):
    """Generate a clean 48 kHz mono sine test signal for modal validation."""
    frequency_hz = float(frequency_hz)
    duration_sec = float(duration_sec)
    amplitude = float(amplitude)
    if not 1.0 <= frequency_hz <= 12000.0:
        raise ValueError("Test-tone frequency must be between 1 and 12000 Hz.")
    if not 0.5 <= duration_sec <= 30.0:
        raise ValueError("Test-tone duration must be between 0.5 and 30 seconds.")
    if not 0.0 < amplitude <= 0.95:
        raise ValueError("Test-tone amplitude must be in (0, 0.95].")
    fs = 48000
    n = max(1, int(round(duration_sec * fs)))
    t = np.arange(n, dtype=np.float64) / fs
    samples = amplitude * np.sin(2.0 * np.pi * frequency_hz * t)
    fade_n = min(int(round(fade_sec * fs)), n // 2)
    if fade_n > 0:
        ramp = np.linspace(0.0, 1.0, fade_n, endpoint=True)
        samples[:fade_n] *= ramp
        samples[-fade_n:] *= ramp[::-1]
    path = tempfile.NamedTemporaryFile(prefix="cpe_modal_test_", suffix=".wav", delete=False).name
    sf.write(path, samples.astype(np.float32), fs, subtype="PCM_24")
    return path, {
        "waveform": "sine",
        "frequency_hz": frequency_hz,
        "amplitude_peak": amplitude,
        "sample_rate_hz": fs,
        "channels": 1,
        "duration_sec": duration_sec,
        "fade_in_sec": min(fade_sec, duration_sec / 2.0),
        "fade_out_sec": min(fade_sec, duration_sec / 2.0),
        "noise_added": False,
        "purpose": "modal_validation_test",
    }


def _modal_test_run(frequency_hz, duration_sec, particle_count, amplitude=0.25):
    """Direct analytical modal validation path for the fixed reference plate.

    This bypasses the expensive full audio STFT→256-mode reconstruction because a
    pure-tone modal test has an analytically known spatial field. It is a validation
    test of the plate-mode geometry and particle accumulation proxy, not a physical
    measurement.
    """
    plate = _plate()
    best = None
    for m in range(1, plate.n_modes_x + 1):
        for n in range(1, plate.n_modes_y + 1):
            fn = __import__("cymatic_engine.physics.modal", fromlist=["modal_frequency_hz"]).modal_frequency_hz(plate, m, n)
            err = abs(fn - float(frequency_hz))
            if best is None or err < best[0]:
                best = (err, m, n, fn)
    _, m, n, matched_f = best
    nx = ny = 128
    x = np.linspace(0, plate.length_x_m, nx)
    y = np.linspace(0, plate.length_y_m, ny)
    X, Y = np.meshgrid(x, y, indexing="xy")
    phi = np.sin(m*np.pi*X/plate.length_x_m) * np.sin(n*np.pi*Y/plate.length_y_m)
    # Acceleration amplitude is proportional to omega^2 * modal amplitude. For
    # particle accumulation only its spatial intensity matters, so use phi^2.
    intensity = (phi / (np.max(np.abs(phi)) + 1e-15)) ** 2
    pconf = ParticleConfig(
        particle_count=particle_count, seed=REFERENCE_CONFIG["particles"]["seed"],
        dt_sec=1/2400, density_nx=128, density_ny=128, gamma=2.5
    )
    integration_time = max(1.5, min(float(duration_sec), 5.0))
    steps = max(1500, min(4000, int(round(integration_time * 1000))))
    particle_result, density_history = run_particles_on_intensity(
        intensity, pconf, integration_time_sec=integration_time, steps=steps,
        force_scale=0.15, damping=2.5, history_points=24
    )
    stability = analyze_stability(density_history, dt_sec=integration_time/max(1,len(density_history)))
    sig = cymatic_signature(particle_result.density, stability)
    return {
        "mode": "pure_tone_modal_validation",
        "particle_result": particle_result,
        "density_sequence": density_history,
        "stability": stability,
        "signature": sig,
        "modal_mode": {"m": m, "n": n, "frequency_hz": float(matched_f),
                        "requested_frequency_hz": float(frequency_hz),
                        "frequency_error_hz": float(abs(matched_f-frequency_hz))},
        "pattern_metrics": {
            "formation_model": "analytical_modal_intensity_gradient_drift",
            "mode_m": int(m), "mode_n": int(n),
            "formation_integration_steps": int(steps),
            "formation_integration_time_sec": float(integration_time),
        },
        "plate_metrics": {
            "mode_frequency_hz": float(matched_f),
            "requested_frequency_hz": float(frequency_hz),
            "frequency_error_hz": float(abs(matched_f-frequency_hz)),
            "field_peak_normalized": float(np.max(intensity)),
        },
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_wav_bytes(data: bytes):
    if not data:
        raise ValueError("No WAV file supplied.")
    if len(data) > 50 * 1024 * 1024:
        raise ValueError("WAV file exceeds the 50 MB public limit.")
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Input must be a RIFF/WAVE file.")

    # Check that the payload is actually decodable before accepting its hash.
    # The later preprocessing step uses the same libsndfile decoding path.
    try:
        info = sf.info(io.BytesIO(data))
    except Exception as exc:
        raise ValueError("WAV container is invalid or unsupported.") from exc
    if str(info.format).upper() != "WAV" or info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0:
        raise ValueError("WAV container is invalid or unsupported.")

    return {
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "sample_rate_hz": int(info.samplerate),
        "channels": int(info.channels),
        "frames": int(info.frames),
        "duration_sec": float(info.duration),
        "subtype": str(info.subtype or ""),
    }


def _plate():
    return PlateModel(
        length_x_m=REFERENCE_CONFIG["plate"]["length_x_m"],
        length_y_m=REFERENCE_CONFIG["plate"]["length_y_m"],
        thickness_m=REFERENCE_CONFIG["plate"]["thickness_m"],
        damping_ratio=REFERENCE_CONFIG["plate"]["damping_ratio"],
        n_modes_x=REFERENCE_CONFIG["modes"]["m_max"],
        n_modes_y=REFERENCE_CONFIG["modes"]["n_max"],
    )


def _real_audio_run(wav_path, duration_sec, particle_count):
    # Explicit preprocessing boundary: the raw upload is never overwritten.
    # Supported WAV inputs are converted to the fixed 48 kHz PCM analysis format,
    # with source/analysis hashes retained for provenance.
    analysis_path, analysis_info, preprocessing = prepare_for_cpe(
        wav_path, target_rate=48000, mono=True
    )
    # Consume the explicitly preprocessed PCM samples directly. This prevents
    # the original non-48-kHz upload from reaching the strict CPE reader.
    processed_audio, processed_fs = __import__("soundfile").read(
        analysis_path, always_2d=True, dtype="float64"
    )
    processed_mono = np.mean(processed_audio, axis=1)
    audio = profile_from_samples(
        processed_mono, processed_fs,
        source_hash=preprocessing["analysis_sha256"],
        channels=1, n_fft=4096, hop=1024,
    )
    if audio.duration_sec < duration_sec:
        raise ValueError(f"WAV duration {audio.duration_sec:.3f}s is shorter than requested {duration_sec:.3f}s")
    plate = _plate()
    response = prescribed_audio_modal_response(audio, plate)
    ts = reconstruct_modal_stft(response.Q_positive, fs=48000, n_fft=4096, hop=1024)
    plate_seq = reconstruct_sequence(plate, ts, nx=64, ny=64, max_frames=120)
    # FIX-CPE-001: the previous implementation advanced particles only once per
    # sparse plate frame while using the 1/4800 s acoustic/physics timestep.
    # A 120-frame sequence therefore integrated for only ~25 ms regardless of a
    # multi-second recording, so particles barely moved and the final density
    # remained close to the identical random initialization.
    #
    # Cymatic accumulation is instead driven here by the time-averaged vibration
    # intensity I(x,y)=mean(a(x,y,t)^2) over the central steady portion. Particle
    # drift is then integrated on its own slower pattern-formation clock.
    acc = np.asarray(plate_seq.acceleration, dtype=np.float64)
    if acc.ndim != 3 or acc.shape[0] < 2:
        raise ValueError("Insufficient plate acceleration frames for pattern formation")
    n_frames = acc.shape[0]
    start = int(0.20 * n_frames)
    end = max(start + 1, int(0.90 * n_frames))
    intensity = np.mean(acc[start:end] ** 2, axis=0)
    pconf = ParticleConfig(
        particle_count=particle_count,
        seed=REFERENCE_CONFIG["particles"]["seed"],
        dt_sec=1 / 2400,
        density_nx=128,
        density_ny=128,
        gamma=2.5,
    )
    integration_time = max(1.5, min(float(duration_sec), 5.0))
    steps = max(1500, min(4000, int(round(integration_time * 1000))))
    particle_result, density_history = run_particles_on_intensity(
        intensity, pconf, integration_time_sec=integration_time, steps=steps,
        force_scale=0.15, damping=2.5, history_points=24
    )
    density_seq = np.asarray(density_history, dtype=np.float64)
    stability = analyze_stability(
        density_seq,
        dt_sec=integration_time / max(1, len(density_seq) - 1),
    )
    sig = cymatic_signature(density_seq[-1], stability)
    # Standard experiment metrics are derived from the actual run; no synthetic
    # phoneme/letter values are inserted.
    final_density = np.asarray(density_seq[-1], dtype=float)
    disp = np.asarray(plate_seq.displacement, dtype=float)
    acc = np.asarray(plate_seq.acceleration, dtype=float)
    freq = np.asarray(audio.frequency_hz, dtype=float)
    mag = np.asarray(audio.magnitude, dtype=float)
    if mag.ndim == 2:
        mag = np.mean(mag, axis=1)
    peak_idx = np.argsort(mag)[-5:][::-1] if mag.size else np.array([], dtype=int)
    acoustic_metrics = {
        "sample_rate_hz": float(audio.sample_rate_hz),
        "duration_sec": float(audio.duration_sec),
        "rms": float(audio.rms),
        "peak": float(audio.peak),
        "clipping_fraction": float(audio.clipping_fraction),
        "silence_fraction": float(audio.silence_fraction),
        "dominant_frequencies_hz": [float(freq[i]) for i in peak_idx],
    }
    plate_metrics = {
        "displacement_rms_model_units": float(np.sqrt(np.mean(disp**2))),
        "displacement_peak_model_units": float(np.max(np.abs(disp))),
        "acceleration_rms_model_units": float(np.sqrt(np.mean(acc**2))),
        "acceleration_peak_model_units": float(np.max(np.abs(acc))),
        "sampled_frames": int(disp.shape[0]),
    }
    p = np.maximum(final_density, 0.0); p = p / (p.sum() + 1e-15)
    yy, xx = np.indices(p.shape, dtype=float)
    pattern_metrics = {
        "density_sum": float(final_density.sum()),
        "density_max": float(final_density.max()) if final_density.size else 0.0,
        "centroid_x_grid": float((xx*p).sum()),
        "centroid_y_grid": float((yy*p).sum()),
        "signature_dimension": int(len(sig)),
        "formation_model": "time_averaged_intensity_gradient_drift",
        "formation_frames_used": int(end - start),
        "formation_integration_steps": int(steps),
        "formation_integration_time_sec": float(integration_time),
    }
    D = np.asarray(stability.frame_distance, dtype=float); C = np.asarray(stability.correlation, dtype=float)
    stability_metrics = {
        "state": stability.state,
        "mean_frame_distance_tail": float(np.mean(D[-10:])) if D.size else 0.0,
        "final_frame_distance": float(D[-1]) if D.size else 0.0,
        "mean_correlation_tail": float(np.mean(C[-10:])) if C.size else 1.0,
        "final_correlation": float(C[-1]) if C.size else 1.0,
        "convergence_time_sec": stability.convergence_time_sec,
    }
    return {
        "mode": "real_audio_reduced_order",
        "audio_profile": audio,
        "modal_response": response,
        "modal_time_series": ts,
        "plate_sequence": plate_seq,
        "particle_result": particle_result,
        "density_sequence": density_seq,
        "stability": stability,
        "signature": sig,
        "preprocessing": preprocessing,
        "acoustic_metrics": acoustic_metrics,
        "plate_metrics": plate_metrics,
        "pattern_metrics": pattern_metrics,
        "stability_metrics": stability_metrics,
    }


def _status_for_real(result, wav_meta, preprocessing, particle_count):
    sig = result["signature"]
    return {
        "experiment_id": "REAL-AUDIO-REDUCED-ORDER",
        "scientific_status": "COMPUTED_REDUCED_ORDER_MODEL",
        "audio_status": "processed_real_wav",
        "audio": wav_meta,
        "preprocessing": preprocessing,
        "audio_profile_hash": result["audio_profile"].source_hash,
        "modal_response_hash": result["modal_response"].response_hash,
        "modal_time_series_hash": result["modal_time_series"].content_hash,
        "plate_frames": int(result["plate_sequence"].displacement.shape[0]),
        "particle_count": particle_count,
        "signature_hash": hashlib.sha256(np.ascontiguousarray(np.asarray(sig, dtype=np.float64)).tobytes()).hexdigest(),
        "excitation_model": "audio_spectrum_prescribed_to_plate",
        "empirical_force_calibration": False,
        "warning": "Real WAV is processed through the computational pipeline, but CAL-006/007 acoustic-to-force calibration is not complete; this is not a measured physical response.",
        "source_audio_sha256": wav_meta.get("sha256"),
        "analysis_audio_sha256": preprocessing.get("analysis_sha256"),
        "acoustic_metrics": result.get("acoustic_metrics", {}),
        "plate_metrics": result.get("plate_metrics", {}),
        "pattern_metrics": result.get("pattern_metrics", {}),
        "stability_metrics": result.get("stability_metrics", {}),
    }


def run_public_demo(wav_path=None, duration_sec=0.10, particle_count=10000, grapheme="", phoneme_ipa="", locale="", input_mode="Real audio", test_frequency_hz=None, tone_amplitude=0.25):
    duration_sec, particle_count = validate_public_request(duration_sec, particle_count)
    generated_test = None
    if input_mode == "Pure tone / modal validation":
        if test_frequency_hz is None:
            raise ValueError("Select a modal test frequency.")
        wav_path, generated_test = generate_modal_test_wav(test_frequency_hz, duration_sec, tone_amplitude)
        result = _modal_test_run(test_frequency_hz, duration_sec, particle_count, tone_amplitude)
        status = {
            "experiment_id": "PURE-TONE-MODAL-VALIDATION",
            "scientific_status": "COMPUTED_REDUCED_ORDER_MODAL_TEST",
            "audio_status": "generated_pure_tone",
            "reference_configuration": REFERENCE_CONFIG,
            "generated_test_signal": generated_test,
            "modal_mode": result["modal_mode"],
            "plate_metrics": result["plate_metrics"],
            "pattern_metrics": result["pattern_metrics"],
            "stability_metrics": {
                "state": result["stability"].state,
                "final_frame_distance": float(result["stability"].frame_distance[-1]) if len(result["stability"].frame_distance) else 0.0,
                "final_correlation": float(result["stability"].correlation[-1]) if len(result["stability"].correlation) else 1.0,
                "convergence_time_sec": result["stability"].convergence_time_sec,
            },
            "signature_hash": hashlib.sha256(np.ascontiguousarray(np.asarray(result["signature"],dtype=np.float64)).tobytes()).hexdigest(),
            "excitation_model": "analytical_modal_field",
            "empirical_force_calibration": False,
            "warning": "Analytical pure-tone/modal validation of the reference plate model; not a physical plate measurement and not evidence of a phoneme-to-glyph mapping.",
        }
        return result, status
    if not wav_path:
        result = run_synthetic_reference(
            duration_sec=duration_sec,
            particle_count=particle_count,
            seed=REFERENCE_CONFIG["particles"]["seed"],
        )
        m = result["manifest"]
        status = {
            "experiment_id": m.experiment_id,
            "scientific_status": m.scientific_status,
            "audio_status": "not_supplied",
            "reference_configuration": REFERENCE_CONFIG,
            "config_hash": m.config_hash,
            "content_hash": m.content_hash,
            "provenance_hash": m.provenance_hash,
            "warnings": list(m.warnings),
        }
        return result, status
    data = Path(wav_path).read_bytes()
    wav_meta = validate_wav_bytes(data)
    result = _real_audio_run(wav_path, duration_sec, particle_count)
    # The analysis hash belongs to the explicitly preprocessed audio, while
    # wav_meta retains the original upload hash.
    status = _status_for_real(result, wav_meta, result.get("preprocessing", {}), particle_count)
    status["input_mode"] = input_mode
    if generated_test is not None:
        status["generated_test_signal"] = generated_test
        status["scientific_status"] = "COMPUTED_REDUCED_ORDER_MODAL_TEST"
        status["warning"] = (
            "This is a computational pure-tone/modal validation test. The frequency is matched to the reference plate model, "
            "but the result is not a measured physical plate response and does not establish a phoneme-to-pattern mapping."
        )
    return result, status
