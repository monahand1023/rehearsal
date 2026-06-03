from engine.types import Word, Transcript
from engine.clarity import analyze_clarity


def _tr(pairs):  # pairs: list of (text, probability)
    words = [Word(t, i * 0.5, i * 0.5 + 0.4, p) for i, (t, p) in enumerate(pairs)]
    return Transcript(words, " ".join(t for t, _ in pairs), 5.0)


def test_mean_confidence():
    c = analyze_clarity(_tr([("a", 0.9), ("b", 0.7)]))
    assert c.mean_confidence == 0.8


def test_low_confidence_words():
    c = analyze_clarity(_tr([("clear", 0.95), ("mumble", 0.3)]), low_threshold=0.5)
    assert c.low_confidence_words == ["mumble"]


def test_empty_transcript():
    c = analyze_clarity(Transcript([], "", 1.0))
    assert c.mean_confidence == 0.0
    assert c.low_confidence_words == []
