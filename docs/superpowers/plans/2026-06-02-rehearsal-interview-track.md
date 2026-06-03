# rehearsal — Interview/English Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the interview/English track end-to-end: record a spoken answer in the browser, upload it to a local server, and get AI feedback on delivery (pace, pauses, fillers, monotone) and content (answered? STAR? conciseness).

**Architecture:** A standalone, importable Python analysis engine (no web deps) wrapped by a thin FastAPI server that also serves a vanilla-JS frontend. The engine converts the upload to WAV, transcribes with faster-whisper (word timestamps), then runs pure analysis functions (timing, fillers) plus acoustic (parselmouth prosody) and an Ollama content LLM, merging everything into one feedback JSON.

**Tech Stack:** Python 3.11+, FastAPI + uvicorn, faster-whisper, praat-parselmouth, Ollama (local LLM), ffmpeg + macOS `say` (audio/fixtures), vanilla HTML/JS (`MediaRecorder`), pytest.

---

## File structure

```
rehearsal/
  pyproject.toml            # deps + pytest config (pythonpath=".")
  requirements.txt
  engine/
    __init__.py
    types.py                # Word, Transcript dataclasses (shared, no deps)
    audio.py                # to_wav(): ffmpeg convert upload -> 16k mono wav
    transcribe.py           # faster-whisper wrapper -> Transcript
    delivery.py             # analyze_delivery(): pace, pauses, talk-time (pure)
    fillers.py              # detect_fillers(): filler lexicon over transcript (pure)
    prosody.py              # summarize_pitch() (pure) + analyze_prosody() (parselmouth)
    content.py              # analyze_content(): Ollama interview-content feedback
    coach.py                # compose_spoken_summary(): local LLM warm summary (Task 13)
    tts/
      __init__.py
      config.py             # voice IDs per language (env), model id (Task 14)
      base.py               # TTSProvider interface + is_available() (Task 14)
      elevenlabs.py         # ElevenLabsProvider.synthesize() -> mp3 bytes (Task 14)
    report.py               # build_report() (pure) + analyze_answer() orchestrator
  web/
    __init__.py
    app.py                  # FastAPI: /api/questions, /api/analyze, /api/config, /api/speak
    static/
      index.html
      recorder.js
      results.js
  questions/
    interview_en.json       # seeded interview questions
  tests/
    conftest.py             # make_transcript fixture
    fixtures/
      hello.wav             # say-generated clip for integration tests
    test_delivery.py
    test_fillers.py
    test_prosody.py
    test_audio.py
    test_transcribe.py
    test_content.py
    test_report.py
    test_web.py
    test_coach.py
    test_tts.py
  docs/superpowers/
    specs/2026-06-02-rehearsal-design.md
    plans/2026-06-02-rehearsal-interview-track.md
    fillers-spike.md        # written in Task 12
```

**Note:** `engine/pronunciation/` and `questions/language_jp.json` belong to the *second* build target (JP track) and are intentionally NOT created here.

**System prerequisites (engineer must have):** `ffmpeg` on PATH, macOS `say`, and Ollama running with a model pulled (`ollama pull llama3.1`).

