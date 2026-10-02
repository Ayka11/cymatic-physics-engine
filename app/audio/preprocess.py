from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import tempfile
import wave

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


@dataclass(frozen=True)
class AudioInspection:
    path: str
    container: str
    sample_rate_hz: int
    channels: int
    subtype: str
    format_name: str
    frames: int
    duration_sec: float
    source_sha256: str


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inspect_wav(path: str | Path) -> AudioInspection:
    path = str(path)
    source_hash = sha256_file(path)
    try:
        info = sf.info(path)
        return AudioInspection(
            path=path,
            container=str(info.format or ""),
            sample_rate_hz=int(info.samplerate),
            channels=int(info.channels),
            subtype=str(info.subtype or ""),
            format_name=str(info.name or ""),
            frames=int(info.frames),
            duration_sec=float(info.duration),
            source_sha256=source_hash,
        )
    except Exception:
        # wave can still identify ordinary RIFF PCM files when libsndfile cannot.
        with wave.open(path, "rb") as w:
            rate = w.getframerate()
            channels = w.getnchannels()
            frames = w.getnframes()
            width = w.getsampwidth()
        return AudioInspection(
            path=path,
            container="WAV",
            sample_rate_hz=rate,
            channels=channels,
            subtype=f"PCM_{width * 8}",
            format_name="WAV",
            frames=frames,
            duration_sec=frames / rate if rate else 0.0,
            source_sha256=source_hash,
        )


def _write_pcm_wav(path: str | Path, samples: np.ndarray, sample_rate: int) -> None:
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak > 1.0:
        x = x / peak
    sf.write(str(path), x, int(sample_rate), subtype="PCM_16", format="WAV")


def prepare_for_cpe(
    source_path: str | Path,
    target_rate: int = 48000,
    mono: bool = True,
) -> tuple[str, AudioInspection, dict]:
    """
    Explicit preprocessing boundary:
      arbitrary supported WAV -> 48 kHz PCM WAV suitable for CPE.

    The original source is never overwritten. Provenance records both hashes.
    """
    source_path = str(source_path)
    src = inspect_wav(source_path)

    try:
        data, fs = sf.read(source_path, always_2d=True, dtype="float32")
    except Exception as exc:
        raise ValueError(
            "Unsupported WAV encoding. "
            f"Detected metadata: {src.sample_rate_hz} Hz, {src.channels} channels, "
            f"{src.subtype or 'unknown subtype'}. "
            "Please provide a standard PCM WAV or use the explicit preprocessing path."
        ) from exc

    if mono and data.shape[1] > 1:
        data = np.mean(data, axis=1, keepdims=True)

    fs = int(fs)
    if fs != target_rate:
        g = np.gcd(fs, target_rate)
        up = target_rate // g
        down = fs // g
        data = resample_poly(data, up, down, axis=0).astype(np.float32)

    fd, out_path = tempfile.mkstemp(prefix="cpe_preprocessed_", suffix=".wav")
    os.close(fd)
    _write_pcm_wav(out_path, data, target_rate)
    out = inspect_wav(out_path)

    provenance = {
        "preprocessing_applied": True,
        "source_sha256": src.source_sha256,
        "source_sample_rate_hz": src.sample_rate_hz,
        "source_channels": src.channels,
        "source_subtype": src.subtype,
        "analysis_sha256": out.source_sha256,
        "analysis_sample_rate_hz": out.sample_rate_hz,
        "analysis_channels": out.channels,
        "analysis_subtype": out.subtype,
        "resampled": fs != target_rate,
        "downmixed_to_mono": bool(mono and src.channels > 1),
        "scientific_boundary": "raw_audio_to_explicitly_preprocessed_48k_pcm",
    }
    return out_path, out, provenance
