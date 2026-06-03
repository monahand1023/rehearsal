from engine.types import Transcript
from engine.fillers.types import FillerHit, FillerReport
from engine.fillers.lexicon import detect_lexicon_fillers

__all__ = ["FillerHit", "FillerReport", "detect_fillers", "detect_lexicon_fillers"]


def detect_fillers(transcript: Transcript, wav_path: str | None = None,
                   include_like: bool = False, acoustic: bool = True) -> FillerReport:
    hits = detect_lexicon_fillers(transcript, include_like=include_like)
    hits.sort(key=lambda h: h.start)
    minutes = transcript.duration / 60 if transcript.duration > 0 else 1e-9
    return FillerReport(hits=hits, count=len(hits),
                        per_minute=round(len(hits) / minutes, 1))
