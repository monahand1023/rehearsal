import os

import pytest

from engine.transcribe import transcribe

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture missing")
def test_transcribe_fixture():
    tr = transcribe(FIXTURE)
    assert "name" in tr.text.lower()
    assert len(tr.words) >= 4
    assert tr.duration > 0
    # word timestamps are monotonic and within the clip
    for w in tr.words:
        assert w.start >= 0
        assert w.end >= w.start
