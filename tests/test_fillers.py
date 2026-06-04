from engine.fillers import detect_fillers


def test_counts_um_uh(make_transcript):
    tr = make_transcript(
        [("So", 0.0, 0.3), ("um", 0.4, 0.7), ("I", 0.8, 1.0),
         ("uh", 1.1, 1.4), ("left", 1.5, 1.9)],
        duration=2.0,
    )
    r = detect_fillers(tr)
    assert r.count == 2
    assert {h.text.lower() for h in r.hits} == {"um", "uh"}


def test_strips_punctuation(make_transcript):
    tr = make_transcript([("Um,", 0.0, 0.3), ("right", 0.4, 0.8)], duration=1.0)
    assert detect_fillers(tr).count == 1


def test_phrase_you_know(make_transcript):
    tr = make_transcript(
        [("it", 0.0, 0.3), ("you", 0.4, 0.6), ("know", 0.7, 0.9),
         ("worked", 1.0, 1.5)],
        duration=2.0,
    )
    r = detect_fillers(tr)
    assert r.count == 1
    assert r.hits[0].text.lower() == "you know"


def test_like_excluded_by_default(make_transcript):
    tr = make_transcript([("I", 0.0, 0.2), ("like", 0.3, 0.6), ("pizza", 0.7, 1.1)],
                         duration=2.0)
    assert detect_fillers(tr).count == 0
    assert detect_fillers(tr, include_like=True).count == 1


def test_per_minute(make_transcript):
    tr = make_transcript([("um", 0.0, 0.3)], duration=30.0)  # 1 filler in 0.5 min
    assert detect_fillers(tr).per_minute == 2.0


def test_filler_hits_have_lexicon_source(make_transcript):
    tr = make_transcript([("um", 0.0, 0.3)], duration=2.0)
    r = detect_fillers(tr)
    assert r.hits[0].source == "lexicon"


def test_japanese_fillers_detected():
    from engine.types import Word, Transcript
    from engine.fillers import detect_fillers
    tr = Transcript(
        [Word("私", 0.0, 0.3), Word("えーと", 0.4, 0.9), Word("です", 1.0, 1.4)],
        "私 えーと です", 2.0, language="ja",
    )
    r = detect_fillers(tr)
    assert r.count == 1
    assert r.hits[0].text == "えーと"
    assert r.hits[0].source == "lexicon"


def test_japanese_fillers_detected_when_tokenized_per_character():
    # OpenAI Whisper emits Japanese word-timestamps roughly one CHARACTER at a time, so a
    # multi-character filler like あの is split across single-char tokens and never equals a
    # whole token. The detector must match it as a substring and span the char tokens.
    from engine.types import Word, Transcript
    from engine.fillers import detect_fillers
    chars = "あの週末は楽しかった"
    words = [Word(ch, i * 0.3, i * 0.3 + 0.25) for i, ch in enumerate(chars)]
    tr = Transcript(words, chars, 6.0, language="ja")
    r = detect_fillers(tr)
    assert r.count == 1
    assert r.hits[0].text == "あの"
    assert r.hits[0].start == words[0].start   # spans あ(0)
    assert r.hits[0].end == words[1].end       # ...through の(1)


def test_japanese_prefers_longer_filler_no_double_count():
    # えーと (え,ー,と) must count once as the long filler, not also as えー.
    from engine.types import Word, Transcript
    from engine.fillers import detect_fillers
    chars = "えーとそれで"
    words = [Word(ch, i * 0.3, i * 0.3 + 0.25) for i, ch in enumerate(chars)]
    tr = Transcript(words, chars, 3.0, language="ja")
    r = detect_fillers(tr)
    assert r.count == 1
    assert r.hits[0].text == "えーと"


def test_english_filler_path_unchanged(make_transcript):
    # make_transcript defaults language="en"
    tr = make_transcript([("So", 0.0, 0.3), ("um", 0.4, 0.7)], duration=2.0)
    from engine.fillers import detect_fillers
    assert detect_fillers(tr).count == 1
