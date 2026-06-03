from engine.types import Transcript
from engine.fillers.types import FillerHit

SINGLE_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mhm", "mm"}
PHRASE_FILLERS = [("you", "know"), ("i", "mean"), ("sort", "of"), ("kind", "of")]
LIKE = "like"


def _norm(s: str) -> str:
    return s.lower().strip().strip(".,!?;:\"'").strip()


def detect_lexicon_fillers(transcript: Transcript,
                           include_like: bool = False) -> list[FillerHit]:
    words = transcript.words
    norms = [_norm(w.text) for w in words]
    hits: list[FillerHit] = []
    used: set[int] = set()

    for i in range(len(words) - 1):
        if i in used or i + 1 in used:
            continue
        if (norms[i], norms[i + 1]) in PHRASE_FILLERS:
            hits.append(FillerHit(f"{words[i].text} {words[i + 1].text}",
                                  words[i].start, words[i + 1].end, source="lexicon"))
            used.add(i)
            used.add(i + 1)

    for i, w in enumerate(words):
        if i in used:
            continue
        if norms[i] in SINGLE_FILLERS or (include_like and norms[i] == LIKE):
            hits.append(FillerHit(w.text, w.start, w.end, source="lexicon"))
            used.add(i)

    hits.sort(key=lambda h: h.start)
    return hits
