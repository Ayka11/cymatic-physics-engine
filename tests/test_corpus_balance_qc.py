import hashlib,json
from cymatic_engine.alignment.validator import CANONICAL_34_PHONES
from cymatic_engine.corpus.balance_qc import audit_dataset, canonical_json

def dataset():
    rows=[]
    for pi,p in enumerate(CANONICAL_34_PHONES):
        for rank in range(1,21):
            speaker=f"spk{(rank-1)%10:02d}"
            r={"candidate_id":f"{p}:{rank:02d}","candidate_rank":rank,"phone_normalized":p,
            "utterance_id":f"utt_{pi}_{rank}","speaker_id":speaker,"audio_file":"a.wav",
            "start_sample":rank*1000,"end_sample":rank*1000+800,"confidence":0.85,
            "alignment_hash":f"ah{pi}{rank}","audio_sha256":f"audio{pi}","transcript_sha256":f"tx{pi}",
            "model_id":"MMS_FA","model_version":"x","alignment_config_hash":"cfg","source_key":f"src_{pi}_{rank}"}
            rows.append(r)
    body=''.join(canonical_json(r)+'\n' for r in rows).encode()
    return {"schema":"CPE_680_CANDIDATE_DATASET_v706","status":"PASS","record_count":680,"dataset_sha256":hashlib.sha256(body).hexdigest(),"records":rows}

def test_pass(): assert audit_dataset(dataset())["status"]=="PASS"
def test_wrong_schema(): assert audit_dataset({"status":"PASS"})["reason"]=="wrong_dataset_schema"
def test_hash_block():
    d=dataset(); d["dataset_sha256"]="0"*64; assert audit_dataset(d)["reason"]=="dataset_hash_mismatch"
def test_speaker_dominance_block():
    d=dataset()
    for r in d["records"]: r["speaker_id"]="only"
    body=''.join(canonical_json(r)+'\n' for r in d["records"]).encode(); d["dataset_sha256"]=hashlib.sha256(body).hexdigest()
    assert audit_dataset(d)["status"]=="BLOCKED"
def test_phone_count_block():
    d=dataset(); d["records"][0]["phone_normalized"]="bad"
    body=''.join(canonical_json(r)+'\n' for r in d["records"]).encode(); d["dataset_sha256"]=hashlib.sha256(body).hexdigest()
    assert audit_dataset(d)["status"]=="BLOCKED"
