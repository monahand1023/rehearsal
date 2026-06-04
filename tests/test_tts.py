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


def _clear_tts_env(monkeypatch):
    for k in ("ELEVENLABS_API_KEY", "REHEARSAL_TTS_PROVIDER",
              "REHEARSAL_PIPER_VOICE_EN", "REHEARSAL_PIPER_VOICE_JA"):
        monkeypatch.delenv(k, raising=False)


def test_provider_defaults_to_browser(monkeypatch):
    _clear_tts_env(monkeypatch)
    assert config.provider() == "browser"
    assert config.server_synthesizer() is None   # browser does TTS client-side


def test_provider_auto_picks_elevenlabs_when_key_set(monkeypatch):
    _clear_tts_env(monkeypatch)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    assert config.provider() == "elevenlabs"
    assert isinstance(config.server_synthesizer(), ElevenLabsProvider)


def test_provider_explicit_browser_overrides_key(monkeypatch):
    _clear_tts_env(monkeypatch)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("REHEARSAL_TTS_PROVIDER", "browser")
    assert config.provider() == "browser"
    assert config.server_synthesizer() is None


def test_provider_auto_picks_piper_when_voice_present(monkeypatch, tmp_path):
    from engine.tts import piper
    from engine.tts.piper import PiperProvider
    _clear_tts_env(monkeypatch)
    model = tmp_path / "ja.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("REHEARSAL_PIPER_VOICE_JA", str(model))
    assert piper.is_available() is True
    assert config.provider() == "piper"          # auto: no EL key, a Piper voice exists
    assert isinstance(config.server_synthesizer(), PiperProvider)


def test_piper_synthesize_missing_voice_raises(monkeypatch):
    from engine.tts.piper import PiperProvider
    monkeypatch.delenv("REHEARSAL_PIPER_VOICE_EN", raising=False)
    with pytest.raises(TTSError):
        PiperProvider().synthesize("hi", "en")
