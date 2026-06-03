from engine.types import Transcript
from engine.fillers.types import FillerHit, FillerReport
from engine.fillers.lexicon import detect_lexicon_fillers

__all__ = ["FillerHit", "FillerReport", "detect_fillers",
           "detect_lexicon_fillers", "merge_hits"]


def _overlaps(a: FillerHit, b: FillerHit) -> bool:
    return a.start < b.end and b.start < a.end


def merge_hits(lexicon_hits, acoustic_hits):
    """Union; drop an acoustic hit that overlaps a lexicon hit (lexicon wins)."""
    merged = list(lexicon_hits)
    for ah in acoustic_hits:
        if not any(_overlaps(ah, lh) for lh in lexicon_hits):
            merged.append(ah)
    merged.sort(key=lambda h: h.start)
    return merged


def detect_fillers(transcript: Transcript, wav_path: str | None = None,
                   include_like: bool = False, acoustic: bool = True) -> FillerReport:
    lex = detect_lexicon_fillers(transcript, include_like=include_like)
    ac = []
    if wav_path and acoustic:
        from engine.fillers.acoustic import detect_acoustic_fillers
        ac = detect_acoustic_fillers(transcript, wav_path)
    hits = merge_hits(lex, ac)
    minutes = transcript.duration / 60 if transcript.duration > 0 else 1e-9
    return FillerReport(hits=hits, count=len(hits),
                        per_minute=round(len(hits) / minutes, 1))
