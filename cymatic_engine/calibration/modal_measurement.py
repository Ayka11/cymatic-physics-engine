import numpy as np

def estimate_frf(force, response, sample_rate_hz, nperseg=4096):
    from scipy.signal import csd, welch
    f, pff = welch(force, fs=sample_rate_hz, nperseg=nperseg)
    _, pfr = csd(force, response, fs=sample_rate_hz, nperseg=nperseg)
    _, prr = welch(response, fs=sample_rate_hz, nperseg=nperseg)
    h1 = pfr / np.maximum(pff, np.finfo(float).eps)
    coh = np.abs(pfr)**2 / np.maximum(pff*prr, np.finfo(float).eps)
    return f, h1, coh
