from dataclasses import dataclass, field
from typing import Any
import hashlib, json
import numpy as np

@dataclass(frozen=True)
class CalibrationManifest:
    calibration_id: str
    level: str
    plate_id: str
    material: dict[str, Any]
    acquisition: dict[str, Any]
    sensor_chain: dict[str, Any]
    excitation: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        payload = json.dumps({
            "calibration_id": self.calibration_id,
            "level": self.level,
            "plate_id": self.plate_id,
            "material": self.material,
            "acquisition": self.acquisition,
            "sensor_chain": self.sensor_chain,
            "excitation": self.excitation,
            "provenance": self.provenance,
        }, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()

@dataclass(frozen=True)
class MeasurementSeries:
    frequency_hz: np.ndarray
    force: np.ndarray
    response: np.ndarray
    response_name: str = "acceleration"
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PhysicalValidationResult:
    level: str
    passed: bool
    metrics: dict[str, float]
    warnings: tuple[str, ...]
    provenance_hash: str
