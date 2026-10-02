from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class ParticleConfig:
    particle_count: int = 10000
    seed: int = 20260912
    dt_sec: float = 1.0/4800.0
    alpha: float = 1.0
    gamma: float = 0.0
    restitution: float = 0.5
    density_nx: int = 128
    density_ny: int = 128
    boundary_model: str = "reflective"
    store_trajectories: bool = False

@dataclass(frozen=True)
class ParticleResult:
    positions: np.ndarray
    velocities: np.ndarray
    density: np.ndarray
    metadata: dict
    trajectories: np.ndarray | None = None

def _bilinear(field, x, y, lx, ly):
    ny,nx=field.shape
    fx=np.clip(x/lx*(nx-1),0,nx-1)
    fy=np.clip(y/ly*(ny-1),0,ny-1)
    x0=np.floor(fx).astype(np.int64); y0=np.floor(fy).astype(np.int64)
    x1=np.minimum(x0+1,nx-1); y1=np.minimum(y0+1,ny-1)
    tx=fx-x0; ty=fy-y0
    return ((1-tx)*(1-ty)*field[y0,x0]+tx*(1-ty)*field[y0,x1]+
            (1-tx)*ty*field[y1,x0]+tx*ty*field[y1,x1])

def field_gradient(field,lx,ly):
    field=np.asarray(field,dtype=np.float64)
    gy,gx=np.gradient(field,ly/(field.shape[0]-1),lx/(field.shape[1]-1),edge_order=1)
    return gx,gy

def run_particles(field,config=None,lx=0.30,ly=0.30,steps=100):
    config=config or ParticleConfig()
    if config.particle_count<1 or config.dt_sec<=0: raise ValueError("Invalid particle configuration")
    field=np.asarray(field,dtype=np.float64)
    if field.ndim!=2 or not np.isfinite(field).all(): raise ValueError("Field must be finite 2-D")
    rng=np.random.default_rng(config.seed)
    pos=rng.uniform([0,0],[lx,ly],size=(config.particle_count,2)).astype(np.float64)
    vel=np.zeros_like(pos)
    gx,gy=field_gradient(field,lx,ly)
    traj=np.empty((steps+1,config.particle_count,2),dtype=np.float64) if config.store_trajectories else None
    if traj is not None: traj[0]=pos

    for k in range(steps):
        fx=_bilinear(gx,pos[:,0],pos[:,1],lx,ly)
        fy=_bilinear(gy,pos[:,0],pos[:,1],lx,ly)
        acc=-config.alpha*np.column_stack((fx,fy))-config.gamma*vel
        vel += acc*config.dt_sec
        pos += vel*config.dt_sec
        if config.boundary_model=="reflective":
            for axis,L in ((0,lx),(1,ly)):
                lo=pos[:,axis]<0; hi=pos[:,axis]>L
                pos[lo,axis]=-pos[lo,axis]; vel[lo,axis]*=-config.restitution
                pos[hi,axis]=2*L-pos[hi,axis]; vel[hi,axis]*=-config.restitution
        elif config.boundary_model=="clamp":
            pos=np.clip(pos,[0,0],[lx,ly])
            vel[(pos[:,0]<=0)|(pos[:,0]>=lx),0]=0
            vel[(pos[:,1]<=0)|(pos[:,1]>=ly),1]=0
        else: raise ValueError("Unknown boundary_model")
        if not np.isfinite(pos).all() or not np.isfinite(vel).all(): raise FloatingPointError("Non-finite particle state")
        if traj is not None: traj[k+1]=pos

    density,_,_=np.histogram2d(pos[:,1],pos[:,0],
        bins=(config.density_ny,config.density_nx),range=((0,ly),(0,lx)))
    return ParticleResult(pos,vel,density.astype(np.float64),
        {"particle_count":config.particle_count,"seed":config.seed,"dt_sec":config.dt_sec,
         "steps":steps,"boundary_model":config.boundary_model,
         "interaction_model":"none","model_status":"reduced_order_model"},
        traj)

def particle_count_conservation(result,expected_count):
    return {"expected":int(expected_count),"observed":int(result.density.sum()),
            "passed":int(result.density.sum())==int(expected_count)}

