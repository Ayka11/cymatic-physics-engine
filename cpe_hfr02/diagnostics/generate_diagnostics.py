from __future__ import annotations
import argparse, hashlib, json, math, wave
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import matplotlib.pyplot as plt

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024), b""): h.update(block)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-frequency", type=float, default=8000.0)
    a=ap.parse_args()
    src=Path(a.input).resolve(); out=Path(a.out).resolve() if a.out else src/"diagnostics"
    out.mkdir(parents=True, exist_ok=True)
    p=json.loads((src/"provenance.json").read_text(encoding="utf-8"))
    if p.get("status")!="ALTERNATE_SOURCE_AUDIO_STFT_COMPUTED_E0":
        raise ValueError("Unexpected provenance status; refusing relabel.")
    wav=src/"canonical_48k_mono.wav"; ogg=src/"source.ogg"; npz=src/"complex_stft.npz"
    for x in (wav,ogg,npz):
        if not x.is_file(): raise FileNotFoundError(x)
    with wave.open(str(wav),"rb") as wf:
        sr=wf.getframerate(); ch=wf.getnchannels(); sw=wf.getsampwidth()
        samples=np.frombuffer(wf.readframes(wf.getnframes()),dtype="<i2").astype(float)/32768.0
    if (sr,ch,sw)!=(48000,1,2): raise ValueError("Expected 48 kHz mono PCM16.")
    with np.load(npz, allow_pickle=False) as z:
        f=np.asarray(z["frequency_hz"],float); t=np.asarray(z["time_s"],float)
        r=np.asarray(z["field_real"],float); im=np.asarray(z["field_imag"],float)
    if r.shape!=im.shape or r.shape!=(f.size,t.size): raise ValueError("Array shape mismatch.")
    if not all(np.isfinite(x).all() for x in (samples,f,t,r,im)): raise ValueError("Non-finite data.")
    if not np.any(im!=0): raise ValueError("Imaginary component is zero.")
    if sha256_file(wav)!=p["canonical_wav_sha256"]: raise ValueError("WAV hash mismatch.")
    if sha256_file(ogg)!=p["source_sha256"]: raise ValueError("Source hash mismatch.")
    m=np.hypot(r,im); phase=np.arctan2(im,r)
    mask=f<=min(a.max_frequency,float(f[-1])); md=20*np.log10(np.maximum(m[mask],np.finfo(float).tiny)); md-=md.max()
    tw=np.arange(len(samples))/sr
    fig,ax=plt.subplots(figsize=(12,4.8),constrained_layout=True); ax.plot(tw,samples,linewidth=.65)
    ax.set_title("Russian «мама» — canonical audio waveform (E0)"); ax.set_xlabel("Time (s)"); ax.set_ylabel("Normalized PCM amplitude"); ax.grid(True,alpha=.25)
    fig.savefig(out/"01_audio_waveform.png",dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,6),constrained_layout=True); q=ax.pcolormesh(t,f[mask],md,shading="auto",cmap="magma",vmin=-80,vmax=0)
    ax.set_title("Audio STFT magnitude — relative dB (not calibrated sound pressure)"); ax.set_xlabel("Time (s)"); ax.set_ylabel("Frequency (Hz)"); fig.colorbar(q,ax=ax,label="Relative magnitude (dB; peak = 0 dB)")
    fig.savefig(out/"02_stft_magnitude_spectrogram.png",dpi=160); plt.close(fig)
    rel=20*np.log10(np.maximum(m[mask],np.finfo(float).tiny)); ph=np.ma.masked_where(rel<rel.max()-50,phase[mask])
    fig,ax=plt.subplots(figsize=(12,6),constrained_layout=True); q=ax.pcolormesh(t,f[mask],ph,shading="auto",cmap="twilight",vmin=-math.pi,vmax=math.pi)
    ax.set_title("Complex STFT phase (low-magnitude bins masked; audio-domain only)"); ax.set_xlabel("Time (s)"); ax.set_ylabel("Frequency (Hz)"); fig.colorbar(q,ax=ax,label="Phase (rad)")
    fig.savefig(out/"03_stft_phase.png",dpi=160); plt.close(fig)
    report={"status":"AUDIO_STFT_DIAGNOSTICS_GENERATED_E0","source_status":p["status"],"source_sha256":p["source_sha256"],"canonical_wav_sha256":p["canonical_wav_sha256"],"sample_rate_hz":sr,"duration_s":len(samples)/sr,"sample_count":len(samples),"stft_shape_frequency_by_time":list(r.shape),"frequency_bin_spacing_hz":float(f[1]-f[0]),"plots":[x.name for x in out.glob("*.png")],"limitations":["Audio STFT diagnostics only; not a measured spatial cymatic field.","Relative magnitude is not calibrated SPL.","Phase is audio-domain phase, not spatial plate-field phase.","No acoustic/force/plate/particle calibration or physical validation.","Alternate source does not clear HFR-06 source-hash gate."],"created_utc":datetime.now(timezone.utc).isoformat()}
    (out/"diagnostic_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
