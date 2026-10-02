from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class PlateFieldResult:
    x_m: np.ndarray
    y_m: np.ndarray
    displacement_rms: np.ndarray
    velocity_rms: np.ndarray
    acceleration_rms: np.ndarray
    displacement_last: np.ndarray
    metadata: dict

def reconstruct_field(plate, q, qdot, qddot, nx=128, ny=128, frame_stride=1):
    q = np.asarray(q, dtype=np.float64)
    qdot = np.asarray(qdot, dtype=np.float64)
    qddot = np.asarray(qddot, dtype=np.float64)
    if q.ndim != 2 or qdot.shape != q.shape or qddot.shape != q.shape:
        raise ValueError("q, qdot and qddot must have identical shape (modes, time)")
    expected_modes = plate.n_modes_x * plate.n_modes_y
    if q.shape[0] != expected_modes:
        raise ValueError("Mode count mismatch")
    if frame_stride < 1:
        raise ValueError("frame_stride must be >= 1")

    x = np.linspace(0, plate.length_x_m, nx)
    y = np.linspace(0, plate.length_y_m, ny)
    sx = np.sin(np.arange(1, plate.n_modes_x+1)[:, None] *
                np.pi*x[None, :]/plate.length_x_m)
    sy = np.sin(np.arange(1, plate.n_modes_y+1)[:, None] *
                np.pi*y[None, :]/plate.length_y_m)

    z2 = np.zeros((ny, nx), dtype=np.float64)
    v2 = np.zeros_like(z2)
    a2 = np.zeros_like(z2)
    last = np.zeros_like(z2)
    used = 0

    for k in range(0, q.shape[1], frame_stride):
        Q = q[:, k].reshape(plate.n_modes_x, plate.n_modes_y)
        V = qdot[:, k].reshape(plate.n_modes_x, plate.n_modes_y)
        A = qddot[:, k].reshape(plate.n_modes_x, plate.n_modes_y)
        z = sx.T @ Q @ sy
        v = sx.T @ V @ sy
        a = sx.T @ A @ sy
        z2 += z*z
        v2 += v*v
        a2 += a*a
        last = z
        used += 1

    used = max(used, 1)
    return PlateFieldResult(
        x_m=x, y_m=y,
        displacement_rms=np.sqrt(z2/used),
        velocity_rms=np.sqrt(v2/used),
        acceleration_rms=np.sqrt(a2/used),
        displacement_last=last,
        metadata={
            "grid": [nx, ny],
            "frame_stride": frame_stride,
            "frames_used": used,
            "basis": "separable_sin_sin",
            "energy_field_type": "displacement_rms_squared_proxy"
        }
    )
