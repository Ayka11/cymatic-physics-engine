from cymatic_engine.dataset.builder import build_dataset
from cymatic_engine.alignment.validator import CANONICAL_34_PHONES

def base(i,p,r):
    return {"candidate_id":f"{p}:{r:02d}","candidate_rank":r,"phone_normalized":p,"utterance_id":f"u{i}","speaker_id":f"s{i%5}","audio_file":"a.wav","start_sample":i*1000,"end_sample":i*1000+500,"confidence":.9,"alignment_hash":f"h{i}","audio_sha256":f"a{i}","transcript_sha256":f"t{i}","model_id":"MMS_FA","model_version":"x","alignment_config_hash":"c","source_key":f"k{i}"}

def selection():
    rows=[]; i=0
    for p in CANONICAL_34_PHONES:
      for r in range(1,21): rows.append(base(i,p,r)); i+=1
    return {"schema":"CPE_CANDIDATE_SELECTION_v705","status":"PASS","complete":True,"selected_size":680,"slots":rows}

def test_build_680():
    x=build_dataset(selection()); assert x["status"]=="PASS" and x["record_count"]==680 and len(x["records"])==680

def test_blocks_incomplete():
    s=selection(); s["complete"]=False; assert build_dataset(s)["status"]=="BLOCKED"

def test_blocks_duplicate_source():
    s=selection(); s["slots"][1]["source_key"]=s["slots"][0]["source_key"]; assert build_dataset(s)["status"]=="BLOCKED"

def test_blocks_missing_provenance():
    s=selection(); del s["slots"][0]["audio_sha256"]; assert build_dataset(s)["status"]=="BLOCKED"
