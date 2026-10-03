from __future__ import annotations

import json
from pathlib import Path

import gradio as gr
import app.adapter as adapter_module
import numpy as np
import pytest
import soundfile as sf

from app.adapter import (
    REFERENCE_MODAL_TESTS_HZ,
    generate_modal_test_wav,
    run_public_demo,
    validate_wav_bytes,
)
from app.audio.preprocess import prepare_for_cpe
from app.state import PUBLIC_LIMITS, validate_public_request
from app.ui import _csv_bytes, _generate_tone, _report, build_app


def test_public_request_limits_accept_boundaries():
    duration, particles = validate_public_request(0.01, 1)
    assert duration == pytest.approx(0.01)
    assert particles == 1

    duration, particles = validate_public_request(PUBLIC_LIMITS.max_duration_sec, PUBLIC_LIMITS.max_particles)
    assert duration == PUBLIC_LIMITS.max_duration_sec
    assert particles == PUBLIC_LIMITS.max_particles


@pytest.mark.parametrize(
    ("duration", "particles"),
    [(0, 1), (-1, 1), (PUBLIC_LIMITS.max_duration_sec + 0.01, 1), (1, 0), (1, PUBLIC_LIMITS.max_particles + 1)],
)
def test_public_request_limits_reject_invalid_values(duration, particles):
    with pytest.raises(ValueError):
        validate_public_request(duration, particles)


@pytest.mark.parametrize(
    ("duration", "particles"),
    [(float("nan"), 1), (float("inf"), 1), (1, 1.5), (1, float("nan")), (1, float("inf"))],
)
def test_public_request_limits_reject_non_finite_or_fractional_values(duration, particles):
    with pytest.raises(ValueError):
        validate_public_request(duration, particles)


def test_wav_validation_rejects_empty_and_non_wav_payloads():
    with pytest.raises(ValueError, match="No WAV file supplied"):
        validate_wav_bytes(b"")
    with pytest.raises(ValueError, match="RIFF/WAVE"):
        validate_wav_bytes(b"not a wav file")


def test_wav_validation_rejects_truncated_riff_container():
    # RIFF/WAVE magic alone is not sufficient evidence of a decodable audio file.
    with pytest.raises(ValueError, match="invalid or unsupported"):
        validate_wav_bytes(b"RIFF" + bytes(4) + b"WAVE")


def test_reference_tone_is_decodable_mono_48khz_and_provenanced():
    path, metadata = generate_modal_test_wav(REFERENCE_MODAL_TESTS_HZ["f11 — 53.318 Hz"], 0.5, 0.25)
    try:
        audio, sample_rate = sf.read(path, always_2d=True)
        assert sample_rate == 48000
        assert audio.shape[1] == 1
        assert audio.shape[0] == 24000
        assert np.max(np.abs(audio)) <= 0.251
        assert metadata["waveform"] == "sine"
        assert metadata["noise_added"] is False
        assert metadata["purpose"] == "modal_validation_test"
    finally:
        Path(path).unlink(missing_ok=True)


@pytest.mark.parametrize(
    ("frequency", "duration", "amplitude"),
    [(0, 1, 0.25), (12001, 1, 0.25), (440, 0.49, 0.25), (440, 30.1, 0.25), (440, 1, 0), (440, 1, 0.96)],
)
def test_reference_tone_rejects_invalid_parameters(frequency, duration, amplitude):
    with pytest.raises(ValueError):
        generate_modal_test_wav(frequency, duration, amplitude)


def test_audio_preprocessing_preserves_source_hash_and_emits_48khz_mono(tmp_path):
    source = tmp_path / "stereo_22050.wav"
    sample_index = np.arange(2205)
    samples = np.column_stack(
        [np.sin(2 * np.pi * 440 * sample_index / 22050),
         np.sin(2 * np.pi * 660 * sample_index / 22050)]
    ).astype(np.float32)
    sf.write(source, samples, 22050, subtype="PCM_16")

    prepared_path, prepared_info, provenance = prepare_for_cpe(source)
    try:
        prepared, rate = sf.read(prepared_path, always_2d=True)
        assert rate == 48000
        assert prepared.shape[1] == 1
        assert prepared_info.sample_rate_hz == 48000
        assert provenance["source_sha256"] == __import__("hashlib").sha256(source.read_bytes()).hexdigest()
        assert provenance["analysis_sha256"]
        assert provenance["resampled"] is True
        assert provenance["downmixed_to_mono"] is True
    finally:
        Path(prepared_path).unlink(missing_ok=True)


