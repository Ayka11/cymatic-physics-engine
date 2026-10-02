import pytest
from cymatic_engine.alignment.phone_projection import build_explicit_map_record, project_phone_spans

SOURCE = {
    "schema": "CPE_MMS_FA_ALIGNMENT",
    "audio_sha256": "a"*64,
    "transcript_sha256": "b"*64,
    "model_id": "MMS_FA",
    "model_version": "MMS_FA"
}
SPANS = [
    {"char_start":0,"char_end":1,"start_sample":0,"end_sample":100,"confidence":0.9},
    {"char_start":1,"char_end":2,"start_sample":100,"end_sample":200,"confidence":0.8},
    {"char_start":2,"char_end":3,"start_sample":200,"end_sample":300,"confidence":0.95},
]

def test_explicit_projection_passes():
    maps = [build_explicit_map_record("k",0,1,mapping_source="gold_g2p_v1"),
            build_explicit_map_record("æ",1,2,mapping_source="gold_g2p_v1"),
            build_explicit_map_record("t",2,3,mapping_source="gold_g2p_v1")]
    out = project_phone_spans(utterance_id="u1",speaker_id="s1",audio_file="a.wav",word="cat",normalized_word="cat",char_spans=SPANS,phone_map=maps,source_alignment=SOURCE)
    assert out["status"] == "PASS"
    assert len(out["phones"]) == 3
    assert all(r["projection_hash"] for r in out["phones"])

def test_missing_map_blocks():
    out = project_phone_spans(utterance_id="u1",speaker_id="s1",audio_file="a.wav",word="cat",normalized_word="cat",char_spans=SPANS,phone_map=[],source_alignment=SOURCE)
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "PHONE_MAP_REQUIRED"

def test_unknown_phone_blocks():
    maps = [build_explicit_map_record("k",0,1,mapping_source="gold"), {"phone":"X","source_char_start":1,"source_char_end":2,"mapping_source":"gold"}]
    out = project_phone_spans(utterance_id="u1",speaker_id="s1",audio_file="a.wav",word="cat",normalized_word="cat",char_spans=SPANS,phone_map=maps,source_alignment=SOURCE)
    assert out["status"] == "BLOCKED"

def test_uncovered_mapping_blocks():
    maps = [build_explicit_map_record("k",0,1,mapping_source="gold"), build_explicit_map_record("æ",4,5,mapping_source="gold")]
    out = project_phone_spans(utterance_id="u1",speaker_id="s1",audio_file="a.wav",word="cat",normalized_word="cat",char_spans=SPANS,phone_map=maps,source_alignment=SOURCE)
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "PHONE_MAP_INVALID"

def test_projection_rejects_overlap():
    maps = [build_explicit_map_record("k",0,2,mapping_source="gold"), build_explicit_map_record("æ",1,3,mapping_source="gold")]
    out = project_phone_spans(utterance_id="u1",speaker_id="s1",audio_file="a.wav",word="cat",normalized_word="cat",char_spans=SPANS,phone_map=maps,source_alignment=SOURCE)
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "PROJECTED_PHONE_OVERLAP"
