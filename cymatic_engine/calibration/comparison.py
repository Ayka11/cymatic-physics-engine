import numpy as np
from .metrics import normalized_rmse, complex_mac, phase_difference

def compare_frf(exp_h, sim_h):
    exp_h = np.asarray(exp_h, complex)
    sim_h = np.asarray(sim_h, complex)
    amp_rmse = normalized_rmse(np.abs(exp_h), np.abs(sim_h))
    phase_rmse = normalized_rmse(np.unwrap(np.angle(exp_h)),
                                 np.unwrap(np.angle(sim_h)))
    return {"amplitude_nrmse": amp_rmse, "phase_nrmse": phase_rmse}

def compare_mode_shapes(exp_mode, sim_mode):
    return {"complex_mac": complex_mac(exp_mode, sim_mode)}
