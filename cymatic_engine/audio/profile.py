from dataclasses import dataclass
import hashlib, json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import stft

@dataclass(frozen=True)
class AudioProfile:
    profile_version: str
    source_hash: str
    sample_rate_hz: float
    channels: int
    duration_sec: float
    samples: np.ndarray
    time_sec: np.ndarray
    frequency_hz: np.ndarray
    stft_complex: np.ndarray
    magnitude: np.ndarray
    phase: np.ndarray
    rms: float
    peak: float
    clipping_fraction: float
    silence_fraction: float
    metadata: dict


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_wav(path, target_sample_rate=48000, n_fft=4096, hop=1024):
    p = Path(path)
    raw = p.read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("Input must be a RIFF/WAVE file")
    audio, fs = sf.read(p, always_2d=True, dtype="float64")
    if fs != target_sample_rate:
        raise ValueError(
            f"Sample rate {fs} Hz is not the required {target_sample_rate} Hz. "
            "Resampling must be an explicit, separately hashed preprocessing stage."
        )
    mono = np.mean(audio, axis=1)
    nperseg = min(int(n_fft), max(1, len(mono)))
    noverlap = min(max(0, int(n_fft-hop)), max(0, nperseg-1))
    f, t, Z = stft(mono, fs=fs, window="hann", nperseg=nperseg, nfft=int(n_fft),
                    noverlap=noverlap, boundary="zeros", padded=True)
    mag = np.abs(Z)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(mono**2))) if mono.size else 0.0
    clipping = float(np.mean(np.abs(mono) >= 0.99999)) if mono.size else 0.0
    silence = float(np.mean(np.abs(mono) < 1e-5)) if mono.size else 1.0
    return AudioProfile(
        profile_version="1.1.0",
        source_hash=_sha256(raw),
        sample_rate_hz=float(fs),
        channels=int(audio.shape[1]),
        duration_sec=float(len(mono)/fs),
        samples=mono,
        time_sec=t.astype(np.float64),
        frequency_hz=f.astype(np.float64),
        stft_complex=Z.astype(np.complex128),
        magnitude=mag.astype(np.float64),
        phase=np.angle(Z).astype(np.float64),
        rms=rms,
        peak=peak,
        clipping_fraction=clipping,
        silence_fraction=silence,
        metadata={
            "source_format": "WAV/PCM",
            "analysis_sample_rate_hz": target_sample_rate,
            "n_fft": n_fft,
            "hop": hop,
            "window": "hann",
            "channel_policy": "mean_channels",
            "raw_audio_unchanged": True,
            "normalization": "none",
        },
    )


def profile_from_samples(samples, fs, source_hash, channels=1, n_fft=4096, hop=1024):
    """Build an AudioProfile from an exact PCM sample slice without re-encoding."""
    x=np.asarray(samples,dtype=np.float64).reshape(-1)
    if int(fs) != 48000:
        raise ValueError("Analysis requires 48000 Hz; resampling must be explicit.")
    nperseg=min(int(n_fft),max(1,len(x)))
    noverlap=min(max(0,int(n_fft-hop)),max(0,nperseg-1))
    f,t,Z=stft(x,fs=fs,window="hann",nperseg=nperseg,nfft=int(n_fft),noverlap=noverlap,boundary="zeros",padded=True)
    peak=float(np.max(np.abs(x))) if x.size else 0.0
    rms=float(np.sqrt(np.mean(x**2))) if x.size else 0.0
    return AudioProfile("1.1.0",source_hash,float(fs),int(channels),float(len(x)/fs),x,
        t.astype(np.float64),f.astype(np.float64),Z.astype(np.complex128),np.abs(Z).astype(np.float64),
        np.angle(Z).astype(np.float64),rms,peak,float(np.mean(np.abs(x)>=.99999)) if x.size else 0.0,
        float(np.mean(np.abs(x)<1e-5)) if x.size else 1.0,{
            "source_format":"exact_pcm_sample_slice","analysis_sample_rate_hz":int(fs),
            "n_fft":n_fft,"hop":hop,"window":"hann","channel_policy":"preselected_mono",
            "raw_audio_unchanged":True,"normalization":"none"})