def test_report_and_csv_exports_include_status_and_metric_values():
    status = {
        "experiment_id": "TEST-001",
        "grapheme": "A",
        "phoneme_ipa": "/a/",
        "locale": "en",
        "input_mode": "Real audio / speech",
        "scientific_status": "COMPUTED_TEST",
        "audio_status": "test_audio",
        "acoustic_metrics": {"sample_rate_hz": 48000},
        "plate_metrics": {},
        "pattern_metrics": {"formation_steps": 10},
        "stability_metrics": {},
        "source_audio_sha256": "abc123",
    }
    report = _report(status)
    csv_text = _csv_bytes(status).decode("utf-8")
    assert "COMPUTED_TEST" in report
    assert "abc123" in report
    assert "formation_steps" in csv_text
    assert "TEST-001" in csv_text


def test_csv_export_preserves_status_provenance_nested_fields_and_negative_numbers():
    status = {
        "experiment_id": "REAL-002",
        "grapheme": "мама",
        "phoneme_ipa": "",
        "scientific_status": "COMPUTED_REDUCED_ORDER_MODEL",
        "audio_status": "processed_real_wav",
        "empirical_force_calibration": False,
        "source_audio_sha256": "source-digest",
        "analysis_audio_sha256": "analysis-digest",
        "warning": "not a measured physical response",
        "acoustic_metrics": {"duration_sec": 0.5, "minimum_sample": -0.2},
        "pattern_metrics": {"formation_steps": 1500},
        "preprocessing": {"analysis_sample_rate_hz": 48000, "channels": 1},
        "physical_measurement": {"image_analysis_status": "stored_as_experimental_record_only"},
    }
    rows = list(__import__("csv").DictReader(__import__("io").StringIO(_csv_bytes(status).decode("utf-8"))))
    values = {(row["record_group"], row["field"]): row["value"] for row in rows}
    assert values[("experiment_metadata", "scientific_status")] == "COMPUTED_REDUCED_ORDER_MODEL"
    assert values[("experiment_metadata", "source_audio_sha256")] == "source-digest"
    assert values[("experiment_metadata", "empirical_force_calibration")] == "false"
    assert values[("acoustic_metrics", "minimum_sample")] == "-0.2"
    assert values[("preprocessing", "analysis_sample_rate_hz")] == "48000"
    assert values[("physical_measurement", "image_analysis_status")] == "stored_as_experimental_record_only"


def test_csv_export_escapes_formula_like_user_strings_but_not_numeric_values():
    status = {
        "experiment_id": "CSV-SAFETY",
        "grapheme": "=HYPERLINK(\\"https://example.invalid\\")",
        "phoneme_ipa": "",
        "scientific_status": "COMPUTED_TEST",
        "acoustic_metrics": {"negative_measurement": -1.25},
    }
    text = _csv_bytes(status).decode("utf-8")
    rows = list(__import__("csv").DictReader(__import__("io").StringIO(text)))
    metadata = next(row for row in rows if row["field"] == "grapheme")
    negative = next(row for row in rows if row["field"] == "negative_measurement")
    assert metadata["value"].startswith("'=")
    assert negative["value"] == "-1.25"


def test_full_public_app_builds_with_registered_event_handlers():
    demo = build_app()
    try:
        assert isinstance(demo, gr.Blocks)
        assert len(demo.fns) >= 2, "Expected registered tone-generation and experiment handlers"
    finally:
        close = getattr(demo, "close", None)
        if callable(close):
            close()


def test_generate_tone_ui_handler_returns_audio_and_metadata():
    path, metadata_text = _generate_tone("f11 — 53.318 Hz", 0.5, 0.25)
    try:
        assert path and Path(path).is_file()
        metadata = json.loads(metadata_text)
        assert metadata["sample_rate_hz"] == 48000
        assert metadata["frequency_hz"] == pytest.approx(REFERENCE_MODAL_TESTS_HZ["f11 — 53.318 Hz"])
    finally:
        if path:
            Path(path).unlink(missing_ok=True)



