# Japanese Track Phase 1 (Free-Response) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `rehearsal` work for free-response Japanese speaking practice — multilingual transcription, Japanese fillers, a confidence-based clarity proxy, a Japanese question library, and frontend track switching — reusing the existing delivery/acoustic/coach/voice stack.

**Architecture:** Extend the engine to be language-aware (transcribe model/language selection; per-language filler sets; a new clarity module) and add a `/api/tracks` endpoint + a frontend track picker. The English path keeps its exact current defaults, so all 53 tests stay green. Per-phoneme pronunciation is NOT in scope (Phase 2).

**Tech Stack:** Python 3.11+, faster-whisper (multilingual `small` model for JP — same dependency), parselmouth, FastAPI, vanilla JS. macOS `say -v Kyoko` for a Japanese test fixture. No new dependencies.

---

## File structure

```
engine/transcribe.py        # MODIFY: _resolve() [pure] + transcribe(wav, language, model_size)
engine/fillers/lexicon.py   # MODIFY: per-language filler sets; JP punctuation in _norm
engine/clarity.py           # NEW: analyze_clarity(transcript) -> ClarityMetrics
engine/report.py            # MODIFY: analyze_answer passes language to transcribe; build_report adds clarity
engine/coach.py             # MODIFY (light): mention clarity in the prompt when present
web/app.py                  # MODIFY: GET /api/tracks
questions/language_jp.json  # NEW
web/static/index.html       # MODIFY: track <select>
web/static/recorder.js      # MODIFY: loadTracks() + loadQuestions(track)
web/static/results.js       # MODIFY: clarity in Delivery card
tests/test_transcribe.py    # MODIFY: _resolve tests + JP integration (skippable)
tests/test_fillers.py       # MODIFY: JP filler test + EN-unchanged test
tests/test_clarity.py       # NEW
tests/test_report.py        # MODIFY: clarity-present test
tests/test_coach.py         # MODIFY: clarity-in-prompt test
tests/test_web.py           # MODIFY: /api/tracks test
```

**Pre-req:** the interview track + acoustic fillers are built; 53 tests pass.

---

## Task 1: Language-aware transcription

**Files:** Modify `engine/transcribe.py`, `engine/report.py`, `tests/test_transcribe.py`.

- [ ] **Step 1: Append failing tests** to `tests/test_transcribe.py`:

```python
import os
import pytest

from engine.transcribe import _resolve, transcribe

JA_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello_ja.wav")


def test_resolve_english_uses_base_en():
    assert _resolve("en") == ("base.en", None)


def test_resolve_japanese_uses_multilingual():
    size, lang = _resolve("ja")
    assert lang == "ja"
    assert size != "base.en"


def test_resolve_explicit_model_override():
    assert _resolve("ja", "medium") == ("medium", "ja")


def test_resolve_explicit_model_english_no_forced_lang():
    assert _resolve("en", "small") == ("small", None)


@pytest.mark.skipif(not os.path.exists(JA_FIXTURE), reason="JP fixture missing")
def test_transcribe_japanese():
    tr = transcribe(JA_FIXTURE, language="ja")
    assert tr.language == "ja"
    assert any("぀" <= c <= "ヿ" or "一" <= c <= "鿿"
               for c in tr.text)   # contains kana/kanji
    assert len(tr.words) >= 1
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_transcribe.py -v`
Expected: FAIL — `cannot import name '_resolve'`.

- [ ] **Step 3: Replace `engine/transcribe.py`** with the language-aware version:

```python
from functools import lru_cache

from faster_whisper import WhisperModel

from engine.types import Word, Transcript

MULTILINGUAL_MODEL = "small"


@lru_cache(maxsize=3)
def _get_model(model_size: str) -> WhisperModel:
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def _resolve(language: str = "en", model_size: str | None = None):
    """Pick (model_size, whisper_language) for a track language."""
    if model_size is not None:
        return model_size, (None if language == "en" else language)
    if language == "en":
        return "base.en", None
    return MULTILINGUAL_MODEL, language


def transcribe(wav_path: str, language: str = "en",
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
```

- [ ] **Step 4: Wire language into the orchestrator** — in `engine/report.py`, change the transcribe call inside `analyze_answer`:
```python
    transcript = transcribe(wav, language=language)
```

