import numpy as np

def coherence(cross_spectrum, auto_force, auto_response):
    denom = np.maximum(np.real(auto_force * auto_response), np.finfo(float).eps)
    return np.abs(cross_spectrum)**2 / denom

def phase_difference(phi_exp, phi_sim):
    d = np.asarray(phi_exp) - np.asarray(phi_sim)
    return np.arctan2(np.sin(d), np.cos(d))

def normalized_rmse(reference, estimate):
    r = np.asarray(reference, float)
    e = np.asarray(estimate, float)
    scale = np.sqrt(np.mean(r*r))
    return float(np.sqrt(np.mean((r-e)**2)) / max(scale, np.finfo(float).eps))

def complex_mac(a, b):
    a = np.asarray(a, complex).reshape(-1)
    b = np.asarray(b, complex).reshape(-1)
    num = abs(np.vdot(a, b))**2
    den = max(float(np.vdot(a,a).real * np.vdot(b,b).real), np.finfo(float).eps)
    return float(num/den)
