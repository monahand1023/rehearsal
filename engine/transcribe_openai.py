import os

import httpx

from engine.types import Word, Transcript

API_URL = "https://api.openai.com/v1/audio/transcriptions"

# Whisper normalizes filler words out by default. Priming it with example fillers biases
# it to transcribe them verbatim, so the lexicon detector + the LLM can see them.
FILLER_PROMPTS = {
    "ja": "えーと、あの、ええと、えっと、まあ、なんか、そのー、うーん。",
    "en": "Um, uh, er, hmm, you know, like, I mean, so, well.",
}


def transcribe_openai(audio_path: str, language: str = "en", client=None) -> Transcript:
    """Transcribe via OpenAI's Whisper API with word timestamps. Accepts the original
    upload (webm/wav/m4a/…) directly — the API auto-detects from the filename, so no
    ffmpeg conversion is needed. OpenAI returns no per-word confidence, so
    Word.probability defaults to 1.0 (the clarity proxy is less precise on cloud)."""
    http = client or httpx
    key = os.environ["OPENAI_API_KEY"]
    filename = os.path.basename(audio_path) or "audio.webm"
    with open(audio_path, "rb") as f:
        data = {"model": "whisper-1", "language": language,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word"}
        if language in FILLER_PROMPTS:
            data["prompt"] = FILLER_PROMPTS[language]  # keep ums/uhs in the transcript
        resp = http.post(
            API_URL,
            headers={"Authorization": f"Bearer {key}"},
            data=data,
            files={"file": (filename, f)},
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
