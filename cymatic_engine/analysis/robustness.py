from dataclasses import dataclass
import hashlib, numpy as np

def cosine_distance(a,b):
    a=np.asarray(a,float).ravel(); b=np.asarray(b,float).ravel(); d=np.linalg.norm(a)*np.linalg.norm(b)
    return 1.0 if d==0 else float(1-np.dot(a,b)/d)

def euclidean_distance(a,b): return float(np.linalg.norm(np.asarray(a,float).ravel()-np.asarray(b,float).ravel()))

def pairwise_distances(signatures, metric='cosine'):
    S=np.asarray(signatures,float); n=len(S); D=np.zeros((n,n))
    fn=cosine_distance if metric=='cosine' else euclidean_distance
    for i in range(n):
        for j in range(i+1,n): D[i,j]=D[j,i]=fn(S[i],S[j])
    return D

@dataclass(frozen=True)
class RobustnessResult:
    baseline_signature_hash: str
    particle_convergence: dict
    timestep_convergence: dict
    grid_convergence: dict
    seed_robustness: dict
    signature_distance_matrix: np.ndarray
    metrics: dict
    status: str
    source_run_hash: str
    config_hash: str
    content_hash: str

def convergence_summary(reference, variants, tolerance=0.05):
    ref=np.asarray(reference,float)
    vals=[float(cosine_distance(ref,v)) for v in variants]
    return {'distances':vals,'max_distance':max(vals) if vals else 0.0,'tolerance':tolerance,
            'passed':bool(all(v<=tolerance for v in vals))}

def assess_robustness(baseline_signature, variants, source_run_hash='', config_hash='', tolerance=0.05):
    S=[np.asarray(baseline_signature,float)]+[np.asarray(v,float) for v in variants]
    D=pairwise_distances(S)
    summary=convergence_summary(S[0],S[1:],tolerance)
    ch=hashlib.sha256(np.ascontiguousarray(D).tobytes()).hexdigest()
    return RobustnessResult('',summary,{}, {},{},D,{'baseline_variant_distance':summary['distances']},
                            'ROBUST' if summary['passed'] else 'SENSITIVE',source_run_hash,config_hash,ch)
