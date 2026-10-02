from cymatic_engine.alignment.mms_fa import make_alignment_record
from cymatic_engine.alignment.validator import validate_alignment_output, WAVInfo
from cymatic_engine.candidates.qc import qc_candidates, select_680


def mk(phone, i, speaker="s1", conf=.9, duration=500):
    return make_alignment_record(
        {"utterance_id": f"u-{phone}-{speaker}-{i}", "speaker_id": speaker,
         "audio_file": "a.wav", "text": "x"},
        i * 1000, i * 1000 + duration, phone, phone, conf,
        "a" * 64, "b" * 64, "MMS_FA", "v1", "c" * 64, sample_rate=16000,
    )


def validate(rows):
    return validate_alignment_output(rows, wav_info={"a.wav": WAVInfo(16000, 1000000)})


def test_upstream_block_is_hard_stop():
    qc = qc_candidates([mk("p", 1)], source_validation_status="BLOCKED")
    assert qc["status"] == "BLOCKED"
    sel = select_680(qc)
    assert sel["status"] == "BLOCKED"


def test_candidate_qc_rejects_short_duration():
    r = mk("p", 1, duration=50)
    v = validate([r])
    qc = qc_candidates(v["accepted_rows"], source_validation_status=v["status"])
    assert qc["eligible_count"] == 0
    assert "duration_too_short" in qc["rejections"][0]["reasons"]


def test_candidate_qc_deduplicates_same_source():
    a = mk("p", 1)
    b = dict(a)
    v = validate([a, b])
    # v7.04 permits duplicate IDs only if intervals do not overlap; these overlap,
    # so this is expected to be blocked before v7.05.
    assert v["status"] == "BLOCKED"


def test_selection_respects_speaker_cap_and_diversity():
    rows = []
    phones = ("æ", "ɑ", "ɛ", "ɪ", "i", "ʌ", "ə", "u", "ʊ", "ɔ", "oʊ", "aɪ", "eɪ",
              "p", "b", "t", "d", "k", "g", "f", "v", "s", "z", "ʃ", "ʒ", "θ", "ð", "h",
              "m", "n", "l", "r", "w", "j")
    for p in phones:
        for i in range(20):
            # Five speakers, four observations each; the default cap is 4.
            rows.append(mk(p, i, speaker=f"s{i % 5}", conf=.95 - i*.001))
    v = validate(rows)
    assert v["status"] == "PASS"
    qc = qc_candidates(v["accepted_rows"], source_validation_status="PASS")
    sel = select_680(qc)
    assert sel["status"] == "PASS"
    assert sel["selected_size"] == 680
    for phone, counts in sel["speaker_counts_per_phone"].items():
        assert max(counts.values()) <= 4


def test_selection_reports_incomplete_instead_of_fabricating():
    rows = [mk("p", i, speaker=f"s{i%2}") for i in range(5)]
    v = validate(rows)
    assert v["status"] == "PASS"
    qc = qc_candidates(v["accepted_rows"], source_validation_status="PASS")
    sel = select_680(qc)
    assert sel["status"] == "INCOMPLETE"
    assert sel["missing_per_phone"]["p"] == 15
    assert sel["selected_size"] == 5
