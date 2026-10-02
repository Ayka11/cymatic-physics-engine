from dataclasses import dataclass

@dataclass(frozen=True)
class PublicLimits:
    max_particles: int = 10000
    max_grid: int = 256
    max_duration_sec: float = 30.0
    max_modes: int = 256

PUBLIC_LIMITS = PublicLimits()

REFERENCE_CONFIG = {
    "plate": {
        "length_x_m": 0.30, "length_y_m": 0.30, "thickness_m": 0.001,
        "material": "steel", "E_Pa": 200e9, "nu": 0.30,
        "density_kg_m3": 7850.0, "damping_ratio": 0.01,
    },
    "grid": {"nx": 256, "ny": 256},
    "modes": {"m_max": 16, "n_max": 16},
    "particles": {"count": 10000, "seed": 20260912, "dt_sec": 1/4800},
}

def validate_public_request(duration_sec, particle_count):
    duration_sec=float(duration_sec)
    particle_count=int(particle_count)
    if not 0 < duration_sec <= PUBLIC_LIMITS.max_duration_sec:
        raise ValueError(f"Duration must be in (0, {PUBLIC_LIMITS.max_duration_sec}] seconds.")
    if not 1 <= particle_count <= PUBLIC_LIMITS.max_particles:
        raise ValueError(f"Particle count must be in [1, {PUBLIC_LIMITS.max_particles}].")
    return duration_sec, particle_count