- [ ] **Step 5: Generate the Japanese fixture (best-effort)**

Check Kyoko availability and generate:
```bash
if say -v '?' | grep -q Kyoko; then
  say -v Kyoko -o tests/fixtures/hello_ja.aiff "こんにちは。えーと、私の名前はダンです。"
  ffmpeg -y -i tests/fixtures/hello_ja.aiff -ac 1 -ar 16000 tests/fixtures/hello_ja.wav
  rm tests/fixtures/hello_ja.aiff
  echo "JP fixture created"
else
  echo "Kyoko voice not installed — JP integration test will skip"
fi
```
If Kyoko isn't installed, that's fine — the JP integration test is `skipif`-guarded. (`hello_ja.wav` is gitignored by `*.wav`.)

- [ ] **Step 6: Run tests**

Run: `.venv/bin/pytest tests/test_transcribe.py -v`
Expected: the 4 `_resolve` tests PASS; `test_transcribe_japanese` PASSES if the JP fixture exists (first run downloads the `small` multilingual model, ~one-time, allow several minutes — use a long timeout) or SKIPS if Kyoko was unavailable. The original English `test_transcribe_fixture` still passes (defaults → `base.en`).

- [ ] **Step 7: Full suite + commit**

Run: `.venv/bin/pytest -q` (expect all green: 57 if JP ran, 56 if it skipped).
```bash
git add engine/transcribe.py engine/report.py tests/test_transcribe.py
git commit -m "feat: language-aware transcription (multilingual model for non-English)"
```

If `test_transcribe_japanese` ran but the text contained no kana/kanji, report DONE_WITH_CONCERNS with the actual `tr.text` — do not weaken the assertion.

---

## Task 2: Japanese filler lexicon

**Files:** Modify `engine/fillers/lexicon.py`, `tests/test_fillers.py`.

- [ ] **Step 1: Append failing tests** to `tests/test_fillers.py`:

```python
def test_japanese_fillers_detected():
    from engine.types import Word, Transcript
    from engine.fillers import detect_fillers
    tr = Transcript(
        [Word("私", 0.0, 0.3), Word("えーと", 0.4, 0.9), Word("です", 1.0, 1.4)],
        "私 えーと です", 2.0, language="ja",
    )
    r = detect_fillers(tr)
    assert r.count == 1
    assert r.hits[0].text == "えーと"
    assert r.hits[0].source == "lexicon"


def test_english_filler_path_unchanged(make_transcript):
    # make_transcript defaults language="en"
    tr = make_transcript([("So", 0.0, 0.3), ("um", 0.4, 0.7)], duration=2.0)
    from engine.fillers import detect_fillers
    assert detect_fillers(tr).count == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_fillers.py::test_japanese_fillers_detected -v`
Expected: FAIL — `えーと` not detected (count 0) under the English-only lexicon.

- [ ] **Step 3: Replace `engine/fillers/lexicon.py`** with the language-aware version:

```python
from engine.types import Transcript
from engine.fillers.types import FillerHit

EN_SINGLE_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah",
                     "hmm", "mhm", "mm"}
EN_PHRASE_FILLERS = [("you", "know"), ("i", "mean"), ("sort", "of"), ("kind", "of")]
LIKE = "like"

JA_FILLERS = {"えーと", "えー", "ええと", "えっと", "あの", "あのー", "あのう",
              "その", "そのー", "まあ", "まぁ", "なんか", "んー", "あー", "ええ"}

_PUNCT = ".,!?;:\"'、。！？「」『』…　"


def _norm(s: str) -> str:
    return s.lower().strip().strip(_PUNCT).strip()


def detect_lexicon_fillers(transcript: Transcript,
                           include_like: bool = False) -> list[FillerHit]:
    if transcript.language == "ja":
        return _detect_ja(transcript)
    return _detect_en(transcript, include_like)


def _detect_ja(transcript: Transcript) -> list[FillerHit]:
    hits = [FillerHit(w.text, w.start, w.end, source="lexicon")
            for w in transcript.words if _norm(w.text) in JA_FILLERS]
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
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_fillers.py -v`
Expected: PASS — both new tests plus all existing `test_fillers.py` tests (the English logic is unchanged, just renamed constants).

