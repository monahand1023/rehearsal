import os

import httpx

from engine.types import Word, Transcript

API_URL = "https://api.openai.com/v1/audio/transcriptions"


def transcribe_openai(wav_path: str, language: str = "en", client=None) -> Transcript:
    """Transcribe via OpenAI's Whisper API with word timestamps. OpenAI does not
    return per-word confidence, so Word.probability defaults to 1.0 (the clarity
    proxy is correspondingly less precise on the cloud provider)."""
    http = client or httpx
    key = os.environ["OPENAI_API_KEY"]
    with open(wav_path, "rb") as f:
        resp = http.post(
            API_URL,
            headers={"Authorization": f"Bearer {key}"},
            data={"model": "whisper-1", "language": language,
                  "response_format": "verbose_json",
                  "timestamp_granularities[]": "word"},
            files={"file": ("audio.wav", f, "audio/wav")},
            timeout=120,
        )
    resp.raise_for_status()
    data = resp.json()
    words = [Word(text=w["word"].strip(), start=float(w["start"]),
                  end=float(w["end"]), probability=1.0)
             for w in data.get("words", [])]
    duration = float(data.get("duration", words[-1].end if words else 0.0))
    return Transcript(words=words, text=data.get("text", "").strip(),
                      duration=duration, language=data.get("language", language))
