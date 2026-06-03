from engine.fillers.acoustic import classify_gap


def test_voiced_filled_pause_is_filler():
    assert classify_gap(voiced_frac=0.8, gap_db=60, speech_db=65,
                        pitch_std=20, duration=0.4) is True


def test_silent_gap_is_not_filler():
    assert classify_gap(voiced_frac=0.05, gap_db=35, speech_db=65,
                        pitch_std=0, duration=0.6) is False


def test_too_short_gap_rejected():
    assert classify_gap(voiced_frac=0.9, gap_db=64, speech_db=65,
                        pitch_std=10, duration=0.05) is False


def test_too_long_gap_rejected():
    assert classify_gap(voiced_frac=0.9, gap_db=64, speech_db=65,
                        pitch_std=10, duration=3.0) is False


def test_loud_but_unvoiced_rejected():
    assert classify_gap(voiced_frac=0.1, gap_db=64, speech_db=65,
                        pitch_std=10, duration=0.4) is False


def test_voiced_but_too_quiet_rejected():
    # voiced_frac=0.8 keeps this a pure "too quiet" test (clears the voicing floor,
    # rejected only on the dB check) after min_voiced_frac was raised to 0.65.
    assert classify_gap(voiced_frac=0.8, gap_db=40, speech_db=65,
                        pitch_std=10, duration=0.4) is False


def test_unsteady_pitch_rejected():
    assert classify_gap(voiced_frac=0.7, gap_db=62, speech_db=65,
                        pitch_std=120, duration=0.4) is False


def test_partial_voiced_pause_not_filler():
    # Regression: real false positive from the en_story ElevenLabs clip — the pause
    # after "leave," whose decaying voiced tail (long vowel + voiced /v/) read as
    # voiced_frac=0.56. A genuine filled pause is a SUSTAINED vowel (~0.8+ voiced);
    # a clause-boundary pause tail is only partially voiced and must be rejected.
    assert classify_gap(voiced_frac=0.56, gap_db=53.5, speech_db=58.8,
                        pitch_std=3.2, duration=0.34) is False


import os
import pytest

from engine.types import Word
from engine.fillers.acoustic import candidate_gaps, detect_acoustic_fillers

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")


def test_candidate_gaps_inter_word():
    words = [Word("a", 0.0, 0.5), Word("b", 1.0, 1.5), Word("c", 1.6, 2.0)]
    gaps = candidate_gaps(words)
    assert (0.5, 1.0) in gaps
    assert (1.5, 1.6) in gaps
    assert all(g[1] > g[0] for g in gaps)


def test_candidate_gaps_leading():
    words = [Word("a", 0.8, 1.2)]
    gaps = candidate_gaps(words)
    assert (0.0, 0.8) in gaps


def test_candidate_gaps_empty():
    assert candidate_gaps([]) == []


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture missing")
def test_detect_acoustic_runs_on_fixture():
    from engine.transcribe import transcribe
    tr = transcribe(FIXTURE)
    hits = detect_acoustic_fillers(tr, FIXTURE)
    assert isinstance(hits, list)
    for h in hits:
        assert h.source == "acoustic"
        assert h.end > h.start


from engine.fillers.types import FillerHit as FH
from engine.fillers import merge_hits


def test_merge_dedups_overlap():
    lex = [FH("um", 0.4, 0.7, "lexicon")]
    ac = [FH("(uh)", 0.5, 0.8, "acoustic")]      # overlaps the lexicon hit
    merged = merge_hits(lex, ac)
    assert len(merged) == 1
    assert merged[0].source == "lexicon"


def test_merge_keeps_nonoverlapping():
    lex = [FH("um", 0.4, 0.7, "lexicon")]
    ac = [FH("(uh)", 2.0, 2.4, "acoustic")]
    merged = merge_hits(lex, ac)
    assert len(merged) == 2
    assert [h.source for h in merged] == ["lexicon", "acoustic"]


def test_merge_sorts_by_start():
    lex = [FH("um", 3.0, 3.2, "lexicon")]
    ac = [FH("(uh)", 1.0, 1.3, "acoustic")]
    merged = merge_hits(lex, ac)
    assert [h.start for h in merged] == [1.0, 3.0]


def test_detect_fillers_acoustic_off_skips_acoustic(make_transcript, monkeypatch):
    from engine.fillers import detect_fillers
    calls = {"n": 0}

    def spy(tr, wav, **kw):
        calls["n"] += 1
        return []

    monkeypatch.setattr("engine.fillers.acoustic.detect_acoustic_fillers", spy)
    tr = make_transcript([("um", 0.0, 0.3)], duration=2.0)
    detect_fillers(tr, wav_path="x.wav", acoustic=False)
    assert calls["n"] == 0


def test_detect_fillers_acoustic_on_merges(make_transcript, monkeypatch):
    from engine.fillers import detect_fillers
    from engine.fillers.types import FillerHit
    monkeypatch.setattr("engine.fillers.acoustic.detect_acoustic_fillers",
                        lambda tr, wav: [FillerHit("(uh)", 5.0, 5.3, "acoustic")])
    tr = make_transcript([("um", 0.0, 0.3)], duration=10.0)
    r = detect_fillers(tr, wav_path="x.wav")  # acoustic defaults True
    assert sorted(h.source for h in r.hits) == ["acoustic", "lexicon"]
