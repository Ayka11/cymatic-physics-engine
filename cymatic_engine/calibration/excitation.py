import numpy as np

def linear_sweep(start_hz: float, stop_hz: float, duration_sec: float,
                 sample_rate_hz: int = 48000) -> tuple[np.ndarray, np.ndarray]:
    n = int(round(duration_sec * sample_rate_hz))
    t = np.arange(n) / sample_rate_hz
    phase = 2*np.pi*(start_hz*t + (stop_hz-start_hz)*t*t/(2*duration_sec))
    return t, np.sin(phase)

def stepped_sine(frequencies_hz, duration_sec: float,
                 sample_rate_hz: int = 48000):
    frequencies_hz = np.asarray(frequencies_hz, dtype=float)
    n = int(round(duration_sec * sample_rate_hz))
    blocks = [np.sin(2*np.pi*f*np.arange(n)/sample_rate_hz) for f in frequencies_hz]
    return np.concatenate(blocks)
