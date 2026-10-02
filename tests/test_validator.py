import hashlib, json, wave
from pathlib import Path
from cymatic_engine.alignment.mms_fa import make_alignment_record
from cymatic_engine.alignment.validator import validate_alignment_output, build_680_candidate_pool, WAVInfo, expected_alignment_hash


def row(phone='p', start=0, end=100, conf=.9, uid='u1'):
    r=make_alignment_record({'utterance_id':uid,'speaker_id':'s1','audio_file':'a.wav','text':'x'},start,end,phone,phone,conf,'a'*64,'b'*64,'MMS_FA','v1','c'*64)
    return r

def test_valid_output_passes():
    r=row('ʃ',0,100)
    x=validate_alignment_output([r], wav_info={'a.wav':WAVInfo(16000,1000)})
    assert x['status']=='PASS'

def test_unknown_phone_blocks():
    r=row('q')
    x=validate_alignment_output([r], wav_info={'a.wav':WAVInfo(16000,1000)})
    assert x['status']=='BLOCKED' and any('unknown_phone' in e for e in x['errors'])

def test_overlap_blocks():
    x=validate_alignment_output([row('p',0,100),row('b',99,200,uid='u1')], wav_info={'a.wav':WAVInfo(16000,1000)})
    assert x['status']=='BLOCKED' and any('overlapping_intervals' in e for e in x['errors'])

def test_wav_boundary_blocks():
    x=validate_alignment_output([row('p',900,1100)], wav_info={'a.wav':WAVInfo(16000,1000)})
    assert x['status']=='BLOCKED' and any('wav_boundary_violation' in e for e in x['errors'])

def test_provenance_hash_blocks():
    r=row(); r['model_id']='OTHER'; r['alignment_hash']='0'*64
    x=validate_alignment_output([r], wav_info={'a.wav':WAVInfo(16000,1000)})
    assert x['status']=='BLOCKED'
    assert any('model_provenance_mismatch' in e for e in x['errors'])
    assert any('alignment_hash_mismatch' in e for e in x['errors'])

def test_low_confidence_blocks():
    x=validate_alignment_output([row(conf=.59)], wav_info={'a.wav':WAVInfo(16000,1000)})
    assert x['status']=='BLOCKED' and any('confidence_below_threshold' in e for e in x['errors'])

def test_pool_is_34x20_when_sufficient():
    rows=[]
    for p in ('æ','ɑ','ɛ','ɪ','i','ʌ','ə','u','ʊ','ɔ','oʊ','aɪ','eɪ','p','b','t','d','k','g','f','v','s','z','ʃ','ʒ','θ','ð','h','m','n','l','r','w','j'):
        for i in range(20):
            rows.append(row(p,i*100,(i+1)*100,.9-i*.001,uid=f'{p}-{i}'))
    v=validate_alignment_output(rows,wav_info={'a.wav':WAVInfo(16000,100000)})
    assert v['status']=='PASS'
    pool=build_680_candidate_pool(v['accepted_rows'])
    assert pool['pool_size']==680 and pool['complete']