- [ ] **Step 5: Full suite + commit**

Run: `.venv/bin/pytest -q` (all green).
```bash
git add engine/fillers/lexicon.py tests/test_fillers.py
git commit -m "feat: Japanese filler lexicon (language-aware detect_lexicon_fillers)"
```

---

## Task 3: Clarity proxy (mean word confidence)

**Files:** Create `engine/clarity.py`, `tests/test_clarity.py`; modify `engine/report.py`, `engine/coach.py`, `tests/test_report.py`, `tests/test_coach.py`.

- [ ] **Step 1: Write failing tests** in `tests/test_clarity.py`:

```python
from engine.types import Word, Transcript
from engine.clarity import analyze_clarity


def _tr(pairs):  # pairs: list of (text, probability)
    words = [Word(t, i * 0.5, i * 0.5 + 0.4, p) for i, (t, p) in enumerate(pairs)]
    return Transcript(words, " ".join(t for t, _ in pairs), 5.0)


def test_mean_confidence():
    c = analyze_clarity(_tr([("a", 0.9), ("b", 0.7)]))
    assert c.mean_confidence == 0.8


def test_low_confidence_words():
    c = analyze_clarity(_tr([("clear", 0.95), ("mumble", 0.3)]), low_threshold=0.5)
    assert c.low_confidence_words == ["mumble"]


def test_empty_transcript():
    c = analyze_clarity(Transcript([], "", 1.0))
    assert c.mean_confidence == 0.0
    assert c.low_confidence_words == []
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_clarity.py -v`
Expected: FAIL — `No module named 'engine.clarity'`.

- [ ] **Step 3: Create `engine/clarity.py`**:

```python
from dataclasses import dataclass

from engine.types import Transcript


@dataclass
class ClarityMetrics:
    mean_confidence: float
    low_confidence_words: list


def analyze_clarity(transcript: Transcript, low_threshold: float = 0.5) -> ClarityMetrics:
    words = transcript.words
    if not words:
        return ClarityMetrics(mean_confidence=0.0, low_confidence_words=[])
    confs = [w.probability for w in words]
    mean = round(sum(confs) / len(confs), 3)
    low = [w.text for w in words if w.probability < low_threshold]
    return ClarityMetrics(mean_confidence=mean, low_confidence_words=low)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_clarity.py -v`
Expected: PASS.

- [ ] **Step 5: Wire clarity into `engine/report.py`** — add the import and a `clarity` section in `build_report`.

Add import near the other engine imports:
```python
from engine.clarity import analyze_clarity
```
Change `build_report` so it computes clarity first (from the transcript it already receives), then includes a `clarity` key. The function becomes:
```python
def build_report(transcript: Transcript, delivery: DeliveryMetrics,
                 fillers: FillerReport, prosody: ProsodyMetrics,
                 content: ContentFeedback | None) -> dict:
    clarity = analyze_clarity(transcript)
    return {
        # ... existing transcript / delivery / fillers / prosody entries UNCHANGED ...
        "clarity": {"mean_confidence": clarity.mean_confidence,
                    "low_confidence_words": clarity.low_confidence_words},
        "content": None if content is None else asdict(content),
    }
```
Keep every existing key exactly as it was; only add the `clarity` line (placed right before `"content"`) and the `clarity = analyze_clarity(transcript)` first line.

- [ ] **Step 6: Add a clarity-present test** to `tests/test_report.py`:

```python
def test_build_report_includes_clarity(make_transcript):
    from engine.delivery import DeliveryMetrics
    from engine.fillers import FillerReport
    from engine.prosody import ProsodyMetrics
    from engine.report import build_report
    tr = make_transcript([("hi", 0.0, 0.4)], duration=1.0)  # Word.probability defaults 1.0
    report = build_report(tr, DeliveryMetrics(1.0, 0.4, 0.0, 0.0, [], 0),
                          FillerReport([], 0, 0.0),
                          ProsodyMetrics(0.0, 0.0, 0.0, True, 0.0), None)
    assert report["clarity"]["mean_confidence"] == 1.0
    assert report["clarity"]["low_confidence_words"] == []
```

