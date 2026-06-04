import os
from functools import lru_cache

from engine.types import Word, Transcript
from engine.constants import LANG_EN

MULTILINGUAL_MODEL = "small"


@lru_cache(maxsize=3)
def _get_model(model_size: str):
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def _resolve(language: str = LANG_EN, model_size: str | None = None):
    """Pick (model_size, whisper_language) for a track language."""
    if model_size is not None:
        return model_size, (None if language == LANG_EN else language)
    if language == LANG_EN:
        return "base.en", None
    return MULTILINGUAL_MODEL, language


def transcribe(wav_path: str, language: str = LANG_EN,
               model_size: str | None = None) -> Transcript:
    if os.environ.get("REHEARSAL_TRANSCRIBE_PROVIDER", "local") == "openai":
        from engine.transcribe_openai import transcribe_openai
        return transcribe_openai(wav_path, language)
    return _transcribe_local(wav_path, language, model_size)


def _transcribe_local(wav_path: str, language: str = LANG_EN,
                      model_size: str | None = None) -> Transcript:
    size, whisper_lang = _resolve(language, model_size)
    model = _get_model(size)
    segments, info = model.transcribe(wav_path, word_timestamps=True,
                                      beam_size=1, language=whisper_lang)

    words: list[Word] = []
    texts: list[str] = []
    for seg in segments:
        texts.append(seg.text)
        for w in (seg.words or []):
            words.append(Word(
                text=w.word.strip(),
                start=float(w.start),
                end=float(w.end),
                probability=float(w.probability),
            ))

    return Transcript(
        words=words,
        text="".join(texts).strip(),
        duration=float(info.duration),
        language=info.language,
    )