**Optional (spoken feedback, Tasks 13–15):** ElevenLabs is opt-in. The app runs fully without it. To exercise the voice layer, set these env vars (placeholders for now — Dan fills them in):
- `ELEVENLABS_API_KEY` — your ElevenLabs key
- `ELEVENLABS_VOICE_EN` — voice ID for English (used in v1)
- `ELEVENLABS_VOICE_JA` — voice ID for Japanese (slot for JP track #2)

When `ELEVENLABS_API_KEY` is unset, `/api/speak` returns 503 and the frontend hides the "Hear feedback" button — every other test stays green.

---

## Task 0: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `engine/__init__.py`, `web/__init__.py`, `web/static/index.html` (placeholder), `tests/fixtures/hello.wav`

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi
uvicorn[standard]
python-multipart
faster-whisper
praat-parselmouth
ollama
pytest
httpx
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "rehearsal"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 3: Create package markers and a placeholder static page**

Create `engine/__init__.py` (empty), `web/__init__.py` (empty), and `web/static/index.html`:

```html
<!doctype html><html><head><meta charset="utf-8"><title>rehearsal</title></head>
<body><p>placeholder</p></body></html>
```

(The placeholder lets `StaticFiles` mount cleanly before Task 11 replaces it.)

- [ ] **Step 4: Create the virtualenv and install deps**

Run:
```bash
cd /Users/danm/Development/rehearsal
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
Expected: installs complete without error.

- [ ] **Step 5: Generate the integration-test fixture clip**

Run:
```bash
mkdir -p tests/fixtures
say -o tests/fixtures/hello.aiff "Hello, um, my name is Dan, and uh, I am testing this."
ffmpeg -y -i tests/fixtures/hello.aiff -ac 1 -ar 16000 tests/fixtures/hello.wav
rm tests/fixtures/hello.aiff
```
Expected: `tests/fixtures/hello.wav` exists and is non-empty.

- [ ] **Step 6: Verify pytest runs (no tests yet)**

Run: `.venv/bin/pytest -q`
Expected: "no tests ran" (exit code 5) — confirms config loads.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold rehearsal project (deps, pytest config, fixture)"
```

---

## Task 1: Shared types + test helper

**Files:**
- Create: `engine/types.py`, `tests/conftest.py`

- [ ] **Step 1: Write `engine/types.py`**

```python
from dataclasses import dataclass


@dataclass
class Word:
    text: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class Transcript:
    words: list[Word]
    text: str
    duration: float
    language: str = "en"
```

- [ ] **Step 2: Write `tests/conftest.py` (shared `make_transcript` fixture)**

```python
import pytest

from engine.types import Word, Transcript


@pytest.fixture
def make_transcript():
    def _make(words, duration=None, language="en"):
        w = [Word(t, s, e) for (t, s, e) in words]
        dur = duration if duration is not None else (w[-1].end if w else 0.0)
        return Transcript(
            words=w,
            text=" ".join(t for t, _, _ in words),
            duration=dur,
            language=language,
        )
    return _make
```

- [ ] **Step 3: Add a sanity test in `tests/test_delivery.py` (stub) to confirm imports**

```python
from engine.types import Word, Transcript


def test_transcript_constructs(make_transcript):
    tr = make_transcript([("hi", 0.0, 0.4)])
    assert tr.words[0].text == "hi"
    assert tr.duration == 0.4
```

- [ ] **Step 4: Run it**

Run: `.venv/bin/pytest tests/test_delivery.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/types.py tests/conftest.py tests/test_delivery.py
git commit -m "feat: shared transcript types + test helper"
```

---

## Task 2: Delivery metrics (pace, pauses, talk-time)

**Files:**
- Create: `engine/delivery.py`
- Test: `tests/test_delivery.py`

- [ ] **Step 1: Write failing tests** (append to `tests/test_delivery.py`)

```python
from engine.delivery import analyze_delivery


def test_wpm_basic(make_transcript):
    # 4 words spanning t=0.0..2.0s -> 4 words / (2/60 min) = 120 wpm
    tr = make_transcript([("a", 0.0, 0.4), ("b", 0.5, 0.9),
                          ("c", 1.0, 1.4), ("d", 1.5, 2.0)])
    m = analyze_delivery(tr)
    assert m.words_per_minute == 120.0


def test_detects_long_pause(make_transcript):
    tr = make_transcript([("a", 0.0, 0.5), ("b", 3.0, 3.5)])  # 2.5s gap
    m = analyze_delivery(tr)
    assert len(m.pauses) == 1
    assert m.long_pause_count == 1
    assert round(m.pauses[0].duration, 1) == 2.5


def test_short_gap_not_a_pause(make_transcript):
    tr = make_transcript([("a", 0.0, 0.5), ("b", 0.7, 1.0)])  # 0.2s gap
    m = analyze_delivery(tr)
    assert m.pauses == []


def test_time_to_first_word(make_transcript):
    tr = make_transcript([("hello", 1.2, 1.6)], duration=2.0)
    m = analyze_delivery(tr)
    assert m.time_to_first_word == 1.2


def test_empty_transcript(make_transcript):
    tr = make_transcript([], duration=3.0)
    m = analyze_delivery(tr)
    assert m.words_per_minute == 0.0
    assert m.total_audio_time == 3.0
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_delivery.py -v`
Expected: FAIL — `cannot import name 'analyze_delivery'`.

- [ ] **Step 3: Implement `engine/delivery.py`**

```python
from dataclasses import dataclass

from engine.types import Transcript


@dataclass
class Pause:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class DeliveryMetrics:
    total_audio_time: float
    talk_time: float
    time_to_first_word: float
    words_per_minute: float
    pauses: list[Pause]
    long_pause_count: int


def analyze_delivery(
    transcript: Transcript,
    gap_threshold: float = 0.5,
    long_pause_threshold: float = 2.0,
) -> DeliveryMetrics:
    words = transcript.words
    if not words:
        return DeliveryMetrics(
            total_audio_time=transcript.duration,
            talk_time=0.0,
            time_to_first_word=transcript.duration,
            words_per_minute=0.0,
            pauses=[],
            long_pause_count=0,
        )

    first = words[0].start
    last = words[-1].end
    talk_time = last - first
    wpm = len(words) / (talk_time / 60) if talk_time > 0 else 0.0

    pauses = []
    for a, b in zip(words, words[1:]):
        gap = b.start - a.end
        if gap >= gap_threshold:
            pauses.append(Pause(a.end, b.start))
    long_pause_count = sum(1 for p in pauses if p.duration >= long_pause_threshold)

    return DeliveryMetrics(
        total_audio_time=transcript.duration,
        talk_time=round(talk_time, 2),
        time_to_first_word=round(first, 2),
        words_per_minute=round(wpm, 1),
        pauses=pauses,
        long_pause_count=long_pause_count,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_delivery.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add engine/delivery.py tests/test_delivery.py
git commit -m "feat: delivery metrics (wpm, pauses, talk-time)"
```

---

## Task 3: Filler-word detection

**Files:**
- Create: `engine/fillers.py`
- Test: `tests/test_fillers.py`

- [ ] **Step 1: Write failing tests** in `tests/test_fillers.py`

```python
from engine.fillers import detect_fillers


def test_counts_um_uh(make_transcript):
    tr = make_transcript(
        [("So", 0.0, 0.3), ("um", 0.4, 0.7), ("I", 0.8, 1.0),
         ("uh", 1.1, 1.4), ("left", 1.5, 1.9)],
        duration=2.0,
    )
    r = detect_fillers(tr)
    assert r.count == 2
    assert {h.text.lower() for h in r.hits} == {"um", "uh"}


def test_strips_punctuation(make_transcript):
    tr = make_transcript([("Um,", 0.0, 0.3), ("right", 0.4, 0.8)], duration=1.0)
    assert detect_fillers(tr).count == 1


def test_phrase_you_know(make_transcript):
    tr = make_transcript(
        [("it", 0.0, 0.3), ("you", 0.4, 0.6), ("know", 0.7, 0.9),
         ("worked", 1.0, 1.5)],
        duration=2.0,
    )
    r = detect_fillers(tr)
    assert r.count == 1
    assert r.hits[0].text.lower() == "you know"


def test_like_excluded_by_default(make_transcript):
    tr = make_transcript([("I", 0.0, 0.2), ("like", 0.3, 0.6), ("pizza", 0.7, 1.1)],
                         duration=2.0)
    assert detect_fillers(tr).count == 0
    assert detect_fillers(tr, include_like=True).count == 1


def test_per_minute(make_transcript):
    tr = make_transcript([("um", 0.0, 0.3)], duration=30.0)  # 1 filler in 0.5 min
    assert detect_fillers(tr).per_minute == 2.0
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_fillers.py -v`
Expected: FAIL — `cannot import name 'detect_fillers'`.

- [ ] **Step 3: Implement `engine/fillers.py`**

```python
from dataclasses import dataclass

from engine.types import Transcript

SINGLE_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mhm", "mm"}
PHRASE_FILLERS = [("you", "know"), ("i", "mean"), ("sort", "of"), ("kind", "of")]
LIKE = "like"


@dataclass
class FillerHit:
    text: str
    start: float
    end: float


@dataclass
class FillerReport:
    hits: list[FillerHit]
    count: int
    per_minute: float


def _norm(s: str) -> str:
    return s.lower().strip().strip(".,!?;:\"'").strip()


def detect_fillers(transcript: Transcript, include_like: bool = False) -> FillerReport:
    words = transcript.words
    norms = [_norm(w.text) for w in words]
    hits: list[FillerHit] = []
    used: set[int] = set()

    for i in range(len(words) - 1):
        if i in used or i + 1 in used:
            continue
        if (norms[i], norms[i + 1]) in PHRASE_FILLERS:
            hits.append(FillerHit(f"{words[i].text} {words[i + 1].text}",
                                  words[i].start, words[i + 1].end))
            used.add(i)
            used.add(i + 1)

    for i, w in enumerate(words):
        if i in used:
            continue
        if norms[i] in SINGLE_FILLERS or (include_like and norms[i] == LIKE):
            hits.append(FillerHit(w.text, w.start, w.end))
            used.add(i)

    hits.sort(key=lambda h: h.start)
    minutes = transcript.duration / 60 if transcript.duration > 0 else 1e-9
    return FillerReport(hits=hits, count=len(hits),
                        per_minute=round(len(hits) / minutes, 1))
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_fillers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/fillers.py tests/test_fillers.py
git commit -m "feat: filler-word detection (lexicon over transcript)"
```

---

## Task 4: Prosody (pitch / monotone / intensity)

**Files:**
- Create: `engine/prosody.py`
- Test: `tests/test_prosody.py`

- [ ] **Step 1: Write failing tests** in `tests/test_prosody.py`

```python
import os

import pytest

from engine.prosody import summarize_pitch, analyze_prosody

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")


def test_summarize_ignores_unvoiced_zeros():
    mean, std, rng, monotone = summarize_pitch([0, 0, 100, 100, 100])
    assert mean == 100.0
    assert std == 0.0
    assert monotone is True


def test_summarize_varied_not_monotone():
    mean, std, rng, monotone = summarize_pitch([80, 120, 160, 200, 240])
    assert monotone is False
    assert rng == 160.0


def test_summarize_empty():
    assert summarize_pitch([]) == (0.0, 0.0, 0.0, True)


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture missing")
def test_analyze_prosody_on_fixture():
    m = analyze_prosody(FIXTURE)
    assert m.mean_pitch_hz > 0          # voiced speech detected
    assert m.mean_intensity_db > 0
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_prosody.py -v`
Expected: FAIL — `cannot import name 'summarize_pitch'`.

- [ ] **Step 3: Implement `engine/prosody.py`**

```python
import statistics
from dataclasses import dataclass

import parselmouth
from parselmouth.praat import call


@dataclass
class ProsodyMetrics:
    mean_pitch_hz: float
    pitch_std_hz: float
    pitch_range_hz: float
    monotone: bool
    mean_intensity_db: float


def summarize_pitch(values, monotone_std_threshold: float = 20.0):
    voiced = [v for v in values if v and v > 0]
    if not voiced:
        return (0.0, 0.0, 0.0, True)
    mean = statistics.fmean(voiced)
    std = statistics.pstdev(voiced) if len(voiced) > 1 else 0.0
    rng = max(voiced) - min(voiced)
    return (round(mean, 1), round(std, 1), round(rng, 1),
            std < monotone_std_threshold)


def analyze_prosody(wav_path: str, monotone_std_threshold: float = 20.0) -> ProsodyMetrics:
    snd = parselmouth.Sound(wav_path)
    pitch = snd.to_pitch()
    values = list(pitch.selected_array["frequency"])
    mean, std, rng, monotone = summarize_pitch(values, monotone_std_threshold)
    intensity = snd.to_intensity()
    mean_db = round(float(call(intensity, "Get mean", 0, 0, "dB")), 1)
    return ProsodyMetrics(mean, std, rng, monotone, mean_db)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_prosody.py -v`
Expected: PASS (4 tests; the fixture test runs since Task 0 created `hello.wav`).

- [ ] **Step 5: Commit**

```bash
git add engine/prosody.py tests/test_prosody.py
git commit -m "feat: prosody analysis (pitch stats, monotone, intensity)"
```

---

## Task 5: Audio conversion to WAV

**Files:**
- Create: `engine/audio.py`
- Test: `tests/test_audio.py`

- [ ] **Step 1: Write failing test** in `tests/test_audio.py`

```python
import os
import subprocess

from engine.audio import to_wav

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")


def test_to_wav_produces_16k_mono(tmp_path):
    # Re-encode the fixture to a non-wav container, then convert back.
    src = tmp_path / "in.m4a"
    subprocess.run(["ffmpeg", "-y", "-i", FIXTURE, str(src)],
                   check=True, capture_output=True)
    out = to_wav(str(src), str(tmp_path / "out.wav"))
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=channels,sample_rate", "-of", "csv=p=0", out],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "16000" in probe
    assert probe.strip().split(",")[0] == "1"  # mono
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_audio.py -v`
Expected: FAIL — `cannot import name 'to_wav'`.

- [ ] **Step 3: Implement `engine/audio.py`**

```python
import os
import subprocess


def to_wav(src_path: str, dst_path: str | None = None, sample_rate: int = 16000) -> str:
    if dst_path is None:
        dst_path = os.path.splitext(src_path)[0] + ".converted.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-ac", "1", "-ar", str(sample_rate), dst_path],
        check=True, capture_output=True,
    )
    return dst_path
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_audio.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/audio.py tests/test_audio.py
git commit -m "feat: ffmpeg WAV conversion for uploads"
```

---

## Task 6: Transcription (faster-whisper)

**Files:**
- Create: `engine/transcribe.py`
- Test: `tests/test_transcribe.py`

- [ ] **Step 1: Write failing test** in `tests/test_transcribe.py`

```python
import os

import pytest

from engine.transcribe import transcribe

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture missing")
def test_transcribe_fixture():
    tr = transcribe(FIXTURE)
    assert "name" in tr.text.lower()
    assert len(tr.words) >= 4
    assert tr.duration > 0
    # word timestamps are monotonic and within the clip
    for w in tr.words:
        assert w.start >= 0
        assert w.end >= w.start
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_transcribe.py -v`
Expected: FAIL — `cannot import name 'transcribe'`.

- [ ] **Step 3: Implement `engine/transcribe.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_transcribe.py -v`
Expected: PASS (first run downloads the `base.en` model; allow time).

- [ ] **Step 5: Commit**

```bash
git add engine/transcribe.py tests/test_transcribe.py
git commit -m "feat: faster-whisper transcription with word timestamps"
```

---

## Task 7: Content analysis (Ollama interview feedback)

**Files:**
- Create: `engine/content.py`
- Test: `tests/test_content.py`

- [ ] **Step 1: Write failing tests** in `tests/test_content.py`

```python
import json

from engine.content import build_prompt, parse_response, analyze_content


def test_build_prompt_includes_question_and_answer():
    p = build_prompt("Tell me about a conflict", "I had a disagreement once")
    assert "Tell me about a conflict" in p
    assert "I had a disagreement once" in p


def test_parse_response_computes_missing_and_caps_notes():
    raw = json.dumps({
        "answered_question": True,
        "answered_explanation": "ok",
        "star_present": {"situation": True, "task": False,
                         "action": True, "result": False},
        "issues": ["rambled"],
        "tighter_rewrite": "short",
        "coaching_notes": ["a", "b", "c", "d"],
    })
    fb = parse_response(raw)
    assert fb.star_missing == ["task", "result"]
    assert fb.coaching_notes == ["a", "b", "c"]
    assert fb.answered_question is True


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.kw = None

    def chat(self, **kw):
        self.kw = kw
        return {"message": {"content": self.payload}}


def test_analyze_content_uses_client_and_json_format():
    payload = json.dumps({
        "answered_question": False, "answered_explanation": "no",
        "star_present": {}, "issues": [], "tighter_rewrite": "",
        "coaching_notes": [],
    })
    client = FakeClient(payload)
    fb = analyze_content("Q?", "I dunno", client=client)
    assert fb.answered_question is False
    assert fb.star_missing == ["situation", "task", "action", "result"]
    assert client.kw["format"] == "json"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_content.py -v`
Expected: FAIL — `cannot import name 'build_prompt'`.

- [ ] **Step 3: Implement `engine/content.py`**

```python
import json
from dataclasses import dataclass

import ollama

STAR_KEYS = ("situation", "task", "action", "result")

SYSTEM = (
    "You are a concise, candid interview coach. You analyze a transcribed spoken "
    "answer to an interview question and return structured JSON feedback. Be "
    "specific and practical. Never invent facts the candidate did not say."
)


@dataclass
class ContentFeedback:
    answered_question: bool
    answered_explanation: str
    star_present: dict
    star_missing: list
    issues: list
    tighter_rewrite: str
    coaching_notes: list


def build_prompt(question: str, answer: str) -> str:
    return (
        f"Interview question:\n{question}\n\n"
        f"Candidate's transcribed answer:\n{answer}\n\n"
        "Return ONLY JSON with these keys:\n"
        "- answered_question (boolean): did they actually answer what was asked\n"
        "- answered_explanation (string, one sentence)\n"
        "- star_present (object with booleans: situation, task, action, result)\n"
        "- issues (array of short strings: rambling, hedging, vague claims, etc.)\n"
        "- tighter_rewrite (string, an improved answer, <=120 words)\n"
        "- coaching_notes (array of exactly 3 short actionable tips)"
    )


def parse_response(raw: str) -> ContentFeedback:
    data = json.loads(raw)
    star_raw = data.get("star_present", {}) or {}
    star_present = {k: bool(star_raw.get(k)) for k in STAR_KEYS}
    star_missing = [k for k in STAR_KEYS if not star_present[k]]
    return ContentFeedback(
        answered_question=bool(data.get("answered_question", False)),
        answered_explanation=data.get("answered_explanation", ""),
        star_present=star_present,
        star_missing=star_missing,
        issues=list(data.get("issues", [])),
        tighter_rewrite=data.get("tighter_rewrite", ""),
        coaching_notes=list(data.get("coaching_notes", []))[:3],
    )


def analyze_content(question: str, answer: str, model: str = "llama3.1",
                    client=ollama) -> ContentFeedback:
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(question, answer)},
        ],
        format="json",
    )
    return parse_response(resp["message"]["content"])
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_content.py -v`
Expected: PASS (no Ollama needed — the client is faked).

- [ ] **Step 5: Commit**

```bash
git add engine/content.py tests/test_content.py
git commit -m "feat: Ollama interview-content analysis (STAR, conciseness)"
```

---

## Task 8: Report assembly + orchestrator

**Files:**
- Create: `engine/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write failing test** in `tests/test_report.py`

```python
from engine.delivery import DeliveryMetrics, Pause
from engine.fillers import FillerReport, FillerHit
from engine.prosody import ProsodyMetrics
from engine.content import ContentFeedback
from engine.report import build_report


def test_build_report_shape(make_transcript):
    tr = make_transcript([("hello", 0.0, 0.5), ("world", 0.6, 1.0)], duration=2.0)
    delivery = DeliveryMetrics(
        total_audio_time=2.0, talk_time=1.0, time_to_first_word=0.0,
        words_per_minute=120.0, pauses=[Pause(0.5, 0.6)], long_pause_count=0,
    )
    fillers = FillerReport(hits=[FillerHit("um", 0.4, 0.6)], count=1, per_minute=0.5)
    prosody = ProsodyMetrics(150.0, 30.0, 90.0, False, 60.0)
    content = ContentFeedback(
        answered_question=True, answered_explanation="ok",
        star_present={"situation": True, "task": True, "action": True, "result": False},
        star_missing=["result"], issues=[], tighter_rewrite="x",
        coaching_notes=["a", "b", "c"],
    )

    report = build_report(tr, delivery, fillers, prosody, content)

    assert report["transcript"]["text"] == "hello world"
    assert report["delivery"]["words_per_minute"] == 120.0
    assert report["fillers"]["count"] == 1
    assert report["prosody"]["monotone"] is False
    assert report["content"]["star_missing"] == ["result"]


def test_build_report_without_content(make_transcript):
    tr = make_transcript([("hi", 0.0, 0.4)], duration=1.0)
    delivery = DeliveryMetrics(1.0, 0.4, 0.0, 0.0, [], 0)
    fillers = FillerReport([], 0, 0.0)
    prosody = ProsodyMetrics(0.0, 0.0, 0.0, True, 0.0)
    report = build_report(tr, delivery, fillers, prosody, None)
    assert report["content"] is None
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_report.py -v`
Expected: FAIL — `cannot import name 'build_report'`.

- [ ] **Step 3: Implement `engine/report.py`**

```python
from dataclasses import asdict

from engine.types import Transcript
from engine.delivery import DeliveryMetrics, analyze_delivery
from engine.fillers import FillerReport, detect_fillers
from engine.prosody import ProsodyMetrics, analyze_prosody
from engine.content import ContentFeedback, analyze_content
from engine.audio import to_wav
from engine.transcribe import transcribe


def _pauses_json(pauses):
    return [{"start": round(p.start, 2), "end": round(p.end, 2),
             "duration": round(p.duration, 2)} for p in pauses]


def build_report(transcript: Transcript, delivery: DeliveryMetrics,
                 fillers: FillerReport, prosody: ProsodyMetrics,
                 content: ContentFeedback | None) -> dict:
    return {
        "transcript": {
            "text": transcript.text,
            "duration": round(transcript.duration, 2),
            "words": [{"text": w.text, "start": round(w.start, 2),
                       "end": round(w.end, 2)} for w in transcript.words],
        },
        "delivery": {
            "words_per_minute": delivery.words_per_minute,
            "talk_time": round(delivery.talk_time, 2),
            "time_to_first_word": round(delivery.time_to_first_word, 2),
            "long_pause_count": delivery.long_pause_count,
            "pauses": _pauses_json(delivery.pauses),
        },
        "fillers": {
            "count": fillers.count,
            "per_minute": fillers.per_minute,
            "hits": [{"text": h.text, "start": round(h.start, 2),
                      "end": round(h.end, 2)} for h in fillers.hits],
        },
        "prosody": {
            "mean_pitch_hz": prosody.mean_pitch_hz,
            "pitch_std_hz": prosody.pitch_std_hz,
            "pitch_range_hz": prosody.pitch_range_hz,
            "monotone": prosody.monotone,
            "mean_intensity_db": prosody.mean_intensity_db,
        },
        "content": None if content is None else asdict(content),
    }


def analyze_answer(audio_path: str, question: str, *, run_content: bool = True,
                   content_model: str = "llama3.1") -> dict:
    wav = to_wav(audio_path)
    transcript = transcribe(wav)
    delivery = analyze_delivery(transcript)
    fillers = detect_fillers(transcript)
    prosody = analyze_prosody(wav)
    content = (analyze_content(question, transcript.text, model=content_model)
               if run_content and transcript.text else None)
    return build_report(transcript, delivery, fillers, prosody, content)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_report.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/report.py tests/test_report.py
git commit -m "feat: report assembly + analyze_answer orchestrator"
```

---

## Task 9: Seeded question library

**Files:**
- Create: `questions/interview_en.json`

- [ ] **Step 1: Write `questions/interview_en.json`**

```json
{
  "track": "interview_en",
  "language": "en",
  "questions": [
    {"id": "behavioral-conflict", "category": "Behavioral",
     "prompt": "Tell me about a time you had a conflict with a coworker and how you resolved it."},
    {"id": "behavioral-failure", "category": "Behavioral",
     "prompt": "Describe a time you failed. What happened and what did you learn?"},
    {"id": "leadership-influence", "category": "Leadership",
     "prompt": "Tell me about a time you influenced a decision without having formal authority."},
    {"id": "behavioral-deadline", "category": "Behavioral",
     "prompt": "Describe a situation where you had to meet a tight deadline under pressure."},
    {"id": "general-strength", "category": "General",
     "prompt": "What is your greatest strength, and can you give a concrete example of it in action?"}
  ]
}
```

- [ ] **Step 2: Validate JSON**

Run: `.venv/bin/python -c "import json; json.load(open('questions/interview_en.json'))"`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git add questions/interview_en.json
git commit -m "feat: seeded interview_en question library"
```

---

## Task 10: FastAPI server

**Files:**
- Create: `web/app.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write failing tests** in `tests/test_web.py`

```python
from fastapi.testclient import TestClient

import web.app as appmod


def test_questions_endpoint():
    client = TestClient(appmod.app)
    resp = client.get("/api/questions?track=interview_en")
    assert resp.status_code == 200
    body = resp.json()
    assert body["track"] == "interview_en"
    assert len(body["questions"]) >= 1


def test_questions_unknown_track_404():
    client = TestClient(appmod.app)
    resp = client.get("/api/questions?track=nope")
    assert resp.status_code == 404


def test_analyze_endpoint_calls_engine(monkeypatch):
    captured = {}

    def fake_analyze(audio_path, question, **kwargs):
        captured["question"] = question
        return {"ok": True}

    monkeypatch.setattr(appmod, "analyze_answer", fake_analyze)
    client = TestClient(appmod.app)
    resp = client.post(
        "/api/analyze",
        data={"question": "Tell me about yourself"},
        files={"audio": ("a.webm", b"fakebytes", "audio/webm")},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert captured["question"] == "Tell me about yourself"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_web.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'web.app'`.

- [ ] **Step 3: Implement `web/app.py`**

```python
import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from engine.report import analyze_answer

BASE = Path(__file__).resolve().parent
QUESTIONS_DIR = BASE.parent / "questions"

app = FastAPI(title="rehearsal")


@app.get("/api/questions")
def get_questions(track: str = "interview_en"):
    path = QUESTIONS_DIR / f"{track}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"unknown track: {track}")
    return json.loads(path.read_text())


@app.post("/api/analyze")
async def analyze(
    question: str = Form(...),
    audio: UploadFile = File(...),
    run_content: bool = Form(True),
):
    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        report = analyze_answer(tmp_path, question, run_content=run_content)
    finally:
        os.unlink(tmp_path)
    return JSONResponse(report)


# Serve the frontend (index.html etc.). Mounted last so /api routes win.
app.mount("/", StaticFiles(directory=str(BASE / "static"), html=True), name="static")
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_web.py -v`
Expected: PASS (engine is monkeypatched, so no heavy deps run).

- [ ] **Step 5: Full suite green**

Run: `.venv/bin/pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/app.py tests/test_web.py
git commit -m "feat: FastAPI server (questions + analyze endpoints)"
```

---

## Task 11: Frontend (record → analyze → results)

**Files:**
- Modify: `web/static/index.html` (replace placeholder)
- Create: `web/static/recorder.js`, `web/static/results.js`

- [ ] **Step 1: Write `web/static/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>rehearsal — interview practice</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; }
    select, button { font-size: 1rem; padding: 0.5rem; }
    button { cursor: pointer; }
    #question { font-size: 1.25rem; margin: 1rem 0; padding: 1rem; background: #f4f4f5; border-radius: 8px; }
    .controls { display: flex; gap: 0.5rem; align-items: center; margin: 1rem 0; }
    .rec-on { color: #b91c1c; font-weight: 600; }
    .metric { display: inline-block; margin: 0.25rem 1rem 0.25rem 0; }
    .filler { background: #fde68a; border-radius: 3px; padding: 0 2px; }
    .pause { color: #6b7280; font-style: italic; }
    #results { margin-top: 1.5rem; }
    .card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; margin: 0.75rem 0; }
    .hidden { display: none; }
  </style>
</head>
<body>
  <h1>rehearsal</h1>
  <label>Question:
    <select id="questionSelect"></select>
  </label>
  <div id="question">Loading questions…</div>

  <div class="controls">
    <button id="recordBtn">● Record</button>
    <button id="stopBtn" disabled>■ Stop</button>
    <span id="status"></span>
  </div>

  <audio id="playback" controls class="hidden"></audio>
  <div class="controls">
    <button id="analyzeBtn" disabled>Analyze answer</button>
  </div>

  <div id="results"></div>

  <script src="recorder.js"></script>
  <script src="results.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `web/static/recorder.js`**

```javascript
let mediaRecorder = null;
let chunks = [];
let lastBlob = null;
let questions = [];

const qSelect = document.getElementById("questionSelect");
const qText = document.getElementById("question");
const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const playback = document.getElementById("playback");
const statusEl = document.getElementById("status");

async function loadQuestions() {
  const resp = await fetch("/api/questions?track=interview_en");
  const data = await resp.json();
  questions = data.questions;
  qSelect.innerHTML = "";
  questions.forEach((q, i) => {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = `[${q.category}] ${q.prompt.slice(0, 60)}…`;
    qSelect.appendChild(opt);
  });
  showQuestion();
}

function currentQuestion() {
  return questions[Number(qSelect.value)];
}

function showQuestion() {
  qText.textContent = currentQuestion().prompt;
}

qSelect.addEventListener("change", showQuestion);

recordBtn.addEventListener("click", async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  chunks = [];
  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
  mediaRecorder.onstop = () => {
    lastBlob = new Blob(chunks, { type: "audio/webm" });
    playback.src = URL.createObjectURL(lastBlob);
    playback.classList.remove("hidden");
    analyzeBtn.disabled = false;
    stream.getTracks().forEach((t) => t.stop());
  };
  mediaRecorder.start();
  recordBtn.disabled = true;
  stopBtn.disabled = false;
  analyzeBtn.disabled = true;
  statusEl.textContent = "Recording…";
  statusEl.className = "rec-on";
});

stopBtn.addEventListener("click", () => {
  mediaRecorder.stop();
  recordBtn.disabled = false;
  stopBtn.disabled = true;
  statusEl.textContent = "";
  statusEl.className = "";
});

analyzeBtn.addEventListener("click", async () => {
  if (!lastBlob) return;
  analyzeBtn.disabled = true;
  statusEl.textContent = "Analyzing… (this can take a few seconds)";
  const form = new FormData();
  form.append("question", currentQuestion().prompt);
  form.append("audio", lastBlob, "answer.webm");
  try {
    const resp = await fetch("/api/analyze", { method: "POST", body: form });
    const report = await resp.json();
    window.renderResults(report);
  } finally {
    statusEl.textContent = "";
    analyzeBtn.disabled = false;
  }
});

loadQuestions();
```

- [ ] **Step 3: Write `web/static/results.js`**

```javascript
function annotateTranscript(report) {
  const words = report.transcript.words;
  const fillerStarts = new Set(report.fillers.hits.map((h) => h.start));
  const pauseAfter = {}; // word index -> pause duration
  // mark a pause when a gap precedes a word
  for (let i = 1; i < words.length; i++) {
    const gap = words[i].start - words[i - 1].end;
    if (gap >= 0.5) pauseAfter[i - 1] = gap;
  }
  const parts = [];
  words.forEach((w, i) => {
    if (fillerStarts.has(w.start)) {
      parts.push(`<span class="filler">${w.text}</span>`);
    } else {
      parts.push(w.text);
    }
    if (pauseAfter[i]) {
      parts.push(`<span class="pause"> …(${pauseAfter[i].toFixed(1)}s)… </span>`);
    }
  });
  return parts.join(" ");
}

window.renderResults = function (report) {
  const d = report.delivery;
  const f = report.fillers;
  const p = report.prosody;
  const c = report.content;

  let html = "";

  html += `<div class="card"><h2>Delivery</h2>
    <span class="metric"><b>${d.words_per_minute}</b> wpm</span>
    <span class="metric"><b>${f.count}</b> fillers (${f.per_minute}/min)</span>
    <span class="metric"><b>${d.long_pause_count}</b> long pauses</span>
    <span class="metric">monotone: <b>${p.monotone ? "yes" : "no"}</b> (pitch σ ${p.pitch_std_hz}Hz)</span>
    <span class="metric">first word at <b>${d.time_to_first_word}s</b></span>
  </div>`;

  html += `<div class="card"><h2>Transcript</h2>
    <p>${annotateTranscript(report)}</p>
    <small>Highlighted = filler word · italic = pause</small></div>`;

  if (c) {
    const star = Object.entries(c.star_present)
      .map(([k, v]) => `${v ? "✅" : "⬜️"} ${k}`)
      .join("  ");
    html += `<div class="card"><h2>Content</h2>
      <p><b>Answered the question:</b> ${c.answered_question ? "yes" : "no"} — ${c.answered_explanation}</p>
      <p><b>STAR:</b> ${star}</p>
      ${c.issues.length ? `<p><b>Watch out:</b> ${c.issues.join("; ")}</p>` : ""}
      <p><b>Tighter version:</b> ${c.tighter_rewrite}</p>
      <p><b>Next time, try:</b></p>
      <ul>${c.coaching_notes.map((n) => `<li>${n}</li>`).join("")}</ul>
    </div>`;
  }

  document.getElementById("results").innerHTML = html;
};
```

- [ ] **Step 4: Manual smoke test** (browser MediaRecorder can't be unit-tested headlessly)

Run the server:
```bash
cd /Users/danm/Development/rehearsal
.venv/bin/uvicorn web.app:app --reload --port 8000
```
Then in a browser (Chrome/Safari) open `http://localhost:8000` and verify, in order:
1. The question dropdown populates and selecting one updates the prompt text.
2. Clicking **Record** prompts for mic permission and shows "Recording…".
3. Speak a ~30s answer including a couple of deliberate "um"s and a long pause.
4. Clicking **Stop** shows the audio player; **Analyze** becomes enabled.
5. Clicking **Analyze** shows "Analyzing…", then within a few seconds renders:
   - Delivery card with a plausible wpm, the filler count ≥ 1, long-pause count ≥ 1.
   - Transcript with your "um"s highlighted and the pause marked.
   - Content card with answered/STAR/coaching notes (requires Ollama running with `llama3.1`).

Record the result of each numbered check. If any fails, debug before committing.

- [ ] **Step 5: Commit**

```bash
git add web/static/index.html web/static/recorder.js web/static/results.js
git commit -m "feat: browser frontend (record, analyze, annotated results)"
```

---

## Task 12: Filler-detection accuracy spike (de-risk)

**Files:**
- Create: `docs/superpowers/fillers-spike.md`, `scripts/filler_eval.py`

This validates the highest-risk module against *real* speech, where Whisper drops many fillers (unlike the clean `say`-synthesized fixture).

- [ ] **Step 1: Record labeled clips**

Record 8–10 short clips of yourself speaking naturally, each with a **known, written-down count** of "um/uh/like/you know". Save as `tests/fixtures/spike/clip01.webm`, etc., and create `tests/fixtures/spike/labels.json`:

```json
[
  {"file": "clip01.webm", "fillers": 3},
  {"file": "clip02.webm", "fillers": 0}
]
```

- [ ] **Step 2: Write `scripts/filler_eval.py`**

```python
import json
import os
import sys

from engine.audio import to_wav
from engine.transcribe import transcribe
from engine.fillers import detect_fillers

SPIKE = os.path.join("tests", "fixtures", "spike")


def main():
    labels = json.load(open(os.path.join(SPIKE, "labels.json")))
    total_true = total_pred = 0
    print(f"{'file':16} {'expected':>8} {'detected':>8}")
    for item in labels:
        wav = to_wav(os.path.join(SPIKE, item["file"]))
        tr = transcribe(wav)
        rep = detect_fillers(tr)
        total_true += item["fillers"]
        total_pred += rep.count
        print(f"{item['file']:16} {item['fillers']:>8} {rep.count:>8}")
    recall_proxy = total_pred / total_true if total_true else 0.0
    print(f"\nTotal expected: {total_true}  detected: {total_pred}  "
          f"(detected/expected = {recall_proxy:.2f})")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run the evaluation**

Run: `.venv/bin/python scripts/filler_eval.py`
Expected: a per-clip table and an overall detected/expected ratio.

- [ ] **Step 4: Write findings to `docs/superpowers/fillers-spike.md`**

Record: the detected/expected ratio, which filler types Whisper dropped most (typically bare "um/uh"), and a recommendation — if the ratio is well below ~0.7, the next iteration should add an **acoustic filled-pause detector** (e.g., forced alignment or a small wav2vec2 classifier) rather than relying on the transcript lexicon. Keep this as the decision record for whether to invest further.

- [ ] **Step 5: Commit**

```bash
git add scripts/filler_eval.py docs/superpowers/fillers-spike.md tests/fixtures/spike/labels.json
git commit -m "test: filler-detection accuracy spike + findings"
```

(Do not commit the `.webm` clips of your voice — they're covered by `.gitignore`.)

---

## Task 13: Coach — local LLM spoken-summary script

The core interview track is now working end-to-end. This adds the **local** half of the
spoken-feedback layer: a warm, patient summary written by Ollama. Nothing leaves the
machine here — this is just text generation. Cloud voicing is Task 14.

**Files:**
- Create: `engine/coach.py`
- Modify: `engine/report.py` (wire `spoken_summary` into `analyze_answer`)
- Test: `tests/test_coach.py`

- [ ] **Step 1: Write failing tests** in `tests/test_coach.py`

```python
from engine.coach import build_summary_prompt, compose_spoken_summary


def _report():
    return {
        "delivery": {"words_per_minute": 165.0, "long_pause_count": 2,
                     "time_to_first_word": 0.5},
        "fillers": {"count": 4, "per_minute": 6.0},
        "prosody": {"monotone": True},
        "content": {"answered_question": True, "star_missing": ["result"]},
    }


def test_prompt_includes_metrics_and_language():
    p = build_summary_prompt(_report(), language="en")
    assert "165" in p
    assert "English" in p


def test_prompt_japanese_language_name():
    p = build_summary_prompt(_report(), language="ja")
    assert "Japanese" in p


def test_prompt_handles_missing_content():
    report = _report()
    report["content"] = None
    p = build_summary_prompt(report, language="en")
    assert "165" in p  # still summarizes delivery without content


class FakeClient:
    def __init__(self, text):
        self.text = text
        self.kw = None

    def chat(self, **kw):
        self.kw = kw
        return {"message": {"content": self.text}}


def test_compose_strips_and_returns_text():
    client = FakeClient("  You spoke at a nice pace. Try a breath next time.  ")
    out = compose_spoken_summary(_report(), language="en", client=client)
    assert out == "You spoke at a nice pace. Try a breath next time."
    # prose generation, not JSON mode
    assert "format" not in client.kw
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_coach.py -v`
Expected: FAIL — `cannot import name 'build_summary_prompt'`.

- [ ] **Step 3: Implement `engine/coach.py`**

```python
import ollama

COACH_SYSTEM = (
    "You are a warm, patient, encouraging speaking coach. You address the person "
    "directly as 'you'. You are kind and never harsh. Your summary will be read "
    "aloud, so write natural flowing spoken sentences — no lists, no markdown, no "
    "headings, no emoji."
)

LANGUAGE_NAMES = {"en": "English", "ja": "Japanese"}


def build_summary_prompt(report: dict, language: str = "en") -> str:
    d = report["delivery"]
    f = report["fillers"]
    p = report["prosody"]
    c = report.get("content")
    lang_name = LANGUAGE_NAMES.get(language, "English")

    lines = [
        "Metrics from the person's spoken answer:",
        f"- Speaking rate: {d['words_per_minute']} words per minute",
        f"- Filler words: {f['count']} total",
        f"- Long pauses: {d['long_pause_count']}",
        f"- Monotone delivery: {'yes' if p['monotone'] else 'no'}",
    ]
    if c:
        lines.append(
            f"- Answered the question: {'yes' if c['answered_question'] else 'no'}"
        )
        if c.get("star_missing"):
            lines.append(f"- Missing STAR parts: {', '.join(c['star_missing'])}")
    metrics = "\n".join(lines)

    return (
        f"{metrics}\n\n"
        f"Write a short spoken summary in {lang_name}, 3 to 5 sentences, in a kind and "
        f"patient tone. Touch on their pace, the one or two most important delivery "
        f"notes, and end with one encouraging, specific thing to try next time. Plain "
        f"spoken prose only."
    )


def compose_spoken_summary(report: dict, language: str = "en",
                           model: str = "llama3.1", client=ollama) -> str:
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": COACH_SYSTEM},
            {"role": "user", "content": build_summary_prompt(report, language)},
        ],
    )
    return resp["message"]["content"].strip()
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_coach.py -v`
Expected: PASS.

- [ ] **Step 5: Wire `spoken_summary` into `engine/report.py`**

Add the import near the other engine imports:

```python
from engine.coach import compose_spoken_summary
```

Replace the existing `analyze_answer` function with this version (adds a `language`
parameter and the `spoken_summary` field; everything else unchanged):

```python
def analyze_answer(audio_path: str, question: str, *, language: str = "en",
                   run_content: bool = True, content_model: str = "llama3.1") -> dict:
    wav = to_wav(audio_path)
    transcript = transcribe(wav)
    delivery = analyze_delivery(transcript)
    fillers = detect_fillers(transcript)
    prosody = analyze_prosody(wav)
    content = (analyze_content(question, transcript.text, model=content_model)
               if run_content and transcript.text else None)
    report = build_report(transcript, delivery, fillers, prosody, content)
    report["spoken_summary"] = (
        compose_spoken_summary(report, language=language, model=content_model)
        if run_content and transcript.text else None
    )
    return report
```

- [ ] **Step 6: Confirm the full suite is still green**

Run: `.venv/bin/pytest -q`
Expected: all tests pass (`build_report` tests unchanged — `spoken_summary` is added in
`analyze_answer`, not `build_report`).

- [ ] **Step 7: Commit**

```bash
git add engine/coach.py engine/report.py tests/test_coach.py
git commit -m "feat: local LLM coach spoken-summary script"
```

---

## Task 14: TTS provider (ElevenLabs) + speak/config endpoints

The cloud half: voice the summary text via ElevenLabs, opt-in behind an API key.

**Files:**
- Create: `engine/tts/__init__.py`, `engine/tts/config.py`, `engine/tts/base.py`, `engine/tts/elevenlabs.py`
- Modify: `web/app.py` (add `/api/config`, `/api/speak`; forward `language` in `/api/analyze`)
- Test: `tests/test_tts.py`, additions to `tests/test_web.py`

- [ ] **Step 1: Write failing tests** in `tests/test_tts.py`

```python
import pytest

from engine.tts import config
from engine.tts.base import TTSError
from engine.tts.elevenlabs import ElevenLabsProvider


def test_voice_for_reads_env(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE_EN", "voice123")
    assert config.voice_for("en") == "voice123"
    monkeypatch.setenv("ELEVENLABS_VOICE_JA", "voiceJA")
    assert config.voice_for("ja") == "voiceJA"


def test_is_available_follows_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert config.is_available() is False
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    assert config.is_available() is True


def test_synthesize_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(TTSError):
        ElevenLabsProvider().synthesize("hello", "en")


class FakeResp:
    def __init__(self, status_code=200, content=b"AUDIO", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeClient:
    def __init__(self, resp):
        self.resp = resp
        self.call = None

    def post(self, url, **kw):
        self.call = {"url": url, **kw}
        return self.resp


def test_synthesize_posts_and_returns_bytes(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_VOICE_EN", "voiceEN")
    fake = FakeClient(FakeResp(200, b"MP3BYTES"))
    audio = ElevenLabsProvider(client=fake).synthesize("Nice job", "en")
    assert audio == b"MP3BYTES"
    assert "voiceEN" in fake.call["url"]
    assert fake.call["headers"]["xi-api-key"] == "secret"
    assert fake.call["json"]["text"] == "Nice job"


def test_synthesize_missing_voice_raises(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.delenv("ELEVENLABS_VOICE_JA", raising=False)
    with pytest.raises(TTSError):
        ElevenLabsProvider(client=FakeClient(FakeResp())).synthesize("hi", "ja")


def test_synthesize_api_error_raises(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_VOICE_EN", "voiceEN")
    fake = FakeClient(FakeResp(401, b"", "unauthorized"))
    with pytest.raises(TTSError):
        ElevenLabsProvider(client=fake).synthesize("hi", "en")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_tts.py -v`
Expected: FAIL — `No module named 'engine.tts'`.

- [ ] **Step 3: Implement the TTS module**

`engine/tts/__init__.py` — empty file.

`engine/tts/config.py`:

```python
import os

MODEL_ID = "eleven_multilingual_v2"


def api_key() -> str | None:
    return os.environ.get("ELEVENLABS_API_KEY")


def is_available() -> bool:
    return bool(api_key())


def voice_for(language: str) -> str | None:
    return os.environ.get(f"ELEVENLABS_VOICE_{language.upper()}")
```

`engine/tts/base.py`:

```python
class TTSError(Exception):
    pass


class TTSProvider:
    def synthesize(self, text: str, language: str = "en") -> bytes:
        raise NotImplementedError
```

`engine/tts/elevenlabs.py`:

```python
import httpx

from engine.tts import config
from engine.tts.base import TTSProvider, TTSError

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class ElevenLabsProvider(TTSProvider):
    def __init__(self, client=None):
        self._client = client or httpx

    def synthesize(self, text: str, language: str = "en") -> bytes:
        key = config.api_key()
        if not key:
            raise TTSError("ELEVENLABS_API_KEY not set")
        voice_id = config.voice_for(language)
        if not voice_id:
            raise TTSError(
                f"No voice configured for language '{language}' "
                f"(set ELEVENLABS_VOICE_{language.upper()})"
            )
        resp = self._client.post(
            API_URL.format(voice_id=voice_id),
            headers={
                "xi-api-key": key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": config.MODEL_ID,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise TTSError(f"ElevenLabs error {resp.status_code}: {resp.text}")
        return resp.content
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_tts.py -v`
Expected: PASS.

- [ ] **Step 5: Add endpoints to `web/app.py`**

Add these imports near the top:

```python
from fastapi import Response
from engine.tts import config as tts_config
from engine.tts.base import TTSError
from engine.tts.elevenlabs import ElevenLabsProvider
```

Add the `language` parameter to the existing `/api/analyze` handler signature and forward
it (replace the handler's signature line and the `analyze_answer(...)` call):

```python
async def analyze(
    question: str = Form(...),
    audio: UploadFile = File(...),
    language: str = Form("en"),
    run_content: bool = Form(True),
):
```
```python
        report = analyze_answer(tmp_path, question, language=language,
                                run_content=run_content)
```

Add these two routes **above** the `app.mount(...)` line (so they're not shadowed by the
static mount):

```python
@app.get("/api/config")
def get_config():
    return {"tts_enabled": tts_config.is_available()}


@app.post("/api/speak")
async def speak(text: str = Form(...), language: str = Form("en")):
    if not tts_config.is_available():
        raise HTTPException(status_code=503, detail="TTS not configured")
    try:
        audio = ElevenLabsProvider().synthesize(text, language)
    except TTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return Response(content=audio, media_type="audio/mpeg")
```

- [ ] **Step 6: Add endpoint tests** to `tests/test_web.py`

```python
def test_config_endpoint_reports_disabled(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    client = TestClient(appmod.app)
    assert client.get("/api/config").json() == {"tts_enabled": False}


def test_speak_without_key_returns_503(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    client = TestClient(appmod.app)
    resp = client.post("/api/speak", data={"text": "hi", "language": "en"})
    assert resp.status_code == 503


def test_speak_with_key_returns_audio(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    import engine.tts.elevenlabs as el
    monkeypatch.setattr(el.ElevenLabsProvider, "synthesize",
                        lambda self, text, language="en": b"AUDIOBYTES")
    client = TestClient(appmod.app)
    resp = client.post("/api/speak", data={"text": "great", "language": "en"})
    assert resp.status_code == 200
    assert resp.content == b"AUDIOBYTES"
    assert resp.headers["content-type"] == "audio/mpeg"
```

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add engine/tts tests/test_tts.py web/app.py tests/test_web.py
git commit -m "feat: ElevenLabs TTS provider + speak/config endpoints (opt-in)"
```

---

## Task 15: Frontend — "Hear feedback" button

**Files:**
- Modify: `web/static/recorder.js` (load `/api/config`, track language, send `language`)
- Modify: `web/static/results.js` (render coach summary + optional voice button)

- [ ] **Step 1: Update `web/static/recorder.js`**

Add two globals near the top (after the existing `let questions = [];`):

```javascript
let trackLanguage = "en";
window.ttsEnabled = false;
window.trackLanguage = "en";
```

In `loadQuestions()`, after `questions = data.questions;`, capture the language:

```javascript
  trackLanguage = data.language || "en";
  window.trackLanguage = trackLanguage;
  try {
    const cfg = await (await fetch("/api/config")).json();
    window.ttsEnabled = !!cfg.tts_enabled;
  } catch (e) {
    window.ttsEnabled = false;
  }
```

In the `analyzeBtn` click handler, add the language field to the form (next to the
existing `form.append("question", ...)` and `form.append("audio", ...)` lines):

```javascript
  form.append("language", trackLanguage);
```

- [ ] **Step 2: Update `web/static/results.js`** — append the coach section

At the end of `renderResults`, **after** the `content` card is built but **before**
`document.getElementById("results").innerHTML = html;`, add:

```javascript
  if (report.spoken_summary) {
    const voiceUi = window.ttsEnabled
      ? '<button id="hearBtn">🔊 Hear feedback</button> ' +
        '<span id="hearStatus"></span>' +
        '<audio id="coachAudio" class="hidden"></audio>'
      : "";
    html += `<div class="card"><h2>Coach</h2>
      <p id="coachText">${report.spoken_summary}</p>
      ${voiceUi}</div>`;
  }
```

Then, **after** the `innerHTML` assignment, wire the button:

```javascript
  if (report.spoken_summary && window.ttsEnabled) {
    const hearBtn = document.getElementById("hearBtn");
    const status = document.getElementById("hearStatus");
    hearBtn.addEventListener("click", async () => {
      hearBtn.disabled = true;
      status.textContent = "Generating voice…";
      try {
        const form = new FormData();
        form.append("text", report.spoken_summary);
        form.append("language", window.trackLanguage || "en");
        const resp = await fetch("/api/speak", { method: "POST", body: form });
        if (!resp.ok) throw new Error("speak failed");
        const blob = await resp.blob();
        const audio = document.getElementById("coachAudio");
        audio.src = URL.createObjectURL(blob);
        audio.classList.remove("hidden");
        audio.play();
        status.textContent = "";
      } catch (e) {
        status.textContent = "Voice unavailable.";
      } finally {
        hearBtn.disabled = false;
      }
    });
  }
```

- [ ] **Step 3: Manual smoke test — without a key (default)**

Ensure `ELEVENLABS_API_KEY` is unset, run `.venv/bin/uvicorn web.app:app --port 8000`,
record and analyze an answer. Verify:
1. A **Coach** card appears with the warm summary text.
2. **No** "Hear feedback" button is shown (TTS disabled).

- [ ] **Step 4: Manual smoke test — with a key**

Set the env vars, then restart the server in the same shell:
```bash
export ELEVENLABS_API_KEY="<your-key>"
export ELEVENLABS_VOICE_EN="<your-english-voice-id>"
.venv/bin/uvicorn web.app:app --port 8000
```
Record and analyze, then verify:
1. The **Coach** card shows the summary text.
2. A "🔊 Hear feedback" button appears.
3. Clicking it shows "Generating voice…", then plays the summary in your chosen voice.

Record the result of each check. If any fails, debug before committing.

- [ ] **Step 5: Commit**

```bash
git add web/static/recorder.js web/static/results.js
git commit -m "feat: frontend coach summary + Hear feedback voice button"
```

---

## Definition of done

- [ ] `.venv/bin/pytest -q` is fully green.
- [ ] `uvicorn web.app:app` serves the page; the Task 11 manual smoke test passes end-to-end with Ollama running.
- [ ] The filler spike has been run and its findings recorded, so we know the real-world accuracy of the highest-risk module before building on it.
- [ ] The spoken-feedback layer works both ways: **without** a key the Coach text shows and the app is local-only; **with** a key + `ELEVENLABS_VOICE_EN`, the "Hear feedback" button voices the summary (Task 15 smoke tests).
- [ ] Only the short summary text is ever sent to ElevenLabs — the recording and transcript never leave the machine.
- [ ] The engine package (`engine/`) has zero imports from `web/` — the boundary that lets it later sit behind a different backend (or the JP track) is intact.
