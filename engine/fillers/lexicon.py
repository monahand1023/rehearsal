from engine.types import Transcript
from engine.fillers.types import FillerHit

EN_SINGLE_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah",
                     "hmm", "mhm", "mm"}
EN_PHRASE_FILLERS = [("you", "know"), ("i", "mean"), ("sort", "of"), ("kind", "of")]
LIKE = "like"

# Strong fillers: unambiguous hesitation forms (often elongated), matched anywhere.
JA_FILLERS_STRONG = {"えーと", "えー", "ええと", "えっと", "あのー", "あのう", "そのー",
                     "なんか", "なんだろう", "んー", "あー"}
# Weak fillers: bare forms that are ALSO common content words (あの本 = "that book",
# まあまあ = "so-so"). Only counted when set off by punctuation or end-of-utterance —
# i.e. used as a discourse marker ("あの、…") — to avoid flagging legitimate demonstratives.
# (その / ええ are dropped entirely: too often legitimate content/agreement; そのー stays.)
JA_FILLERS_WEAK = {"あの", "まあ", "まぁ"}
JA_FILLERS = JA_FILLERS_STRONG | JA_FILLERS_WEAK   # kept for reference
_JA_STRONG_BY_LEN = sorted(JA_FILLERS_STRONG, key=len, reverse=True)
_JA_WEAK_BY_LEN = sorted(JA_FILLERS_WEAK, key=len, reverse=True)
# A weak filler only counts when the next character is one of these (or end-of-text).
_JA_BOUNDARY = set("、。，．・…！？!?,. 　\n\t」』）)】〉")

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

    def scan(filler: str, require_boundary: bool):
        flen = len(filler)
        i = text.find(filler)
        while i != -1:
            j = i + flen
            ok = not any(used[i:j])
            if ok and require_boundary:
                nxt = text[j] if j < len(text) else ""
                ok = nxt == "" or nxt in _JA_BOUNDARY
            if ok:
                for k in range(i, j):
                    used[k] = True
                hits.append(FillerHit(filler, words[owner[i]].start,
                                      words[owner[j - 1]].end, source="lexicon"))
                i = text.find(filler, j)
            else:
                i = text.find(filler, i + 1)

    for filler in _JA_STRONG_BY_LEN:   # unambiguous forms: match anywhere
        scan(filler, require_boundary=False)
    for filler in _JA_WEAK_BY_LEN:     # bare demonstratives: only as set-off discourse markers
        scan(filler, require_boundary=True)
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
