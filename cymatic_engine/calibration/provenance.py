import hashlib, json
from dataclasses import asdict

def hash_manifest(obj):
    payload=json.dumps(obj,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(payload).hexdigest()

def calibration_manifest(**kwargs):
    m={"schema_version":"2.3.0","calibration_status":"MEASUREMENT_REQUIRED",
       "force_calibration":True,**kwargs}
    m["manifest_hash"]=hash_manifest(m)
    return m
