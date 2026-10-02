from cymatic_engine.alignment.mms_fa_runtime import normalize_mms_text, phone_projection_gate

def test_normalization():
    assert normalize_mms_text("Hello, WORLD! 2026") == "hello world"
    assert normalize_mms_text("don't") == "don't"

def test_phone_gate_blocks_without_projection():
    r=phone_projection_gate({},None)
    assert r['status']=='BLOCKED'
    assert r['reason']=='PHONE_PROJECTION_REQUIRED'
