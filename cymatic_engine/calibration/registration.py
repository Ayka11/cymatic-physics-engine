import numpy as np

def normalize_mode_shape(mode):
    x = np.asarray(mode, complex)
    n = np.sqrt(np.vdot(x, x).real)
    if n == 0:
        raise ValueError("Mode shape has zero norm.")
    return x / n

def align_phase(reference, measured):
    r = normalize_mode_shape(reference)
    m = normalize_mode_shape(measured)
    phase = np.angle(np.vdot(m, r))
    return m * np.exp(1j*phase)
