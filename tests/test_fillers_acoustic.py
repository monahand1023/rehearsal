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
    assert classify_gap(voiced_frac=0.6, gap_db=40, speech_db=65,
                        pitch_std=10, duration=0.4) is False


def test_unsteady_pitch_rejected():
    assert classify_gap(voiced_frac=0.7, gap_db=62, speech_db=65,
                        pitch_std=120, duration=0.4) is False


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
