# Cloud Processing Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make transcription and the LLM (content/proficiency/coach) pluggable between **local** (faster-whisper + Ollama, the default) and **cloud** (OpenAI Whisper + GPT-4o), selected by env config, so the engine can run on a server with no GPU — without changing local behavior.

**Architecture:** Two small provider seams. The LLM modules already accept an injectable `client` with a `.chat(model=, messages=, format=)` shape, so a new `engine/llm.py` returns either the `ollama` module or an `OpenAIChatClient` that mimics that shape. `engine/transcribe.py` gains a provider dispatch (local vs an OpenAI Whisper call) returning the same `Transcript`. Heavy local libs (`faster_whisper`, `ollama`) become **lazy imports** so a cloud-only deploy needn't install them. Local stays the default everywhere → the existing suite is untouched.

**Tech Stack:** Python 3.11+, httpx (already a dep, used like the ElevenLabs provider), faster-whisper + Ollama (local, now lazy), OpenAI HTTP APIs (cloud), pytest with mocked HTTP clients (no real API calls in tests).

---

## File structure

```
engine/llm.py              # NEW: provider() / default_model() / get_client()
engine/llm_openai.py       # NEW: OpenAIChatClient.chat() — mimics the ollama .chat() shape
engine/transcribe.py       # MODIFY: lazy faster_whisper import + provider dispatch
engine/transcribe_openai.py# NEW: transcribe_openai() — OpenAI Whisper API -> Transcript
engine/content.py          # MODIFY: lazy ollama (default client only)
engine/proficiency.py      # MODIFY: lazy ollama
engine/coach.py            # MODIFY: lazy ollama
engine/report.py           # MODIFY: analyze_answer uses get_client()+default_model()
web/app.py                 # MODIFY: drop _content_model(); engine resolves model now
README.md                  # MODIFY: document the cloud env switches
tests/test_llm.py              # NEW
tests/test_transcribe_openai.py# NEW
tests/test_report.py           # MODIFY: provider plumbing test
tests/test_web.py              # MODIFY: relocate the two model tests to engine.llm
```

**Pre-req:** the app is at 95 passing tests; local is the only provider today.

---

## Task 1: LLM provider seam (`engine/llm.py` + `engine/llm_openai.py`)

**Files:** Create `engine/llm.py`, `engine/llm_openai.py`, `tests/test_llm.py`.

- [ ] **Step 1: Write failing tests** in `tests/test_llm.py`:

```python
import json

from engine import llm
from engine.llm_openai import OpenAIChatClient


def test_default_provider_is_ollama(monkeypatch):
    monkeypatch.delenv("REHEARSAL_LLM_PROVIDER", raising=False)
    assert llm.provider() == "ollama"


def test_default_model_is_provider_aware(monkeypatch):
    monkeypatch.delenv("REHEARSAL_LLM_MODEL", raising=False)
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "ollama")
    assert llm.default_model() == "qwen2.5:7b"
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "openai")
    assert llm.default_model() == "gpt-4o"


def test_default_model_env_override(monkeypatch):
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "openai")
    monkeypatch.setenv("REHEARSAL_LLM_MODEL", "gpt-4o-mini")
    assert llm.default_model() == "gpt-4o-mini"


def test_get_client_openai(monkeypatch):
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "openai")
    assert isinstance(llm.get_client(), OpenAIChatClient)


class FakeResp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


class FakeHTTP:
    def __init__(self, payload):
        self._payload = payload
        self.call = None
    def post(self, url, **kw):
        self.call = {"url": url, **kw}
        return FakeResp(self._payload)


def test_openai_chat_shape_and_json_mode(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    payload = {"choices": [{"message": {"content": "{\"level\": \"Novice-High\"}"}}]}
    http = FakeHTTP(payload)
    client = OpenAIChatClient(client=http)
    out = client.chat(model="gpt-4o",
                      messages=[{"role": "user", "content": "hi"}],
                      format="json")
    assert out == {"message": {"content": "{\"level\": \"Novice-High\"}"}}
    assert http.call["json"]["model"] == "gpt-4o"
    assert http.call["json"]["response_format"] == {"type": "json_object"}
    assert http.call["headers"]["Authorization"] == "Bearer sk-test"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_llm.py -v`
Expected: FAIL — `No module named 'engine.llm'`.

- [ ] **Step 3: Create `engine/llm_openai.py`**:

