from dataclasses import dataclass
import numpy as np
from .robustness import cosine_distance

@dataclass(frozen=True)
class SeparationResult:
    labels: tuple[str,...]
    within_distance: dict
    between_distance: dict
    separation_matrix: np.ndarray
    permutation_pvalues: dict
    feature_ablation: dict
    status: str

def separation(signatures, labels):
    S=np.asarray(signatures,float); labels=np.asarray(labels)
    if len(S)!=len(labels) or len(S)<2: raise ValueError('signatures/labels mismatch')
    groups=list(dict.fromkeys(labels.tolist())); within={}; between={}
    for g in groups:
        X=S[labels==g]; vals=[]
        for i in range(len(X)):
            for j in range(i+1,len(X)): vals.append(cosine_distance(X[i],X[j]))
        within[g]=float(np.median(vals)) if vals else 0.0
    M=np.zeros((len(groups),len(groups)))
    for i,g in enumerate(groups):
        for j,h in enumerate(groups):
            if j<=i: continue
            vals=[cosine_distance(a,b) for a in S[labels==g] for b in S[labels==h]]
            between[f'{g}|{h}']=float(np.median(vals)); M[i,j]=M[j,i]=between[f'{g}|{h}']
    status='DISCRIMINATIVE' if any(v>0 for v in between.values()) else 'NOT_DISCRIMINATIVE'
    return SeparationResult(tuple(groups),within,between,M,{}, {},status)
