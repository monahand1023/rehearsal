"""Local neural TTS via Piper — fully on-device, nothing leaves the machine.

Opt-in: `pip install piper-tts` and point REHEARSAL_PIPER_VOICE_EN / REHEARSAL_PIPER_VOICE_JA
at downloaded .onnx voice models (https://github.com/rhasspy/piper voices). Higher and more
consistent quality than the browser Web Speech API, at the cost of a model download.
"""
import io
import os
import wave

from engine.tts.base import TTSProvider, TTSError


def voice_path(language: str) -> str | None:
    return os.environ.get(f"REHEARSAL_PIPER_VOICE_{language.upper()}")


def is_available() -> bool:
    """True when a Piper voice model is configured AND present for at least one language.
    Cheap (no piper import) so it's safe to call from the provider-resolution path."""
    return any(p and os.path.exists(p) for p in (voice_path("en"), voice_path("ja")))


class PiperProvider(TTSProvider):
    media_type = "audio/wav"

    def synthesize(self, text: str, language: str = "en") -> bytes:
        path = voice_path(language)
        if not path or not os.path.exists(path):
            raise TTSError(f"No Piper voice for '{language}' — set "
                           f"REHEARSAL_PIPER_VOICE_{language.upper()} to a .onnx model path")
        try:
            from piper import PiperVoice
        except ImportError as e:  # opt-in dependency
            raise TTSError("piper-tts not installed (pip install piper-tts)") from e
        voice = PiperVoice.load(path)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            voice.synthesize(text, wav)
        return buf.getvalue()
