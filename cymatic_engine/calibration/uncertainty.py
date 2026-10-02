import numpy as np

def transfer_uncertainty(relative_response_uncertainty,
                         relative_force_uncertainty):
    ur = np.asarray(relative_response_uncertainty, float)
    uf = np.asarray(relative_force_uncertainty, float)
    return np.sqrt(ur**2 + uf**2)

def delay_phase_slope(delay_sec: float, frequency_hz):
    return -2*np.pi*np.asarray(frequency_hz)*delay_sec
