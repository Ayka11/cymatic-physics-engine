import json
from pathlib import Path
from cymatic_engine.corpus.real_corpus_runner import run_corpus

def test_empty_manifest_blocks(tmp_path):
    m=tmp_path/'m.jsonl'; m.write_text('',encoding='utf8')
    r=run_corpus(m,tmp_path/'out')
    assert r['status']=='BLOCKED' and r['reason']=='EMPTY_MANIFEST'

def test_missing_phone_map_blocks_before_runtime(tmp_path):
    audio=tmp_path/'x.wav'; audio.write_bytes(b'not audio')
    m=tmp_path/'m.jsonl'; m.write_text(json.dumps({'utterance_id':'u1','speaker_id':'s1','audio_file':str(audio),'transcript':'cat'})+'\n',encoding='utf8')
    # Runtime is not invoked because phone map is a mandatory manifest dependency.
    # This verifies fail-closed manifest validation at the corpus layer.
    from cymatic_engine.corpus import real_corpus_runner
    class FakeRuntime:
        def __init__(self,*a,**k): pass
        def align(self,*a,**k): raise AssertionError('runtime should not be called')
    old=real_corpus_runner.MMSFARuntime; real_corpus_runner.MMSFARuntime=FakeRuntime
    try:
        r=run_corpus(m,tmp_path/'out')
    finally: real_corpus_runner.MMSFARuntime=old
    assert r['status']=='BLOCKED' and r['blocked_items'][0]['reason']=='PHONE_MAP_REQUIRED'
