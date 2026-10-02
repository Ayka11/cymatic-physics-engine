from dataclasses import dataclass
import hashlib
import numpy as np
from .modal import PlateModel, modal_frequency_hz
from cymatic_engine.audio.profile import AudioProfile

@dataclass(frozen=True)
class ModalResponse:
    Q_positive: np.ndarray
    frequency_hz: np.ndarray
    time_sec: np.ndarray
    source_audio_hash: str
    response_hash: str
    metadata: dict


def gaussian_coupling(plate, m, n, x0=0.073, y0=0.119, sigma=0.008, nx=256, ny=256):
    x = np.linspace(0, plate.length_x_m, nx)
    y = np.linspace(0, plate.length_y_m, ny)
    X, Y = np.meshgrid(x, y, indexing="xy")
    g = np.exp(-((X-x0)**2 + (Y-y0)**2)/(2*sigma**2))
    phi = np.sin(m*np.pi*X/plate.length_x_m)*np.sin(n*np.pi*Y/plate.length_y_m)
    return float(np.trapezoid(np.trapezoid(g*phi, x, axis=1), y, axis=0))


def prescribed_audio_modal_response(audio: AudioProfile, plate: PlateModel,
                                     contact=(0.073,0.119,0.008)):
    x0,y0,sigma = contact
    n_modes = plate.n_modes_x*plate.n_modes_y
    n_freq = len(audio.frequency_hz)
    Q = np.zeros((n_modes,n_freq,len(audio.time_sec)), dtype=np.complex128)
    # Reduced-order prescribed-force proxy: audio STFT is treated as a mathematical
    # excitation spectrum. It is NOT yet a calibrated acoustic force.
    for m in range(1, plate.n_modes_x+1):
        for n in range(1, plate.n_modes_y+1):
            idx=(m-1)*plate.n_modes_y+(n-1)
            fn=modal_frequency_hz(plate,m,n)
            wn=2*np.pi*fn
            M=plate.modal_mass_kg
            G=gaussian_coupling(plate,m,n,x0,y0,sigma)
            w=2*np.pi*audio.frequency_hz
            H=(1.0/M)/(wn**2-w**2+1j*2*plate.damping_ratio*wn*w)
            Q[idx]=H[:,None]*G*audio.stft_complex
    h=hashlib.sha256()
    h.update(np.ascontiguousarray(Q).tobytes())
    return ModalResponse(Q, audio.frequency_hz, audio.time_sec, audio.source_hash,
                         h.hexdigest(), {
                             "excitation_model":"audio_spectrum_prescribed_to_plate",
                             "physical_status":"reduced_order_model",
                             "empirical_force_calibration":False,
                             "contact_model":"gaussian",
                             "contact_center_m":[x0,y0],
                             "contact_sigma_m":sigma,
                         })
