import hashlib
import pytest
from cymatic_engine.alignment.phone_projection import build_explicit_map_record, project_phone_spans

SOURCE = {
    "schema": "CPE_MMS_FA_ALIGNMENT",
    "audio_sha256": "a"*64,
    "transcript_sha256": hashlib.sha256(b"cat").hexdigest(),
    "transcript_raw": "cat",
    "transcript_normalized": "cat",
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


def test_missing_mapping_source_blocks():
    maps = [{"phone": "k", "source_char_start": 0, "source_char_end": 1}]
    out = project_phone_spans(
        utterance_id="u1", speaker_id="s1", audio_file="a.wav",
        word="cat", normalized_word="cat", char_spans=SPANS,
        phone_map=maps, source_alignment=SOURCE,
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "PHONE_MAP_INVALID"


def test_empty_mapping_source_blocks():
    maps = [{"phone": "k", "source_char_start": 0,
             "source_char_end": 1, "mapping_source": "  "}]
    out = project_phone_spans(
        utterance_id="u1", speaker_id="s1", audio_file="a.wav",
        word="cat", normalized_word="cat", char_spans=SPANS,
        phone_map=maps, source_alignment=SOURCE,
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "PHONE_MAP_INVALID"


def test_missing_source_alignment_provenance_blocks():
    maps = [build_explicit_map_record("k", 0, 1, mapping_source="gold")]
    out = project_phone_spans(
        utterance_id="u1", speaker_id="s1", audio_file="a.wav",
        word="cat", normalized_word="cat", char_spans=SPANS,
        phone_map=maps, source_alignment={},
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "SOURCE_ALIGNMENT_PROVENANCE_REQUIRED"


def test_malformed_source_alignment_hash_blocks():
    maps = [build_explicit_map_record("k", 0, 1, mapping_source="gold")]
    bad_source = {**SOURCE, "audio_sha256": "not-a-sha256"}
    out = project_phone_spans(
        utterance_id="u1", speaker_id="s1", audio_file="a.wav",
        word="cat", normalized_word="cat", char_spans=SPANS,
        phone_map=maps, source_alignment=bad_source,
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "SOURCE_ALIGNMENT_PROVENANCE_INVALID"


def test_unmapped_character_alignment_span_blocks():
    maps = [
        build_explicit_map_record("k", 0, 1, mapping_source="gold"),
        build_explicit_map_record("t", 2, 3, mapping_source="gold"),
    ]
    out = project_phone_spans(
        utterance_id="u1", speaker_id="s1", audio_file="a.wav",
        word="cat", normalized_word="cat", char_spans=SPANS,
        phone_map=maps, source_alignment=SOURCE,
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "UNMAPPED_CHARACTER_ALIGNMENT_SPAN"
    assert out["phones"] == []


def test_none_source_alignment_blocks_cleanly():
    maps = [build_explicit_map_record("k", 0, 1, mapping_source="gold")]
    out = project_phone_spans(
        utterance_id="u1", speaker_id="s1", audio_file="a.wav",
        word="cat", normalized_word="cat", char_spans=SPANS,
        phone_map=maps, source_alignment=None,
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "SOURCE_ALIGNMENT_INVALID"


def test_non_object_phone_map_entry_blocks_cleanly():
    out = project_phone_spans(
        utterance_id="u1", speaker_id="s1", audio_file="a.wav",
        word="cat", normalized_word="cat", char_spans=SPANS,
        phone_map=[None], source_alignment=SOURCE,
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "PHONE_MAP_INVALID"


def test_non_integral_mapping_index_blocks_cleanly():
    maps = [{
        "phone": "k", "source_char_start": 0.5,
        "source_char_end": 1, "mapping_source": "gold",
    }]
    out = project_phone_spans(
        utterance_id="u1", speaker_id="s1", audio_file="a.wav",
        word="cat", normalized_word="cat", char_spans=SPANS,
        phone_map=maps, source_alignment=SOURCE,
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "PHONE_MAP_INVALID"

def test_mapping_beyond_normalized_transcript_blocks():
    bad_map = [{
        "phone": "K",
        "source_char_start": 0,
        "source_char_end": 4,
        "mapping_source": "explicit_test_mapping",
    }]
    result = project_phone_spans(
        utterance_id="u1",
        speaker_id="s1",
        audio_file="test.wav",
        word="cat",
        normalized_word="cat",
        char_spans=[{
            "char_start": 0,
            "char_end": 1,
            "start_sample": 0,
            "end_sample": 100,
            "confidence": 0.9,
        }],
        phone_map=bad_map,
        source_alignment=SOURCE,
    )
    assert result["status"] == "BLOCKED"
    assert result.get("phones", []) == []
    assert any("char_span_out_of_bounds" in e for e in result.get("errors", []))


def test_alignment_span_beyond_normalized_transcript_blocks():
    bad_span = {
        "char_start": 2,
        "char_end": 4,
        "start_sample": 100,
        "end_sample": 200,
        "confidence": 0.9,
    }
    result = project_phone_spans(
        utterance_id="u1",
        speaker_id="s1",
        audio_file="test.wav",
        word="cat",
        normalized_word="cat",
        char_spans=[bad_span],
        phone_map=[{
            "phone": "T",
            "source_char_start": 0,
            "source_char_end": 3,
            "mapping_source": "explicit_test_mapping",
        }],
        source_alignment=SOURCE,
    )
    assert result["status"] == "BLOCKED"
    assert result.get("phones", []) == []
    assert result.get("reason") == "CHARACTER_SPAN_OUT_OF_BOUNDS"


def test_transcript_hash_mismatch_blocks():
    mismatched_source = dict(SOURCE)
    mismatched_source["transcript_raw"] = "dog"
    result = project_phone_spans(
        utterance_id="u1",
        speaker_id="s1",
        audio_file="test.wav",
        word="cat",
        normalized_word="cat",
        char_spans=[{
            "char_start": 0,
            "char_end": 1,
            "start_sample": 0,
            "end_sample": 100,
            "confidence": 0.9,
        }],
        phone_map=[{
            "phone": "K",
            "source_char_start": 0,
            "source_char_end": 3,
            "mapping_source": "explicit_test_mapping",
        }],
        source_alignment=mismatched_source,
    )
    assert result["status"] == "BLOCKED"
    assert result.get("phones", []) == []
    assert result.get("reason") == "SOURCE_ALIGNMENT_TRANSCRIPT_HASH_MISMATCH"