- [ ] **Step 7: Light coach touch** — in `engine/coach.py`, in `build_summary_prompt`, after the existing metric `lines` are built (just before `metrics = "\n".join(lines)`), add:
```python
    cl = report.get("clarity")
    if cl:
        lines.append(f"- Clarity (confidence proxy): {cl['mean_confidence']}")
```
Add a test to `tests/test_coach.py`:
```python
def test_prompt_includes_clarity_when_present():
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 150.0, "long_pause_count": 0,
                     "time_to_first_word": 0.2},
        "fillers": {"count": 0, "per_minute": 0.0},
        "prosody": {"monotone": False},
        "content": None,
        "clarity": {"mean_confidence": 0.82, "low_confidence_words": []},
    }
    p = build_summary_prompt(report, language="en")
    assert "0.82" in p
```

- [ ] **Step 8: Full suite + commit**

Run: `.venv/bin/pytest -q`
Expected: all green (existing `test_report.py` / `test_coach.py` still pass — the `clarity` key is additive and `report.get("clarity")` is None in their fixtures).
```bash
git add engine/clarity.py engine/report.py engine/coach.py tests/test_clarity.py tests/test_report.py tests/test_coach.py
git commit -m "feat: clarity proxy (mean word confidence) in report + coach"
```

---

## Task 4: Japanese question library + /api/tracks

**Files:** Create `questions/language_jp.json`; modify `web/app.py`, `tests/test_web.py`.

- [ ] **Step 1: Create `questions/language_jp.json`**:

```json
{
  "track": "language_jp",
  "language": "ja",
  "questions": [
    {"id": "jp-self-intro", "category": "自己紹介",
     "prompt": "あなた自身について教えてください。趣味や仕事について話してください。"},
    {"id": "jp-daily", "category": "ナレーション",
     "prompt": "昨日一日の出来事を、順番に説明してください。"},
    {"id": "jp-photo", "category": "描写",
     "prompt": "今いる部屋の様子を、できるだけ詳しく描写してください。"},
    {"id": "jp-opinion", "category": "意見",
     "prompt": "リモートワークについてどう思いますか。理由とともに意見を述べてください。"},
    {"id": "jp-experience", "category": "経験",
     "prompt": "最近うれしかった出来事について話してください。"}
  ]
}
```

- [ ] **Step 2: Validate the JSON**

Run: `.venv/bin/python -c "import json; d=json.load(open('questions/language_jp.json')); print(d['track'], d['language'], len(d['questions']))"`
Expected: `language_jp ja 5`.

- [ ] **Step 3: Write a failing test** for `/api/tracks` — append to `tests/test_web.py`:

```python
def test_tracks_endpoint_lists_both():
    client = TestClient(appmod.app)
    body = client.get("/api/tracks").json()
    tracks = {t["track"]: t for t in body["tracks"]}
    assert "interview_en" in tracks
    assert "language_jp" in tracks
    assert tracks["language_jp"]["language"] == "ja"
```

- [ ] **Step 4: Run to verify failure**

Run: `.venv/bin/pytest tests/test_web.py::test_tracks_endpoint_lists_both -v`
Expected: FAIL — 404 (no `/api/tracks` route).

- [ ] **Step 5: Add the route to `web/app.py`** — above the `app.mount(...)` line:

```python
@app.get("/api/tracks")
def get_tracks():
    tracks = []
    for path in sorted(QUESTIONS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        tracks.append({"track": data["track"], "language": data["language"],
                       "count": len(data.get("questions", []))})
    return {"tracks": tracks}
```

- [ ] **Step 6: Run + commit**

Run: `.venv/bin/pytest tests/test_web.py -v` then `.venv/bin/pytest -q` (all green).
```bash
git add questions/language_jp.json web/app.py tests/test_web.py
git commit -m "feat: Japanese question library + /api/tracks endpoint"
```

---

## Task 5: Frontend track switching + clarity display

**Files:** Modify `web/static/index.html`, `web/static/recorder.js`, `web/static/results.js`.

- [ ] **Step 1: Add a track picker to `web/static/index.html`** — insert ABOVE the existing `<label>Question: …</label>`:
```html
  <label>Track:
    <select id="trackSelect"></select>
  </label>
```

