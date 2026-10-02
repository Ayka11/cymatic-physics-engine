import copy, hashlib, json
from cymatic_engine.benchmark import benchmark, dataset_hash
from cymatic_engine.alignment.validator import CANONICAL_34_PHONES

def make_dataset():
    rows=[]
    for p in CANONICAL_34_PHONES:
        for rank in range(1,21):
            rows.append({"candidate_id":f"{p}-{rank}","candidate_rank":rank,"phone_normalized":p,"utterance_id":f"u-{p}-{rank}","speaker_id":f"s{rank%8}","audio_file":"a.wav","start_sample":rank*1000,"end_sample":rank*1000+500,"confidence":0.8,"alignment_hash":"a","audio_sha256":"b","transcript_sha256":"c","model_id":"MMS_FA","model_version":"1","alignment_config_hash":"d","source_key":f"src-{p}-{rank}"})
    return {"schema":"CPE_680_CANDIDATE_DATASET_v706","status":"PASS","record_count":680,"dataset_sha256":dataset_hash(rows),"records":rows}

def good_qc(): return {"schema":"CPE_CORPUS_BALANCE_QC_v707","status":"PASS"}
def good_manifest(): return {"schema":"CPE_REPRODUCIBILITY_MANIFEST_v708","status":"PASS","fail_closed":True}

def test_blocks_without_deterministic_rerun():
    d=make_dataset(); r=benchmark(d,good_qc(),good_manifest()); assert r['status']=='BLOCKED'; assert 'deterministic_dataset_hash' in r['failures']

def test_passes_complete_gate():
    d=make_dataset(); h=d['dataset_sha256']; r=benchmark(d,good_qc(),good_manifest(),deterministic_rerun_hash=h); assert r['status']=='PASS'; assert not r['failures']

def test_blocks_hash_tamper():
    d=make_dataset(); d['dataset_sha256']='0'*64; r=benchmark(d,good_qc(),good_manifest(),deterministic_rerun_hash='0'*64); assert r['status']=='BLOCKED'; assert 'dataset_hash_integrity' in r['failures']

def test_blocks_unknown_phone():
    d=make_dataset(); d['records'][0]['phone_normalized']='ZZ'; d['dataset_sha256']=dataset_hash(d['records']); r=benchmark(d,good_qc(),good_manifest(),deterministic_rerun_hash=d['dataset_sha256']); assert r['status']=='BLOCKED'; assert '34_phone_coverage' in r['failures']
