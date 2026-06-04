import os

import httpx

from engine.types import Word, Transcript

API_URL = "https://api.openai.com/v1/audio/transcriptions"

# Whisper normalizes filler words out by default. Priming it with a FEW example fillers biases
# it to transcribe them verbatim, so the lexicon detector + the LLM can see them. Kept SHORT:
# on near-silent/short audio Whisper can echo the prompt verbatim into the transcript, so a
# shorter prompt means a smaller phantom-filler surface (and we guard the echo below).
FILLER_PROMPTS = {
    "ja": "えーと、あの。",
    "en": "Um, uh, you know.",
}


def _is_prompt_echo(text: str, prompt: str) -> bool:
    """True when Whisper parroted the priming prompt back (a silent/short clip), which would
    otherwise produce phantom fillers. Compares with punctuation/space stripped."""
    drop = " 　、。，．,.!?！？"
    norm = lambda s: "".join(ch for ch in s if ch not in drop)
    t = norm(text)
    return bool(t) and t == norm(prompt)


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
    text = data.get("text", "").strip()
    words = [Word(text=w["word"].strip(), start=float(w["start"]),
                  end=float(w["end"]), probability=1.0)
             for w in data.get("words", [])]
    if _is_prompt_echo(text, FILLER_PROMPTS.get(language, "")):
        text, words = "", []   # silent/short clip parroted the prompt — drop the phantom fillers
    duration = float(data.get("duration", words[-1].end if words else 0.0))
    # Keep the requested ISO code ("ja"/"en"): OpenAI's verbose_json reports the full
    # language NAME ("japanese"), which would break downstream ISO checks (e.g. the
    # Japanese filler detector keys off language == "ja"). We force the language anyway.
    return Transcript(words=words, text=text, duration=duration, language=language)