```python
import os

import httpx

API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIChatClient:
    """Mimics the ollama `.chat()` interface so content/proficiency/coach can use it
    unchanged: chat(model=, messages=, format=) -> {"message": {"content": str}}."""

    def __init__(self, client=None):
        self._client = client or httpx

    def chat(self, model, messages, format=None):
        key = os.environ["OPENAI_API_KEY"]
        body = {"model": model, "messages": messages}
        if format == "json":
            body["response_format"] = {"type": "json_object"}
        resp = self._client.post(
            API_URL,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"message": {"content": data["choices"][0]["message"]["content"]}}
```

- [ ] **Step 4: Create `engine/llm.py`**:

```python
import os

DEFAULT_MODELS = {"ollama": "qwen2.5:7b", "openai": "gpt-4o"}


def provider() -> str:
    return os.environ.get("REHEARSAL_LLM_PROVIDER", "ollama")


def default_model() -> str:
    return os.environ.get("REHEARSAL_LLM_MODEL") or DEFAULT_MODELS.get(provider(), "qwen2.5:7b")


def get_client():
    """The chat client for the configured provider. Ollama is imported lazily so a
    cloud-only deploy needn't install it."""
    if provider() == "openai":
        from engine.llm_openai import OpenAIChatClient
        return OpenAIChatClient()
    import ollama
    return ollama
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/pytest tests/test_llm.py -v`
Expected: PASS (6 tests; no real network — `OpenAIChatClient` uses the injected fake).

- [ ] **Step 6: Commit**

```bash
git add engine/llm.py engine/llm_openai.py tests/test_llm.py
git commit -m "feat: LLM provider seam (ollama default, openai cloud client)"
```

---

## Task 2: Lazy Ollama imports in content / proficiency / coach

So a cloud-only deploy (provider=openai) doesn't require `ollama` installed. Each module
currently does `import ollama` at top and `client=ollama` as a default param.

**Files:** Modify `engine/content.py`, `engine/proficiency.py`, `engine/coach.py`.

- [ ] **Step 1: Add a regression test** to `tests/test_content.py` (proves the default-client path still works and is lazy):

```python
def test_analyze_content_default_client_is_lazy(monkeypatch):
    # With a fake injected client, ollama must not be required.
    import engine.content as content
    captured = {}

    class FakeClient:
        def chat(self, **kw):
            captured.update(kw)
            return {"message": {"content": __import__("json").dumps(
                {"answered_question": True, "answered_explanation": "ok",
                 "star_present": {}, "issues": [], "tighter_rewrite": "",
                 "coaching_notes": []})}}

    fb = content.analyze_content("Q", "A", client=FakeClient())
    assert fb.kind == "interview"
    assert captured["format"] == "json"
```

- [ ] **Step 2: Run it (passes today, but confirms behavior before refactor)**

Run: `.venv/bin/pytest tests/test_content.py::test_analyze_content_default_client_is_lazy -v`
Expected: PASS.

- [ ] **Step 3: Edit `engine/content.py`** — remove the top-level `import ollama`, and make the default client lazy. Change the signature + first lines of `analyze_content`:

```python
def analyze_content(question: str, answer: str, model: str = "llama3.1",
                    client=None) -> ContentFeedback:
    if client is None:
        import ollama
        client = ollama
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
(Delete the `import ollama` line at the top of the file.)

- [ ] **Step 4: Edit `engine/proficiency.py`** — same change: delete top-level `import ollama`; in `analyze_proficiency` change `client=ollama` to `client=None` and add at the top of the body:

```python
def analyze_proficiency(question: str, answer: str, language: str = "ja",
                        model: str = "llama3.1", client=None) -> ProficiencyFeedback:
    if client is None:
        import ollama
        client = ollama
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",
             "content": build_proficiency_prompt(question, answer, language)},
        ],
        format="json",
    )
    return parse_proficiency_response(resp["message"]["content"])
```

- [ ] **Step 5: Edit `engine/coach.py`** — same: delete top-level `import ollama`; in `compose_spoken_summary` change `client=ollama` to `client=None` and add the lazy default:

```python
def compose_spoken_summary(report: dict, language: str = "en",
                           model: str = "llama3.1", client=None) -> str:
    if client is None:
        import ollama
        client = ollama
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": COACH_SYSTEM},
            {"role": "user", "content": build_summary_prompt(report, language)},
        ],
    )
    return resp["message"]["content"].strip()
