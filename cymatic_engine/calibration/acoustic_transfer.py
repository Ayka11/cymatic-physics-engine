from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class TransferEstimate:
    frequency_hz: np.ndarray
    transfer: np.ndarray
    coherence: np.ndarray
    uncertainty_relative: np.ndarray
    source_hash: str
    status: str = "MEASURED_CALIBRATED"

def h1_force_transfer(input_spectrum, force_spectrum, input_psd,
                      force_psd=None, cross_spectrum=None,
                      coherence=None, eps=1e-18, source_hash=""):
    """Estimate calibrated input->force transfer H=F/X.

    Preferred cross-spectrum convention:
        H = S_FX / S_XX
    where S_FX is force-vs-input cross spectrum.
    For direct complex spectra, H=F/X is used.
    """
    X=np.asarray(input_spectrum,complex)
    F=np.asarray(force_spectrum,complex)
    if cross_spectrum is not None:
        Sxx=np.asarray(input_psd,float)
        Sfx=np.asarray(cross_spectrum,complex)
        H=Sfx/(Sxx+eps)
    else:
        H=F/(X+eps)
    if coherence is None:
        coh=np.ones(H.shape,float)
    else:
        coh=np.clip(np.asarray(coherence,float),0,1)
    rel=np.sqrt(np.maximum(1.0-coh,0.0)/(coh+eps))
    return H,coh,rel

def calibrate_transfer(frequency_hz, input_spectrum, force_spectrum,
                       input_psd, coherence=None, source_hash=""):
    H,coh,rel=h1_force_transfer(input_spectrum,force_spectrum,input_psd,
                                coherence=coherence,source_hash=source_hash)
    return TransferEstimate(np.asarray(frequency_hz,float),H,coh,rel,source_hash)

def interpolate_complex_transfer(calibration, frequencies_hz):
    f=np.asarray(frequencies_hz,float)
    order=np.argsort(calibration.frequency_hz)
    fs=calibration.frequency_hz[order]
    H=calibration.transfer[order]
    if len(fs)<2:
        raise ValueError("At least two calibration frequency points are required.")
    if np.any(f<fs[0]) or np.any(f>fs[-1]):
        raise ValueError("Requested frequency lies outside calibration range.")
    real=np.interp(f,fs,H.real)
    imag=np.interp(f,fs,H.imag)
    return real+1j*imag

def apply_transfer_to_audio_spectrum(audio_spectrum, audio_frequencies_hz, calibration):
    H=interpolate_complex_transfer(calibration,audio_frequencies_hz)
    return np.asarray(audio_spectrum,complex)*H
