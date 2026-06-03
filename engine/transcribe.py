from functools import lru_cache

from faster_whisper import WhisperModel

from engine.types import Word, Transcript


@lru_cache(maxsize=2)
def _get_model(model_size: str = "base.en") -> WhisperModel:
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(wav_path: str, model_size: str = "base.en") -> Transcript:
    model = _get_model(model_size)
    segments, info = model.transcribe(wav_path, word_timestamps=True, beam_size=1)

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
