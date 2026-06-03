import pytest

from engine.tts import config
from engine.tts.base import TTSError
from engine.tts.elevenlabs import ElevenLabsProvider


def test_voice_for_reads_env(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE_EN", "voice123")
    assert config.voice_for("en") == "voice123"
    monkeypatch.setenv("ELEVENLABS_VOICE_JA", "voiceJA")
    assert config.voice_for("ja") == "voiceJA"


def test_is_available_follows_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert config.is_available() is False
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    assert config.is_available() is True


def test_synthesize_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(TTSError):
        ElevenLabsProvider().synthesize("hello", "en")


class FakeResp:
    def __init__(self, status_code=200, content=b"AUDIO", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeClient:
    def __init__(self, resp):
        self.resp = resp
        self.call = None

    def post(self, url, **kw):
        self.call = {"url": url, **kw}
        return self.resp


def test_synthesize_posts_and_returns_bytes(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_VOICE_EN", "voiceEN")
    fake = FakeClient(FakeResp(200, b"MP3BYTES"))
    audio = ElevenLabsProvider(client=fake).synthesize("Nice job", "en")
    assert audio == b"MP3BYTES"
    assert "voiceEN" in fake.call["url"]
    assert fake.call["headers"]["xi-api-key"] == "secret"
    assert fake.call["json"]["text"] == "Nice job"


def test_synthesize_missing_voice_raises(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.delenv("ELEVENLABS_VOICE_JA", raising=False)
    with pytest.raises(TTSError):
        ElevenLabsProvider(client=FakeClient(FakeResp())).synthesize("hi", "ja")


def test_synthesize_api_error_raises(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_VOICE_EN", "voiceEN")
    fake = FakeClient(FakeResp(401, b"", "unauthorized"))
    with pytest.raises(TTSError):
        ElevenLabsProvider(client=fake).synthesize("hi", "en")
