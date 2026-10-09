from dataclasses import replace
import hashlib

import numpy as np

from cymatic_engine.audio.profile import profile_from_samples
from cymatic_engine.physics.audio_to_modal import (
    gaussian_coupling,
    prescribed_audio_modal_response,
)
from cymatic_engine.physics.modal import PlateModel


def _test_profile(global_phase_rad: float = 0.0):
    sample_rate = 48000
    sample_index = np.arange(4096, dtype=np.float64)
    samples = 0.2 * np.sin(2 * np.pi * 440.0 * sample_index / sample_rate)
    # This digest identifies only the deterministic in-memory test fixture,
    # not an experimental WAV file.
    fixture_hash = hashlib.sha256(
        np.asarray(samples, dtype="<f8").tobytes()
    ).hexdigest()
    profile = profile_from_samples(
        samples,
        sample_rate,
        fixture_hash,
        n_fft=1024,
        hop=256,
    )
    if global_phase_rad == 0.0:
        return profile
    rotated = profile.stft_complex * np.exp(1j * global_phase_rad)
    return replace(
        profile,
        stft_complex=rotated,
        magnitude=np.abs(rotated),
        phase=np.angle(rotated),
    )


def test_gaussian_coupling_is_finite_and_deterministic_with_supported_quadrature():
    plate = PlateModel(n_modes_x=1, n_modes_y=1)
    args = (plate, 1, 1)
    first = gaussian_coupling(*args, nx=64, ny=64)
    second = gaussian_coupling(*args, nx=64, ny=64)

    assert np.isfinite(first)
    assert first != 0.0
    assert first == second


def test_modal_response_hash_is_deterministic_and_global_phase_equivariant():
    plate = PlateModel(n_modes_x=1, n_modes_y=1)
    profile = _test_profile()
    response_a = prescribed_audio_modal_response(profile, plate)
    response_b = prescribed_audio_modal_response(profile, plate)

    assert response_a.response_hash == response_b.response_hash
    assert np.isfinite(response_a.Q_positive.real).all()
    assert np.isfinite(response_a.Q_positive.imag).all()

    phase_shift_rad = 0.37
    shifted_profile = _test_profile(phase_shift_rad)
    shifted_response = prescribed_audio_modal_response(shifted_profile, plate)
    expected = response_a.Q_positive * np.exp(1j * phase_shift_rad)

    np.testing.assert_allclose(
        shifted_response.Q_positive,
        expected,
        rtol=1e-12,
        atol=1e-14,
    )
    assert shifted_response.response_hash != response_a.response_hash
    assert response_a.metadata["physical_status"] == "reduced_order_model"
    assert response_a.metadata["empirical_force_calibration"] is False
