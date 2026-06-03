from engine.types import Word, Transcript


def test_transcript_constructs(make_transcript):
    tr = make_transcript([("hi", 0.0, 0.4)])
    assert tr.words[0].text == "hi"
    assert tr.duration == 0.4
