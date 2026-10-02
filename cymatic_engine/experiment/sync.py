import numpy as np
from scipy.signal import correlate

def estimate_delay(reference, measured, sample_rate_hz):
    a = np.asarray(reference,float) - np.mean(reference)
    b = np.asarray(measured,float) - np.mean(measured)
    c = correlate(b, a, mode="full")
    lag = int(np.argmax(c) - (len(a)-1))
    return lag / float(sample_rate_hz)

def synchronize_channels(reference, measured, sample_rate_hz, max_delay_sec=0.1):
    delay = estimate_delay(reference, measured, sample_rate_hz)
    if abs(delay) > max_delay_sec:
        raise ValueError("Estimated channel delay exceeds configured safety bound.")
    n = min(len(reference), len(measured))
    ref = np.asarray(reference)[:n]
    mea = np.asarray(measured)[:n]
    shift = int(round(delay*sample_rate_hz))
    if shift > 0:
        ref, mea = ref[shift:], mea[:len(ref)-shift]
    elif shift < 0:
        mea, ref = mea[-shift:], ref[:len(mea)+shift]
    return ref, mea, delay
