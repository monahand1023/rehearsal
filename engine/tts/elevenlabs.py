import httpx

from engine.tts import config
from engine.tts.base import TTSProvider, TTSError

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class ElevenLabsProvider(TTSProvider):
    def __init__(self, client=None):
        self._client = client or httpx

    def synthesize(self, text: str, language: str = "en") -> bytes:
        key = config.api_key()
        if not key:
            raise TTSError("ELEVENLABS_API_KEY not set")
        voice_id = config.voice_for(language)
        if not voice_id:
            raise TTSError(
                f"No voice configured for language '{language}' "
                f"(set ELEVENLABS_VOICE_{language.upper()})"
            )
        resp = self._client.post(
            API_URL.format(voice_id=voice_id),
            headers={
                "xi-api-key": key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": config.MODEL_ID,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise TTSError(f"ElevenLabs error {resp.status_code}: {resp.text}")
        return resp.content
