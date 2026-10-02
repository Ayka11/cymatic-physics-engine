from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
import soundfile as sf
from .models import MeasurementRecord

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()

def read_measurement_csv(path, time_column="time_sec"):
    path = Path(path)
    df = pd.read_csv(path)
    if time_column not in df.columns:
        raise ValueError(f"Missing required time column: {time_column}")
    t = df[time_column].to_numpy(float)
    channels = {c: df[c].to_numpy(float) for c in df.columns if c != time_column}
    if len(t) < 2:
        raise ValueError("Measurement requires at least two samples.")
    dt = np.median(np.diff(t))
    if dt <= 0:
        raise ValueError("Time column must be strictly increasing.")
    return MeasurementRecord(t, channels, 1.0/dt, _sha256(path), {"format":"csv"})

def read_measurement_wav(path):
    path = Path(path)
    x, fs = sf.read(path, always_2d=True)
    t = np.arange(len(x))/fs
    channels = {f"ch{i+1}": x[:,i].astype(float) for i in range(x.shape[1])}
    return MeasurementRecord(t, channels, float(fs), _sha256(path), {"format":"wav"})