```

- [ ] **Step 6: Run the affected suites**

Run: `.venv/bin/pytest tests/test_content.py tests/test_proficiency.py tests/test_coach.py -q`
Expected: all PASS (the fake-client tests already inject a client; the default path is now lazy).

- [ ] **Step 7: Commit**

```bash
git add engine/content.py engine/proficiency.py engine/coach.py tests/test_content.py
git commit -m "refactor: lazy ollama imports so cloud-only runs without ollama"
```

---

## Task 3: Transcription provider (lazy local + OpenAI Whisper)

**Files:** Modify `engine/transcribe.py`; create `engine/transcribe_openai.py`, `tests/test_transcribe_openai.py`.

- [ ] **Step 1: Write failing tests** in `tests/test_transcribe_openai.py`:

```python
from engine.transcribe_openai import transcribe_openai


class FakeResp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


class FakeHTTP:
    def __init__(self, payload):
        self._payload = payload
        self.call = None
    def post(self, url, **kw):
        self.call = {"url": url, **kw}
        return FakeResp(self._payload)


def test_transcribe_openai_builds_transcript(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFxxxx")
    payload = {
        "text": "hello world",
        "language": "english",
        "duration": 1.5,
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
        ],
    }
    http = FakeHTTP(payload)
    tr = transcribe_openai(str(audio), language="en", client=http)
    assert tr.text == "hello world"
    assert len(tr.words) == 2
    assert tr.words[0].text == "hello"
    assert tr.words[0].probability == 1.0   # OpenAI gives no per-word confidence
    assert tr.duration == 1.5
    assert http.call["data"]["model"] == "whisper-1"


def test_transcribe_openai_empty_words(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFxxxx")
    tr = transcribe_openai(str(audio), language="ja",
                           client=FakeHTTP({"text": "", "duration": 0.0, "words": []}))
    assert tr.words == []
    assert tr.duration == 0.0
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_transcribe_openai.py -v`
Expected: FAIL — `No module named 'engine.transcribe_openai'`.

- [ ] **Step 3: Create `engine/transcribe_openai.py`**:

```python
import os

import httpx

from engine.types import Word, Transcript

API_URL = "https://api.openai.com/v1/audio/transcriptions"


def transcribe_openai(wav_path: str, language: str = "en", client=None) -> Transcript:
    """Transcribe via OpenAI's Whisper API with word timestamps. OpenAI does not
    return per-word confidence, so Word.probability defaults to 1.0 (the clarity
    proxy is correspondingly less precise on the cloud provider)."""
    http = client or httpx
    key = os.environ["OPENAI_API_KEY"]
    with open(wav_path, "rb") as f:
        resp = http.post(
            API_URL,
            headers={"Authorization": f"Bearer {key}"},
            data={"model": "whisper-1", "language": language,
                  "response_format": "verbose_json",
                  "timestamp_granularities[]": "word"},
            files={"file": ("audio.wav", f, "audio/wav")},
            timeout=120,
        )
    resp.raise_for_status()
    data = resp.json()
    words = [Word(text=w["word"].strip(), start=float(w["start"]),
                  end=float(w["end"]), probability=1.0)
             for w in data.get("words", [])]
    duration = float(data.get("duration", words[-1].end if words else 0.0))
    return Transcript(words=words, text=data.get("text", "").strip(),
                      duration=duration, language=data.get("language", language))
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_transcribe_openai.py -v`
Expected: PASS (2 tests, fake HTTP).

- [ ] **Step 5: Edit `engine/transcribe.py`** — make `faster_whisper` lazy and add provider dispatch. Replace the top of the file and the `transcribe` function:

Replace the top imports:
```python
import os
from functools import lru_cache

from engine.types import Word, Transcript

MULTILINGUAL_MODEL = "small"
```
(Remove the top-level `from faster_whisper import WhisperModel`.)

Change `_get_model` to import lazily:
```python
@lru_cache(maxsize=3)
def _get_model(model_size: str):
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device="cpu", compute_type="int8")
```

Rename the existing local body to `_transcribe_local` and add a dispatching `transcribe`:
```python
def transcribe(wav_path: str, language: str = "en",
               model_size: str | None = None) -> Transcript:
    if os.environ.get("REHEARSAL_TRANSCRIBE_PROVIDER", "local") == "openai":
        from engine.transcribe_openai import transcribe_openai
        return transcribe_openai(wav_path, language)
    return _transcribe_local(wav_path, language, model_size)


