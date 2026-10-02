from dataclasses import dataclass
import hashlib
import numpy as np
from scipy.signal import istft

@dataclass(frozen=True)
class ModalTimeSeries:
    reconstruction_id: str
    modal_response_id: str
    time_sec: np.ndarray
    q: np.ndarray
    qdot: np.ndarray
    qddot: np.ndarray
    sample_rate_hz: float
    reconstruction_method: str
    derivative_method: str
    source_hash: str
    content_hash: str

def _hash_arrays(*arrays):
    h = hashlib.sha256()
    for a in arrays:
        x = np.ascontiguousarray(np.asarray(a))
        h.update(str(x.dtype).encode())
        h.update(str(x.shape).encode())
        h.update(x.tobytes())
    return h.hexdigest()

def hermitian_complete(positive_spectrum, n_fft):
    positive_spectrum = np.asarray(positive_spectrum, dtype=np.complex128)
    expected = n_fft // 2 + 1
    if positive_spectrum.shape[0] != expected:
        raise ValueError(f"Expected {expected} positive-frequency bins")
    full = np.empty((n_fft,) + positive_spectrum.shape[1:], dtype=np.complex128)
    full[:expected] = positive_spectrum
    full[expected:] = np.conj(positive_spectrum[1:-1][::-1])
    full[0] = full[0].real
    full[n_fft // 2] = full[n_fft // 2].real
    return full

def _istft(x, fs, n_fft, hop):
    t, y = istft(
        x, fs=fs, window="hann", nperseg=n_fft,
        noverlap=n_fft-hop, input_onesided=True,
        boundary=True
    )
    return t.astype(np.float64), y.astype(np.float64)

def reconstruct_modal_stft(Q_positive, fs=48000, n_fft=4096, hop=1024):
    Q_positive = np.asarray(Q_positive, dtype=np.complex128)
    if Q_positive.ndim != 3:
        raise ValueError("Q_positive must have shape (modes, frequency, frames)")
    n_modes, n_freq, _ = Q_positive.shape
    if n_freq != n_fft // 2 + 1:
        raise ValueError("Frequency dimension does not match n_fft")

    freqs_hz = np.fft.rfftfreq(n_fft, 1.0/fs)
    omega = 2*np.pi*freqs_hz

    q_list, qd_list, qdd_list = [], [], []
    time = None
    for mode in range(n_modes):
        Q = Q_positive[mode]
        time, q = _istft(Q, fs, n_fft, hop)
        _, qdot = _istft(1j*omega[:, None]*Q, fs, n_fft, hop)
        _, qddot = _istft(-(omega[:, None]**2)*Q, fs, n_fft, hop)
        q_list.append(q)
        qd_list.append(qdot)
        qdd_list.append(qddot)

    n = min(map(len, q_list))
    q = np.asarray([x[:n] for x in q_list])
    qdot = np.asarray([x[:n] for x in qd_list])
    qddot = np.asarray([x[:n] for x in qdd_list])
    time = np.arange(n, dtype=np.float64)/fs

    source_hash = _hash_arrays(Q_positive)
    content_hash = _hash_arrays(q, qdot, qddot)
    return ModalTimeSeries(
        reconstruction_id=hashlib.sha256((source_hash + "istft-hann").encode()).hexdigest(),
        modal_response_id=source_hash,
        time_sec=time, q=q, qdot=qdot, qddot=qddot,
        sample_rate_hz=float(fs),
        reconstruction_method="scipy_istft_hann",
        derivative_method="frequency_domain",
        source_hash=source_hash,
        content_hash=content_hash
    )

def reconstruction_metrics(reference, reconstructed):
    a = np.asarray(reference, dtype=np.float64).ravel()
    b = np.asarray(reconstructed, dtype=np.float64).ravel()
    n = min(a.size, b.size)
    if n == 0:
        raise ValueError("Empty signal")
    e = a[:n] - b[:n]
    rmse = float(np.sqrt(np.mean(e**2)))
    rms = float(np.sqrt(np.mean(a[:n]**2)))
    return {
        "rmse": rmse,
        "nrmse": rmse/(rms + np.finfo(float).eps),
        "peak_error": float(np.max(np.abs(e))),
        "samples_compared": int(n)
    }
