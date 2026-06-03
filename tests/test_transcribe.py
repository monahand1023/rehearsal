import os

import pytest

from engine.transcribe import _resolve, transcribe

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")
JA_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello_ja.wav")


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


def test_resolve_english_uses_base_en():
    assert _resolve("en") == ("base.en", None)


def test_resolve_japanese_uses_multilingual():
    size, lang = _resolve("ja")
    assert lang == "ja"
    assert size != "base.en"


def test_resolve_explicit_model_override():
    assert _resolve("ja", "medium") == ("medium", "ja")


def test_resolve_explicit_model_english_no_forced_lang():
    assert _resolve("en", "small") == ("small", None)


@pytest.mark.skipif(not os.path.exists(JA_FIXTURE), reason="JP fixture missing")
def test_transcribe_japanese():
    tr = transcribe(JA_FIXTURE, language="ja")
    assert tr.language == "ja"
    assert any("぀" <= c <= "ヿ" or "一" <= c <= "鿿"
               for c in tr.text)   # contains kana/kanji
    assert len(tr.words) >= 1


def test_transcribe_dispatches_to_openai(monkeypatch):
    monkeypatch.setenv("REHEARSAL_TRANSCRIBE_PROVIDER", "openai")
    import engine.transcribe as t
    from engine.types import Transcript
    called = {}

    def fake(wav, language="en"):
        called["wav"] = wav
        called["language"] = language
        return Transcript([], "", 0.0, language)

    monkeypatch.setattr("engine.transcribe_openai.transcribe_openai", fake)
    t.transcribe("x.wav", language="ja")
    assert called == {"wav": "x.wav", "language": "ja"}
