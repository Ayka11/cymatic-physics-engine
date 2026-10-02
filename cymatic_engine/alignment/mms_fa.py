import hashlib,json,os
REQUIRED=("utterance_id","audio_file","speaker_id","text")
def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha256_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b): h.update(b)
    return h.hexdigest()
def validate_rows(rows):
    errors=[]; seen=set()
    for i,r in enumerate(rows):
        miss=[k for k in REQUIRED if not r.get(k)]
        if miss: errors.append(f"row_{i}_missing:{','.join(miss)}")
        uid=r.get("utterance_id")
        if uid and uid in seen: errors.append("duplicate_utterance_id:"+uid)
        if uid: seen.add(uid)
    return {"status":"PASS" if not errors else "BLOCKED","errors":errors,"rows":len(rows)}
def require_mms_fa(weights_path):
    ok=bool(weights_path) and os.path.isfile(weights_path) and os.path.getsize(weights_path)>0
    return {"status":"PASS" if ok else "BLOCKED","reason":None if ok else "MMS_FA_model_weights_not_available"}
def make_alignment_record(row,start_sample,end_sample,phone_raw,phone_normalized,confidence,audio_sha256,transcript_sha256,model_id,model_version,config_hash,sample_rate=None):
    payload={"utterance_id":row["utterance_id"],"speaker_id":row["speaker_id"],"audio_file":row["audio_file"],
             "start_sample":int(start_sample),"end_sample":int(end_sample),"phone_raw":phone_raw,"phone_normalized":phone_normalized,
             "confidence":float(confidence),"audio_sha256":audio_sha256,"transcript_sha256":transcript_sha256,
             "model_id":model_id,"model_version":model_version,"alignment_config_hash":config_hash}
    if sample_rate is not None:
        if float(sample_rate) <= 0: raise ValueError("sample_rate must be positive")
        payload["sample_rate"] = int(sample_rate)
        payload["start_sec"] = int(start_sample) / float(sample_rate)
        payload["end_sec"] = int(end_sample) / float(sample_rate)
    payload["alignment_hash"]=hashlib.sha256(canonical(payload).encode()).hexdigest()
    return payload
