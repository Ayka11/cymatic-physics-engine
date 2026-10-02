import numpy as np

def rms_pressure_from_pa(samples):
    x=np.asarray(samples,float)
    return float(np.sqrt(np.mean(x*x))) if x.size else 0.0

def spectrum_from_pressure(samples, fs, n_fft=4096):
    from scipy.signal import stft
    x=np.asarray(samples,float)
    f,t,Z=stft(x,fs=fs,nperseg=min(n_fft,len(x)),nfft=n_fft,
               window="hann",boundary=None,padded=False)
    return f,t,Z
