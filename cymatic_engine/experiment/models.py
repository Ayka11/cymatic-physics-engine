from dataclasses import dataclass, field
from typing import Any
import hashlib, json
import numpy as np

@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    plate_id: str
    date_utc: str
    operator: str
    acquisition: dict[str, Any]
    excitation: dict[str, Any]
    sensors: dict[str, Any]
    calibration_refs: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def content_hash(self):
        d = {k: getattr(self, k) for k in (
            "experiment_id","plate_id","date_utc","operator","acquisition",
            "excitation","sensors","calibration_refs","notes")}
        return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",",":")).encode()).hexdigest()

@dataclass(frozen=True)
class MeasurementRecord:
    time_sec: np.ndarray
    channels: dict[str, np.ndarray]
    sample_rate_hz: float
    source_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ExperimentResult:
    frequency_hz: np.ndarray
    frf: np.ndarray
    coherence: np.ndarray
    peak_frequencies_hz: np.ndarray
    delay_sec: float
    metrics: dict[str, float]
    warnings: tuple[str, ...]
    manifest_hash: str
