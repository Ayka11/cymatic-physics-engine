from dataclasses import dataclass
import hashlib, json
import numpy as np

@dataclass(frozen=True)
class PatternCanonicalizerResult:
    raw_density: np.ndarray
    mass_normalized_density: np.ndarray
    canonical_density: np.ndarray
    centroid_xy: tuple[float,float]
    covariance_2x2: np.ndarray
    physical_scale_m: tuple[float,float]
    coordinate_frame: str
    transformation_log: tuple[str,...]
    source_run_hash: str
    result_hash: str

def _hash(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

def canonicalize_density(density, physical_size_m=(0.30,0.30), translation=True):
    raw=np.asarray(density,dtype=np.float64)
    if raw.ndim!=2 or not np.isfinite(raw).all() or np.any(raw<0): raise ValueError('density must be finite, nonnegative 2-D')
    mass=float(raw.sum())
    if mass<=0: raise ValueError('density mass must be positive')
    p=raw/mass
    ny,nx=p.shape
    x=np.linspace(0,physical_size_m[0],nx); y=np.linspace(0,physical_size_m[1],ny)
    X,Y=np.meshgrid(x,y,indexing='xy')
    cx=float((p*X).sum()); cy=float((p*Y).sum())
    dx=X-cx; dy=Y-cy
    cov=np.array([[(p*dx*dx).sum(),(p*dx*dy).sum()],[(p*dx*dy).sum(),(p*dy*dy).sum()]])
    out=p.copy(); log=[]
    # Translation canonicalization is implemented with integer pixel shifts only.
    # No interpolation, rotation, reflection or scaling is silently applied.
    if translation:
        target_x=(nx-1)/2; target_y=(ny-1)/2
        ix=int(round(cx/(physical_size_m[0]/(nx-1)))); iy=int(round(cy/(physical_size_m[1]/(ny-1))))
        sx=int(round(target_x-ix)); sy=int(round(target_y-iy))
        shifted=np.zeros_like(out)
        xs=slice(max(0,sx),min(nx,nx+sx)); xt=slice(max(0,-sx),min(nx,nx-sx))
        ys=slice(max(0,sy),min(ny,ny+sy)); yt=slice(max(0,-sy),min(ny,ny-sy))
        shifted[ys,xs]=out[yt,xt]
        out=shifted
        if sx or sy: log.append(f'translate_pixels:{sx},{sy}')
    rh=_hash(out)
    return PatternCanonicalizerResult(raw,p,out,(cx,cy),cov,tuple(map(float,physical_size_m)),
                                      'plate_xy',tuple(log),_hash(raw),rh)