def run_particle_sequence(fields, config=None, lx=0.30, ly=0.30, dt_sec=None):
    """Propagate one particle ensemble through a time-ordered field sequence.

    The input fields are computational acceleration/energy proxies. This remains a
    reduced-order particle model until CAL-004 physically identifies contact/friction.
    """
    config=config or ParticleConfig()
    fields=np.asarray(fields,dtype=np.float64)
    if fields.ndim != 3 or not np.isfinite(fields).all():
        raise ValueError("fields must be finite with shape (frames, ny, nx)")
    rng=np.random.default_rng(config.seed)
    pos=rng.uniform([0,0],[lx,ly],size=(config.particle_count,2)).astype(np.float64)
    vel=np.zeros_like(pos)
    dt=float(dt_sec if dt_sec is not None else config.dt_sec)
    densities=[]
    for field in fields:
        gx,gy=field_gradient(field,lx,ly)
        fx=_bilinear(gx,pos[:,0],pos[:,1],lx,ly)
        fy=_bilinear(gy,pos[:,0],pos[:,1],lx,ly)
        acc=-config.alpha*np.column_stack((fx,fy))-config.gamma*vel
        vel += acc*dt
        pos += vel*dt
        for axis,L in ((0,lx),(1,ly)):
            lo=pos[:,axis]<0; hi=pos[:,axis]>L
            pos[lo,axis]=-pos[lo,axis]; vel[lo,axis]*=-config.restitution
            pos[hi,axis]=2*L-pos[hi,axis]; vel[hi,axis]*=-config.restitution
        density,_,_=np.histogram2d(pos[:,1],pos[:,0],
            bins=(config.density_ny,config.density_nx),range=((0,ly),(0,lx)))
        densities.append(density.astype(np.float64))
    density=np.asarray(densities)
    return ParticleResult(pos,vel,density[-1],
        {"particle_count":config.particle_count,"seed":config.seed,"dt_sec":dt,
         "steps":len(fields),"boundary_model":config.boundary_model,
         "interaction_model":"none","model_status":"reduced_order_model",
         "sequence_mode":True}, None), density


def run_particles_on_intensity(intensity_field, config=None, lx=0.30, ly=0.30,
                               integration_time_sec=3.0, steps=3000,
                               force_scale=0.15, damping=2.5, history_points=24):
    """Compute a time-averaged cymatic accumulation pattern.

    The field is interpreted as vibration intensity (e.g. mean acceleration^2),
    not as an instantaneous mechanical force. Particles drift down the spatial
    intensity gradient toward low-vibration/nodal regions. This is a reduced-order
    proxy for cymatic accumulation; it is intentionally separate from acoustic-to-
    mechanical calibration and from the fast acoustic sampling clock.
    """
    config = config or ParticleConfig()
    field = np.asarray(intensity_field, dtype=np.float64)
    if field.ndim != 2 or not np.isfinite(field).all():
        raise ValueError("intensity_field must be finite 2-D")
    if config.particle_count < 1 or steps < 1 or integration_time_sec <= 0:
        raise ValueError("Invalid particle integration configuration")
    if force_scale <= 0 or damping < 0:
        raise ValueError("force_scale must be > 0 and damping must be >= 0")

    # Deterministic, shape-preserving normalization. Do not smooth or crop.
    lo, hi = float(np.min(field)), float(np.max(field))
    if hi - lo <= np.finfo(float).eps:
        normalized = np.zeros_like(field)
    else:
        normalized = (field - lo) / (hi - lo)

    gx, gy = field_gradient(normalized, lx, ly)
    rng = np.random.default_rng(config.seed)
    pos = rng.uniform([0, 0], [lx, ly], size=(config.particle_count, 2)).astype(np.float64)
    vel = np.zeros_like(pos)
    dt = float(integration_time_sec) / float(steps)
    history = []
    sample_every = max(1, int(steps / max(1, int(history_points))))

    for step in range(int(steps)):
        fx = _bilinear(gx, pos[:,0], pos[:,1], lx, ly)
        fy = _bilinear(gy, pos[:,0], pos[:,1], lx, ly)
        acc = -force_scale * np.column_stack((fx, fy)) - damping * vel
        vel += acc * dt
        pos += vel * dt
        for axis, L in ((0, lx), (1, ly)):
            lo_mask = pos[:,axis] < 0
            hi_mask = pos[:,axis] > L
            pos[lo_mask,axis] = -pos[lo_mask,axis]
            vel[lo_mask,axis] *= -config.restitution
            pos[hi_mask,axis] = 2*L-pos[hi_mask,axis]
            vel[hi_mask,axis] *= -config.restitution
        if not np.isfinite(pos).all() or not np.isfinite(vel).all():
            raise FloatingPointError("Non-finite particle state")
        if (step + 1) % sample_every == 0:
            hd, _, _ = np.histogram2d(
                pos[:,1], pos[:,0], bins=(config.density_ny, config.density_nx),
                range=((0,ly),(0,lx))
            )
            history.append(hd.astype(np.float64))

    density, _, _ = np.histogram2d(
        pos[:,1], pos[:,0], bins=(config.density_ny, config.density_nx),
        range=((0,ly),(0,lx))
    )
    return ParticleResult(
        pos, vel, density.astype(np.float64),
        {
            "particle_count": config.particle_count,
            "seed": config.seed,
            "dt_sec": dt,
            "steps": int(steps),
            "integration_time_sec": float(integration_time_sec),
            "boundary_model": config.boundary_model,
            "interaction_model": "intensity_gradient_drift",
            "model_status": "reduced_order_model",
            "field_interpretation": "time_averaged_vibration_intensity",
            "force_direction": "toward_low_intensity_nodal_regions",
            "field_normalization": "min_max_only_no_smoothing",
            "force_scale": float(force_scale),
            "damping": float(damping),
            "history_points": len(history),
        },
        None
    ), np.asarray(history, dtype=np.float64) if history else density[None, ...]
