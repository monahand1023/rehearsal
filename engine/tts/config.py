import os

MODEL_ID = "eleven_multilingual_v2"


def api_key() -> str | None:
    return os.environ.get("ELEVENLABS_API_KEY")


def is_available() -> bool:
    return bool(api_key())


def voice_for(language: str) -> str | None:
    return os.environ.get(f"ELEVENLABS_VOICE_{language.upper()}")