def test_pure_tone_experiment_runs_end_to_end_with_scientific_guard():
    frequency = REFERENCE_MODAL_TESTS_HZ["f11 — 53.318 Hz"]
    result, status = run_public_demo(
        duration_sec=0.5,
        particle_count=64,
        grapheme="A",
        phoneme_ipa="/a/",
        locale="en",
        input_mode="Pure tone / modal validation",
        test_frequency_hz=frequency,
        tone_amplitude=0.25,
    )

    assert result["mode"] == "pure_tone_modal_validation"
    assert status["scientific_status"] == "COMPUTED_REDUCED_ORDER_MODAL_TEST"
    assert status["empirical_force_calibration"] is False
    assert "not a physical plate measurement" in status["warning"]
    assert status["modal_mode"]["requested_frequency_hz"] == pytest.approx(frequency)
    assert status["pattern_metrics"]["formation_integration_steps"] >= 1500



def test_pure_tone_temporary_wav_is_removed_when_model_fails(monkeypatch):
    original_generator = adapter_module.generate_modal_test_wav
    generated_paths = []

    def tracked_generator(*args, **kwargs):
        path, metadata = original_generator(*args, **kwargs)
        generated_paths.append(path)
        return path, metadata

    def fail_modal_run(*args, **kwargs):
        raise RuntimeError("simulated modal failure")

    monkeypatch.setattr(adapter_module, "generate_modal_test_wav", tracked_generator)
    monkeypatch.setattr(adapter_module, "_modal_test_run", fail_modal_run)

    with pytest.raises(RuntimeError, match="simulated modal failure"):
        adapter_module.run_public_demo(
            duration_sec=0.5,
            particle_count=64,
            input_mode="Pure tone / modal validation",
            test_frequency_hz=REFERENCE_MODAL_TESTS_HZ["f11 — 53.318 Hz"],
        )

    assert len(generated_paths) == 1
    assert not Path(generated_paths[0]).exists()



def _write_test_sine_wav(path: Path, sample_rate: int = 48000, duration_sec: float = 0.5):
    sample_index = np.arange(int(sample_rate * duration_sec), dtype=np.float64)
    samples = (0.2 * np.sin(2 * np.pi * 440 * sample_index / sample_rate)).astype(np.float32)
    sf.write(path, samples, sample_rate, subtype="PCM_16")
    return path


def test_real_wav_runs_end_to_end_and_preserves_scientific_limits(tmp_path):
    source = _write_test_sine_wav(tmp_path / "real_audio.wav")
    result, status = run_public_demo(
        wav_path=str(source),
        duration_sec=0.1,
        particle_count=64,
        grapheme="",
        phoneme_ipa="",
        locale="en",
        input_mode="Real audio / speech",
    )

    assert result["mode"] == "real_audio_reduced_order"
    assert status["scientific_status"] == "COMPUTED_REDUCED_ORDER_MODEL"
    assert status["audio_status"] == "processed_real_wav"
    assert status["source_audio_sha256"] == __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    assert status["analysis_audio_sha256"]
    assert status["preprocessing"]["analysis_sample_rate_hz"] == 48000
    assert status["preprocessing"]["analysis_channels"] == 1
    assert status["empirical_force_calibration"] is False
    assert "not a measured physical response" in status["warning"]
    assert status["acoustic_metrics"]["duration_sec"] == pytest.approx(0.5, abs=1 / 48000)
    assert status["pattern_metrics"]["formation_integration_steps"] >= 1500


def test_preprocessed_wav_is_removed_when_real_audio_is_too_short(tmp_path, monkeypatch):
    source = _write_test_sine_wav(tmp_path / "short_audio.wav", duration_sec=0.2)
    original_prepare = adapter_module.prepare_for_cpe
    prepared_paths = []

    def tracked_prepare(*args, **kwargs):
        path, info, provenance = original_prepare(*args, **kwargs)
        prepared_paths.append(path)
        return path, info, provenance

    monkeypatch.setattr(adapter_module, "prepare_for_cpe", tracked_prepare)

    with pytest.raises(ValueError, match="shorter than requested"):
        run_public_demo(
            wav_path=str(source),
            duration_sec=0.4,
            particle_count=64,
            input_mode="Real audio / speech",
        )

    assert len(prepared_paths) == 1
    assert not Path(prepared_paths[0]).exists()


def test_malformed_wav_is_rejected_before_real_audio_pipeline(tmp_path, monkeypatch):
    malformed = tmp_path / "malformed.wav"
    malformed.write_bytes(b"RIFF" + bytes(4) + b"WAVE")
    called = False

    def forbidden_pipeline(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("real audio pipeline must not run for malformed WAV")

    monkeypatch.setattr(adapter_module, "_real_audio_run", forbidden_pipeline)

    with pytest.raises(ValueError, match="invalid or unsupported"):
        run_public_demo(wav_path=str(malformed), duration_sec=0.1, particle_count=64)

    assert called is False
