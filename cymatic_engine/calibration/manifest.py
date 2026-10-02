import json
from pathlib import Path
from .models import CalibrationManifest

def save_manifest(manifest: CalibrationManifest, path):
    Path(path).write_text(json.dumps({
        "calibration_id": manifest.calibration_id,
        "level": manifest.level,
        "plate_id": manifest.plate_id,
        "material": manifest.material,
        "acquisition": manifest.acquisition,
        "sensor_chain": manifest.sensor_chain,
        "excitation": manifest.excitation,
        "provenance": manifest.provenance,
        "content_hash": manifest.content_hash(),
    }, indent=2, sort_keys=True), encoding="utf-8")
