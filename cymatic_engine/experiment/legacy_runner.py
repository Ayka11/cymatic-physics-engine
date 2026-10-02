from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib, json
import numpy as np

from cymatic_engine.analysis.stability import analyze_stability
from cymatic_engine.analysis.signature import build_signature

@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    artifact_type: str
    sha256: str
    shape: tuple
    dtype: str

@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    experiment_version: str
    status: str
    scientific_status: str
    config_hash: str
    content_hash: str
    provenance_hash: str
    stages: tuple
    artifacts: tuple
    warnings: tuple

def _sha_array(a):
    return hashlib.sha256(np.ascontiguousarray(np.asarray(a)).tobytes()).hexdigest()

def _json_hash(obj):
    return hashlib.sha256(
        json.dumps(obj,sort_keys=True,separators=(",",":"),default=str).encode()
    ).hexdigest()

def _artifact(name, arr):
    a=np.asarray(arr)
    return ArtifactRef(name,name,_sha_array(a),tuple(a.shape),str(a.dtype))

def run_synthetic_reference(duration_sec=0.10, particle_count=10000, seed=20260912):
    cfg={
        "mode":"synthetic_reference",
        "duration_sec":float(duration_sec),
        "reference_plate":{
            "length_x_m":0.30,"length_y_m":0.30,"thickness_m":0.001,
            "E_Pa":200e9,"nu":0.30,"density_kg_m3":7850.0,
            "damping_ratio":0.01
        },
        "grid":{"nx":64,"ny":64},
        "particles":{"count":int(particle_count),"seed":int(seed),"dt_sec":1/4800},
        "excitation":{"model":"single_mode","mode":[1,1],"amplitude":1e-7}
    }
    config_hash=_json_hash(cfg)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%d")
    experiment_id=f"EXP-SYNREF-{stamp}-{config_hash[:8]}"

    # Analytic reference plate field for the synthetic demo. This deliberately
    # remains a reduced-order demonstration and does not assert calibration.
    nx=ny=64
    x=np.linspace(0,0.30,nx); y=np.linspace(0,0.30,ny)
    X,Y=np.meshgrid(x,y)
    f11=53.31829013
    nframes=max(2,min(80,int(round(duration_sec*48000/600))))
    t=np.arange(nframes)/max(nframes-1,1)*duration_sec
    mode=np.sin(np.pi*X/0.30)*np.sin(np.pi*Y/0.30)
    frames=np.asarray([(1e-7*np.sin(2*np.pi*f11*tt)*mode) for tt in t])
    displacement_rms=np.sqrt(np.mean(frames**2,axis=0))

    # Deterministic reduced-order particle density proxy. Seed controls only
    # the computational sampling; it is not an independent physical replicate.
    rng=np.random.default_rng(seed)
    pts=rng.random((particle_count,2))
    energy=np.abs(mode)
    ix=np.minimum((pts[:,0]*nx).astype(int),nx-1)
    iy=np.minimum((pts[:,1]*ny).astype(int),ny-1)
    weights=1.0+10.0*energy[iy,ix]
    density=np.zeros((ny,nx),dtype=np.float64)
    np.add.at(density,(iy,ix),weights)
    density/=density.sum()

    density_sequence=np.stack([density,density])
    stability=analyze_stability(density_sequence,dt_sec=1/4800,window=1)
    signature=build_signature(density,stability)

    artifacts=(
        _artifact("plate_displacement_rms",displacement_rms),
        _artifact("particle_density",density),
        _artifact("cymatic_signature",signature.signature),
    )
    content_hash=_json_hash({
        "f11_hz":f11,
        "artifacts":[a.sha256 for a in artifacts]
    })
    provenance_hash=_json_hash({
        "config_hash":config_hash,
        "content_hash":content_hash,
        "engine_version":"0.6.0"
    })
    manifest=ExperimentManifest(
        experiment_id, "1.0.0", "COMPLETED",
        "COMPUTED_REDUCED_ORDER_MODEL",
        config_hash, content_hash, provenance_hash,
        ("configuration","modal_reference","plate_field",
         "particle_dynamics_reduced_order","stability","signature"),
        artifacts,
        ("Synthetic reference excitation.",
         "Acoustic-to-force transfer is not experimentally calibrated.",
         "Particle dynamics is a reduced-order density proxy in this demo.")
    )
    return {
        "status":"COMPUTED_REDUCED_ORDER_MODEL",
        "experiment_id":experiment_id,"manifest":manifest,
        "positions":rng.random((1000,2)),"config":cfg,
        "modal_frequency_f11_hz":f11,
        "plate_field":{"x_m":x,"y_m":y,"displacement_rms":displacement_rms},
        "particle_result":{"density":density,"particle_count":particle_count,"seed":seed},
        "stability":stability,"signature":signature
    }