- [ ] **Step 2: Update `web/static/recorder.js`** — replace the existing `loadQuestions` function AND its bare `loadQuestions();` call at the bottom with track-aware versions.

Add this near the other element lookups at the top:
```javascript
const trackSelect = document.getElementById("trackSelect");
```
Replace the whole `async function loadQuestions() { ... }` with:
```javascript
async function loadTracks() {
  try {
    const cfg = await (await fetch("/api/config")).json();
    window.ttsEnabled = !!cfg.tts_enabled;
  } catch (e) {
    window.ttsEnabled = false;
  }
  const data = await (await fetch("/api/tracks")).json();
  trackSelect.innerHTML = "";
  data.tracks.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.track;
    opt.textContent = `${t.track} (${t.language})`;
    trackSelect.appendChild(opt);
  });
  await loadQuestions(trackSelect.value);
}

trackSelect.addEventListener("change", () => loadQuestions(trackSelect.value));

async function loadQuestions(track) {
  const resp = await fetch("/api/questions?track=" + encodeURIComponent(track));
  const data = await resp.json();
  questions = data.questions;
  trackLanguage = data.language || "en";
  window.trackLanguage = trackLanguage;
  qSelect.innerHTML = "";
  questions.forEach((q, i) => {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = `[${q.category}] ${q.prompt.slice(0, 60)}…`;
    qSelect.appendChild(opt);
  });
  showQuestion();
}
```
Replace the bottom `loadQuestions();` line with:
```javascript
loadTracks();
```
(The old `loadQuestions()` used to fetch `/api/config` itself; that now happens once in `loadTracks()`. Everything else — recording, analyze, `form.append("language", trackLanguage)` — is unchanged.)

- [ ] **Step 3: Show clarity in `web/static/results.js`** — in `renderResults`, in the Delivery card metric list, add a clarity metric. Insert this line into the Delivery card template (after the `first word at …` metric, before the closing `</div>`):
```javascript
    ${report.clarity ? `<span class="metric">clarity <b>${Math.round(report.clarity.mean_confidence * 100)}%</b> <small>(confidence proxy)</small></span>` : ""}
```

- [ ] **Step 4: Headless verification**

```bash
.venv/bin/uvicorn web.app:app --port 8014 &
sleep 2
curl -s "http://localhost:8014/api/tracks" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sorted(t['track'] for t in d['tracks']))"
curl -s -o /dev/null -w "index:%{http_code}\n" http://localhost:8014/
curl -s -o /dev/null -w "recorder:%{http_code}\n" http://localhost:8014/recorder.js
curl -s "http://localhost:8014/api/questions?track=language_jp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['language'], len(d['questions']))"
pkill -f "uvicorn web.app:app"
```
Expected: track list `['interview_en', 'language_jp']`; both HTTP 200; `ja 5`. Then `.venv/bin/pytest -q` still green. KILL the server.

- [ ] **Step 5: Commit**

```bash
git add web/static/index.html web/static/recorder.js web/static/results.js
git commit -m "feat: frontend track switching (EN/JP) + clarity display"
```

---

## Definition of done

- [ ] `.venv/bin/pytest -q` fully green (≈66 tests; the one JP transcription integration test may skip if the Kyoko voice isn't installed).
- [ ] English path is unchanged: `transcribe(wav)` still uses `base.en`; English filler detection identical; existing tests pass untouched.
- [ ] `/api/tracks` lists `interview_en` + `language_jp`; the frontend switches tracks and sends the right `language` to `/api/analyze`.
- [ ] A Japanese answer flows end-to-end through the engine (multilingual transcribe → JP fillers + acoustic + delivery + clarity → JP coach), with the clarity proxy shown in the UI.
- [ ] `engine/` still has zero imports from `web/`.
- [ ] Manual (Dan): with the `small` model downloaded, switch to the Japanese track in the browser, record a JP answer, confirm Japanese transcript + Japanese coach summary (and JP voice if `ELEVENLABS_VOICE_JA` is set). Pace is known to read high for Japanese (documented rough edge).
- [ ] Phase 2 (per-phoneme pronunciation provider) remains a separate future plan.
