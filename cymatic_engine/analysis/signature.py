from dataclasses import dataclass
import hashlib, json
import numpy as np

@dataclass(frozen=True)
class SignatureResult:
    signature: np.ndarray
    standardized_signature: np.ndarray
    feature_names: tuple[str, ...]
    feature_groups: dict
    source_hash: str
    content_hash: str
    metadata: dict

def _hash_array(a):
    a=np.asarray(a)
    return hashlib.sha256(a.tobytes(order="C")).hexdigest()

def _moments(p):
    ny,nx=p.shape
    y,x=np.indices(p.shape,dtype=float)
    m=p.sum()+1e-15
    x=(x*p).sum()/m; y=(y*p).sum()/m
    dx=np.indices(p.shape,dtype=float)[1]-x
    dy=np.indices(p.shape,dtype=float)[0]-y
    return [
        float((dx*dx*p).sum()/m),
        float((dy*dy*p).sum()/m),
        float((dx*dy*p).sum()/m),
        float((dx**3*p).sum()/m),
        float((dy**3*p).sum()/m),
        float((dx*dx*dy*p).sum()/m),
        float((dx*dy*dy*p).sum()/m),
    ]

def _radial(p, bins=16):
    y,x=np.indices(p.shape,dtype=float)
    cy,cx=np.array(p.shape)/2-0.5
    r=np.sqrt((x-cx)**2+(y-cy)**2)
    edges=np.linspace(0,r.max()+1e-12,bins+1)
    out=[]
    for i in range(bins):
        mask=(r>=edges[i])&(r<edges[i+1])
        out.append(float(p[mask].mean()) if mask.any() else 0.0)
    return out

def _angular(p, bins=36):
    y,x=np.indices(p.shape,dtype=float)
    cy,cx=np.array(p.shape)/2-0.5
    a=(np.arctan2(y-cy,x-cx)+2*np.pi)%(2*np.pi)
    out=[]
    for i in range(bins):
        lo=2*np.pi*i/bins; hi=2*np.pi*(i+1)/bins
        mask=(a>=lo)&(a<hi)
        out.append(float(p[mask].mean()) if mask.any() else 0.0)
    return out

def _spectral(p, bins=16):
    F=np.fft.fftshift(np.fft.fft2(p))
    P=np.abs(F)**2
    y,x=np.indices(P.shape,dtype=float)
    cy,cx=np.array(P.shape)/2-0.5
    r=np.sqrt((x-cx)**2+(y-cy)**2)
    total=P.sum()+1e-15
    kc=float((r*P).sum()/total)
    spread=float(np.sqrt(((r-kc)**2*P).sum()/total))
    prob=P.ravel()/total
    entropy=float(-(prob*np.log(prob+1e-15)).sum()/np.log(len(prob)))
    radial=_radial(P/total,bins)
    return [kc,spread,entropy,*radial]

def _topology(p, levels=(.10,.25,.50,.75,.90)):
    # Lightweight deterministic topology proxy: connected components and holes
    # are computed on binary masks using 4-connectivity and Euler characteristic.
    from scipy.ndimage import label
    out=[]
    for q in levels:
        b=p>=q*(p.max()+1e-15)
        lab,n=label(b,structure=np.array([[0,1,0],[1,1,1],[0,1,0]]))
        area=float(b.mean())
        largest=float(max([(lab==i).sum() for i in range(1,n+1)],default=0)/b.size)
        # Euler characteristic = components - holes; holes estimated from complement components.
        comp_bg,_=label(~b,structure=np.ones((3,3),int))
        border=np.unique(np.r_[comp_bg[0,:],comp_bg[-1,:],comp_bg[:,0],comp_bg[:,-1]])
        holes=max(int(comp_bg.max())-len(border)+1,0)
        out += [float(n),float(holes),largest,area]
    return out

def build_signature(density, stability=None, radial_bins=16, angular_bins=36):
    raw=np.asarray(density,dtype=float)
    if raw.ndim!=2: raise ValueError("density must be 2-D")
    if not np.isfinite(raw).all(): raise ValueError("density contains non-finite values")
    p=np.maximum(raw,0.0)
    p=p/(p.sum()+1e-15)

    names=[]; vals=[]; groups={}
    def add(group, prefix, arr):
        start=len(vals)
        vals.extend(float(x) for x in arr)
        names.extend(f"{prefix}_{i:02d}" for i in range(len(arr)))
        groups.setdefault(group,[]).extend(range(start,start+len(arr)))

    a=_moments(p); add("spatial","moment",a)
    add("radial","radial",_radial(p,radial_bins))
    add("angular","angular",_angular(p,angular_bins))
    add("spectral","spectral",_spectral(p,radial_bins))
    add("topology","topology",_topology(p))

    temporal=[]
    if stability is not None:
        D=np.asarray(stability.frame_distance,dtype=float)
        C=np.asarray(stability.correlation,dtype=float)
        H=np.asarray(stability.entropy_normalized,dtype=float)
        temporal=[
            float(D.mean()) if D.size else 0.0,
            float(D[-1]) if D.size else 0.0,
            float(C.mean()) if C.size else 1.0,
            float(C[-1]) if C.size else 1.0,
            float(H[-1]) if H.size else 0.0,
            float(stability.convergence_time_sec) if stability.convergence_time_sec is not None else -1.0,
        ]
    else:
        temporal=[0.0,0.0,1.0,1.0,0.0,-1.0]
    add("temporal","temporal",temporal)

    vec=np.asarray(vals,dtype=np.float64)
    # Deterministic within-vector normalization is NOT used. Standardization is
    # deliberately left to a fixed external reference/training set.
    standardized=vec.copy()
    ch=hashlib.sha256(vec.tobytes(order="C")).hexdigest()
    source_hash=hashlib.sha256(p.tobytes(order="C")).hexdigest()
    return SignatureResult(vec,standardized,tuple(names),groups,source_hash,ch,
        {"schema_version":"1.0.0","normalization":"mass","standardization":"external_reference_required"})


# Backward-compatible API used by the existing synthetic runner.
def cymatic_signature(density, stability=None, **kwargs):
    return build_signature(density, stability=stability, **kwargs).signature
