import os

MODEL_ID = "eleven_multilingual_v2"


def api_key() -> str | None:
    return os.environ.get("ELEVENLABS_API_KEY")


def is_available() -> bool:
    """ElevenLabs availability (kept for back-compat with existing callers/tests)."""
    return bool(api_key())


def voice_for(language: str) -> str | None:
    return os.environ.get(f"ELEVENLABS_VOICE_{language.upper()}")


def provider() -> str:
    """The resolved TTS provider: 'elevenlabs' | 'piper' | 'browser'.

    REHEARSAL_TTS_PROVIDER selects it; the default 'auto' picks the best configured option.
    'browser' (the OS Web Speech API, done client-side) is the zero-config, fully-local
    fallback — so the coach voice works offline with NOTHING leaving the machine."""
    choice = os.environ.get("REHEARSAL_TTS_PROVIDER", "auto").strip().lower()
    if choice in ("elevenlabs", "piper", "browser"):
        return choice
    if api_key():
        return "elevenlabs"
    from engine.tts import piper
    if piper.is_available():
        return "piper"
    return "browser"


def server_synthesizer():
    """A server-side TTSProvider (ElevenLabs/Piper) for /api/speak, or None when the browser
    handles TTS locally (nothing to synthesize server-side)."""
    p = provider()
    if p == "elevenlabs":
        from engine.tts.elevenlabs import ElevenLabsProvider
        return ElevenLabsProvider()
    if p == "piper":
        from engine.tts.piper import PiperProvider
        return PiperProvider()
    return None
