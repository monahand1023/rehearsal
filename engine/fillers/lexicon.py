from engine.types import Transcript
from engine.fillers.types import FillerHit

EN_SINGLE_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah",
                     "hmm", "mhm", "mm"}
EN_PHRASE_FILLERS = [("you", "know"), ("i", "mean"), ("sort", "of"), ("kind", "of")]
LIKE = "like"

JA_FILLERS = {"えーと", "えー", "ええと", "えっと", "あの", "あのー", "あのう",
              "その", "そのー", "まあ", "まぁ", "なんか", "んー", "あー", "ええ"}
# Match longest-first so えーと wins over えー and あのー over あの (no double-counting).
_JA_BY_LEN = sorted(JA_FILLERS, key=len, reverse=True)

_PUNCT = ".,!?;:\"'、。！？「」『』…　"


def _norm(s: str) -> str:
    return s.lower().strip().strip(_PUNCT).strip()


def detect_lexicon_fillers(transcript: Transcript,
                           include_like: bool = False) -> list[FillerHit]:
    if transcript.language == "ja":
        return _detect_ja(transcript)
    return _detect_en(transcript, include_like)


def _detect_ja(transcript: Transcript) -> list[FillerHit]:
    # OpenAI Whisper emits Japanese word-timestamps roughly one character at a time, so a
    # multi-character filler (あの, えーと, なんか) is split across single-char tokens and
    # never equals a whole token. Match fillers as substrings of the concatenated tokens,
    # mapping each matched character back to the timestamp of the token it came from.
    words = transcript.words
    if not words:
        return []
    text = ""
    owner: list[int] = []  # owner[i] = index of the word token that contributed text[i]
    for wi, w in enumerate(words):
        for ch in w.text:
            text += ch
            owner.append(wi)
    used = [False] * len(text)
    hits: list[FillerHit] = []
    for filler in _JA_BY_LEN:
        flen = len(filler)
        i = text.find(filler)
        while i != -1:
            if not any(used[i:i + flen]):
                for j in range(i, i + flen):
                    used[j] = True
                start = words[owner[i]].start
                end = words[owner[i + flen - 1]].end
                hits.append(FillerHit(filler, start, end, source="lexicon"))
                i = text.find(filler, i + flen)
            else:
                i = text.find(filler, i + 1)
    hits.sort(key=lambda h: h.start)
    return hits


def _detect_en(transcript: Transcript, include_like: bool) -> list[FillerHit]:
    words = transcript.words
    norms = [_norm(w.text) for w in words]
    hits: list[FillerHit] = []
    used: set[int] = set()

    for i in range(len(words) - 1):
        if i in used or i + 1 in used:
            continue
        if (norms[i], norms[i + 1]) in EN_PHRASE_FILLERS:
            hits.append(FillerHit(f"{words[i].text} {words[i + 1].text}",
                                  words[i].start, words[i + 1].end, source="lexicon"))
            used.add(i)
            used.add(i + 1)

    for i, w in enumerate(words):
        if i in used:
            continue
        if norms[i] in EN_SINGLE_FILLERS or (include_like and norms[i] == LIKE):
            hits.append(FillerHit(w.text, w.start, w.end, source="lexicon"))
            used.add(i)

    hits.sort(key=lambda h: h.start)
    return hits