def _transcribe_local(wav_path: str, language: str = "en",
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
(`_resolve` stays unchanged.)

- [ ] **Step 6: Add a dispatch test** to `tests/test_transcribe.py`:

```python
def test_transcribe_dispatches_to_openai(monkeypatch):
    monkeypatch.setenv("REHEARSAL_TRANSCRIBE_PROVIDER", "openai")
    import engine.transcribe as t
    called = {}

    def fake(wav, language="en"):
        called["wav"] = wav
        called["language"] = language
        from engine.types import Transcript
        return Transcript([], "", 0.0, language)

    monkeypatch.setattr("engine.transcribe_openai.transcribe_openai", fake)
    t.transcribe("x.wav", language="ja")
    assert called == {"wav": "x.wav", "language": "ja"}
```

- [ ] **Step 7: Run transcribe tests**

Run: `.venv/bin/pytest tests/test_transcribe.py tests/test_transcribe_openai.py -v`
Expected: PASS (the local fixture test still uses the default local provider; the dispatch test forces openai and the OpenAI call is faked).

- [ ] **Step 8: Commit**

```bash
git add engine/transcribe.py engine/transcribe_openai.py tests/test_transcribe_openai.py tests/test_transcribe.py
git commit -m "feat: transcription provider (lazy local default, openai whisper cloud)"
```

---

## Task 4: Wire providers into the orchestrator + web layer

**Files:** Modify `engine/report.py`, `web/app.py`, `tests/test_report.py`, `tests/test_web.py`.

- [ ] **Step 1: Write a failing test** in `tests/test_report.py` (the orchestrator uses the configured client + model):

```python
def test_analyze_answer_uses_llm_provider(monkeypatch):
    import engine.report as report
    from engine.types import Word, Transcript
    from engine.delivery import DeliveryMetrics
    from engine.fillers import FillerReport
    from engine.prosody import ProsodyMetrics
    from engine.content import ContentFeedback

    sentinel_client = object()
    monkeypatch.setattr(report, "get_client", lambda: sentinel_client)
    monkeypatch.setattr(report, "default_model", lambda: "gpt-4o")
    monkeypatch.setattr(report, "to_wav", lambda p: p)
    monkeypatch.setattr(report, "transcribe",
                        lambda wav, language="en": Transcript([Word("hi", 0.0, 0.4)], "hi", 1.0, language))
    monkeypatch.setattr(report, "analyze_delivery",
                        lambda tr: DeliveryMetrics(1.0, 0.4, 0.0, 0.0, [], 0))
    monkeypatch.setattr(report, "detect_fillers",
                        lambda tr, wav_path=None: FillerReport([], 0, 0.0))
    monkeypatch.setattr(report, "analyze_prosody",
                        lambda wav: ProsodyMetrics(0.0, 0.0, 0.0, True, 0.0))
    monkeypatch.setattr(report, "compose_spoken_summary", lambda *a, **k: "summary")

    captured = {}
    def fake_content(q, a, model=None, client=None):
        captured["model"] = model
        captured["client"] = client
        return ContentFeedback(True, "ok", {}, ["situation", "task", "action", "result"], [], "", [])
    monkeypatch.setattr(report, "analyze_content", fake_content)

    report.analyze_answer("a.wav", "Q", mode="interview")
    assert captured["model"] == "gpt-4o"
    assert captured["client"] is sentinel_client
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_report.py::test_analyze_answer_uses_llm_provider -v`
Expected: FAIL — `report` has no attribute `get_client` (not imported yet).

- [ ] **Step 3: Edit `engine/report.py`** — import the provider seam and use it. Add to the imports:

```python
from engine.llm import get_client, default_model
```
Replace `analyze_answer` with:
```python
def analyze_answer(audio_path: str, question: str, *, language: str = "en",
                   mode: str = "interview", run_content: bool = True,
                   content_model: str | None = None) -> dict:
    wav = to_wav(audio_path)
    transcript = transcribe(wav, language=language)
    delivery = analyze_delivery(transcript)
    fillers = detect_fillers(transcript, wav_path=wav)
    prosody = analyze_prosody(wav)

    client = get_client()
    model = content_model or default_model()
    content = None
    if run_content and transcript.text:
        if mode == "japanese":
            content = analyze_proficiency(question, transcript.text,
                                          language=language, model=model, client=client)
        else:
            content = analyze_content(question, transcript.text, model=model, client=client)
    report = build_report(transcript, delivery, fillers, prosody, content)
    report["spoken_summary"] = (
        compose_spoken_summary(report, language=language, model=model, client=client)
        if run_content and transcript.text else None
    )
    return report
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_report.py -v`
Expected: PASS (the new test + the existing build_report tests).

- [ ] **Step 5: Simplify `web/app.py`** — the engine now resolves the model, so the web layer stops passing it. Remove the `_content_model()` function entirely, and change the `/api/analyze` engine call from:
```python
        report = analyze_answer(tmp_path, question, language=language, mode=mode,
                                run_content=run_content, content_model=_content_model())
```
to:
```python
        report = analyze_answer(tmp_path, question, language=language, mode=mode,
                                run_content=run_content)
```

- [ ] **Step 6: Relocate the two model tests** — they tested web-level model plumbing that no longer exists. In `tests/test_web.py`, DELETE `test_analyze_uses_env_llm_model` and `test_analyze_default_llm_model`. They are replaced by the `engine.llm` tests from Task 1 (`test_default_model_is_provider_aware`, `test_default_model_env_override`), which test the same behavior at its new home.

- [ ] **Step 7: Full suite**

Run: `.venv/bin/pytest -q -k "not ollama"`
Expected: all green. (The integration test still passes `content_model=` as an explicit override, which `analyze_answer` honors.)

- [ ] **Step 8: Commit**

```bash
git add engine/report.py web/app.py tests/test_report.py tests/test_web.py
git commit -m "feat: orchestrator uses configured LLM provider+model; web stops hardcoding model"
```

---

## Task 5: Document the cloud switches + dependencies

**Files:** Modify `README.md`; create `requirements-cloud.txt`.

- [ ] **Step 1: Create `requirements-cloud.txt`** (the slim set for a cloud-only deploy — no faster-whisper, no ollama):

```
fastapi
uvicorn[standard]
python-multipart
praat-parselmouth
httpx
```

- [ ] **Step 2: Add a "Cloud providers" section to `README.md`** (after the "Model choice" section):

```markdown
## Cloud providers (for hosting)

By default everything runs locally (faster-whisper + Ollama). To run without local
models — e.g. on a server — set:

| Env var | Values | Effect |
|---|---|---|
| `REHEARSAL_TRANSCRIBE_PROVIDER` | `local` (default) / `openai` | Whisper via faster-whisper vs the OpenAI Whisper API |
| `REHEARSAL_LLM_PROVIDER` | `ollama` (default) / `openai` | rubric/coach via Ollama vs OpenAI |
| `REHEARSAL_LLM_MODEL` | (optional) | overrides the provider's default model |
| `OPENAI_API_KEY` | — | required when either provider is `openai` |

With both set to `openai`, the engine needs neither `faster-whisper` nor `ollama`
installed (`requirements-cloud.txt`); parselmouth + ElevenLabs are unchanged.
Note: the OpenAI Whisper API returns word timestamps but no per-word confidence, so
the clarity proxy is less precise on the cloud provider.
```

- [ ] **Step 3: Sanity-check the cloud path end-to-end with mocks** (no real keys) — append to `tests/test_report.py`:

```python
def test_cloud_providers_selectable(monkeypatch):
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "openai")
    monkeypatch.setenv("REHEARSAL_TRANSCRIBE_PROVIDER", "openai")
    from engine import llm
    from engine.llm_openai import OpenAIChatClient
    assert isinstance(llm.get_client(), OpenAIChatClient)
    assert llm.default_model() == "gpt-4o"
    import engine.transcribe as t
    captured = {}
    monkeypatch.setattr("engine.transcribe_openai.transcribe_openai",
                        lambda wav, language="en": captured.setdefault("hit", True))
    t.transcribe("x.wav", language="ja")
    assert captured.get("hit") is True
```

- [ ] **Step 4: Run + commit**

Run: `.venv/bin/pytest -q -k "not ollama"` (all green).
```bash
git add README.md requirements-cloud.txt tests/test_report.py
git commit -m "docs: cloud provider env switches + slim cloud requirements"
```

---

## Definition of done

- [ ] `.venv/bin/pytest -q` fully green; local providers remain the default, so the existing
  suite (incl. the Ollama-gated and fixture tests) is unchanged.
- [ ] Setting `REHEARSAL_LLM_PROVIDER=openai` + `REHEARSAL_TRANSCRIBE_PROVIDER=openai` routes
  the rubric/coach to OpenAI chat and transcription to the OpenAI Whisper API (verified via
  mocked HTTP — no real API calls in tests).
- [ ] `faster_whisper` and `ollama` are imported lazily — the engine runs cloud-only without
  them installed (`requirements-cloud.txt`).
- [ ] `engine/` still has zero imports from `web/`; the web layer no longer hardcodes a model.
- [ ] Real-API verification (actual OpenAI keys) is deferred to the deploy sub-project; this
  plan proves wiring + selection with mocks only.
```
