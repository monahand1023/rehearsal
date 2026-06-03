import pytest

from engine.types import Word, Transcript


@pytest.fixture
def make_transcript():
    def _make(words, duration=None, language="en"):
        w = [Word(t, s, e) for (t, s, e) in words]
        dur = duration if duration is not None else (w[-1].end if w else 0.0)
        return Transcript(
            words=w,
            text=" ".join(t for t, _, _ in words),
            duration=dur,
            language=language,
        )
    return _make
