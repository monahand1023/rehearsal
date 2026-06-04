from engine.types import Word, Transcript
from engine.delivery import analyze_delivery


def test_transcript_constructs(make_transcript):
    tr = make_transcript([("hi", 0.0, 0.4)])
    assert tr.words[0].text == "hi"
    assert tr.duration == 0.4


def test_wpm_basic(make_transcript):
    # 4 words spanning t=0.0..2.0s -> 4 words / (2/60 min) = 120 wpm
    tr = make_transcript([("a", 0.0, 0.4), ("b", 0.5, 0.9),
                          ("c", 1.0, 1.4), ("d", 1.5, 2.0)])
    m = analyze_delivery(tr)
    assert m.words_per_minute == 120.0


def test_detects_long_pause(make_transcript):
    tr = make_transcript([("a", 0.0, 0.5), ("b", 3.0, 3.5)])  # 2.5s gap
    m = analyze_delivery(tr)
    assert len(m.pauses) == 1
    assert m.long_pause_count == 1
    assert round(m.pauses[0].duration, 1) == 2.5


def test_short_gap_not_a_pause(make_transcript):
    tr = make_transcript([("a", 0.0, 0.5), ("b", 0.7, 1.0)])  # 0.2s gap
    m = analyze_delivery(tr)
    assert m.pauses == []


def test_time_to_first_word(make_transcript):
    tr = make_transcript([("hello", 1.2, 1.6)], duration=2.0)
    m = analyze_delivery(tr)
    assert m.time_to_first_word == 1.2


def test_empty_transcript(make_transcript):
    tr = make_transcript([], duration=3.0)
    m = analyze_delivery(tr)
    assert m.words_per_minute == 0.0
    assert m.chars_per_minute == 0.0
    assert m.total_audio_time == 3.0


def test_chars_per_minute_counts_characters_not_tokens(make_transcript):
    # Japanese: Whisper bundles some characters into multi-char tokens, so chars/min must
    # count actual characters (excluding punctuation), not the token rate.
    # 'あの'(2) + 'です'(2) + 'ました。'(3 chars; 。 excluded) = 7 chars over 0.0..6.0s
    # -> 7 / (6/60 min) = 70.0 cpm
    tr = make_transcript([("あの", 0.0, 1.0), ("です", 2.0, 3.0), ("ました。", 5.0, 6.0)])
    m = analyze_delivery(tr)
    assert m.chars_per_minute == 70.0
