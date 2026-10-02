from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class StabilityResult:
    frame_distance: np.ndarray
    correlation: np.ndarray
    spectral_distance: np.ndarray
    entropy_normalized: np.ndarray
    spectral_centroid: np.ndarray
    spectral_spread: np.ndarray
    state: str
    convergence_time_sec: float | None
    cycle_repeatability: float | None
    metadata: dict

def _corr(a,b):
    a=np.asarray(a,dtype=float).ravel(); b=np.asarray(b,dtype=float).ravel()
    aa=a-a.mean(); bb=b-b.mean()
    den=np.linalg.norm(aa)*np.linalg.norm(bb)
    return float(np.dot(aa,bb)/den) if den>0 else 1.0

def _spectrum(d):
    f=np.fft.fftshift(np.fft.fft2(d))
    return np.abs(f)**2

def _spectral_stats(P):
    ny,nx=P.shape
    yy,xx=np.indices(P.shape)
    kx=xx-nx//2; ky=yy-ny//2
    kr=np.sqrt(kx*kx+ky*ky)
    total=P.sum()+np.finfo(float).eps
    kc=float((kr*P).sum()/total)
    spread=float(np.sqrt(((kr-kc)**2*P).sum()/total))
    p=P.ravel()/total
    H=float(-(p*np.log(p+1e-15)).sum()/np.log(len(p)))
    return kc,spread,H

def analyze_stability(density_frames, dt_sec=1/4800, d_max=0.01, c_min=0.99, window=10):
    frames=np.asarray(density_frames,dtype=float)
    if frames.ndim!=3 or frames.shape[0]<2:
        raise ValueError("Expected density frames with shape (time,y,x)")
    D=[]; C=[]; DS=[]; H=[]; KC=[]; KS=[]
    spectra=[_spectrum(f) for f in frames]
    for i in range(1,len(frames)):
        a,b=frames[i-1],frames[i]
        D.append(float(np.linalg.norm(b-a)/(np.linalg.norm(b)+1e-15)))
        C.append(_corr(a,b))
        DS.append(float(np.linalg.norm(spectra[i]-spectra[i-1])/(np.linalg.norm(spectra[i])+1e-15)))
    for P in spectra:
        kc,spread,h=_spectral_stats(P); KC.append(kc); KS.append(spread); H.append(h)

    convergence=None
    if len(D)>=window:
        for j in range(window-1,len(D)):
            if np.all(np.asarray(D[j-window+1:j+1])<d_max) and np.all(np.asarray(C[j-window+1:j+1])>c_min):
                convergence=(j+1)*dt_sec; break

    tail=max(1,min(window,len(D)))
    meanD=float(np.mean(D[-tail:])); meanC=float(np.mean(C[-tail:]))
    if convergence is not None:
        state="stable_attractor_like"
    elif meanD<0.10 and meanC>0.90:
        state="quasi_stable"
    else:
        state="transient_or_drifting"

    return StabilityResult(
        np.asarray(D),np.asarray(C),np.asarray(DS),np.asarray(H),
        np.asarray(KC),np.asarray(KS),state,convergence,None,
        {"dt_sec":dt_sec,"d_max":d_max,"c_min":c_min,"window":window}
    )

def cycle_repeatability(density_frames, cycle_length_frames):
    frames=np.asarray(density_frames,dtype=float)
    if cycle_length_frames<1 or len(frames)<2*cycle_length_frames:
        raise ValueError("Insufficient frames for cycle comparison")
    n=len(frames)//cycle_length_frames
    cycles=frames[:n*cycle_length_frames].reshape(n,cycle_length_frames,*frames.shape[1:])
    vals=[]
    for i in range(n-1):
        vals.append(_corr(cycles[i],cycles[i+1]))
    return float(np.mean(vals)) if vals else 1.0
