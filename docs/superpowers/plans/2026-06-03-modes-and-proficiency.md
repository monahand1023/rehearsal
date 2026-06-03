# Modes + Japanese Proficiency Rubric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `rehearsal` into one app with two modes (Interview Coach / Japanese Practice), routing content analysis by mode, and add a local Japanese proficiency rubric so Japanese answers get an ACTFL-style practice estimate instead of mis-applied interview STAR.

**Architecture:** A `"mode"` field on each track JSON, exposed via `/api/tracks` and surfaced as a frontend mode selector. A `kind` discriminator on both analyzers' result dataclasses lets `analyze_answer(..., mode=...)` route to the interview (`content.py`) or proficiency (`proficiency.py`) analyzer and drop the result into the report's existing `content` slot — so `build_report` is untouched and the interview path is byte-identical. The coach and frontend branch on `content.kind`.

**Tech Stack:** Python 3.11+, Ollama (`llama3.1`, already a dep), FastAPI, vanilla JS. No new dependencies.

---

## File structure

```
questions/interview_en.json   # MODIFY: add "mode": "interview"
questions/language_jp.json     # MODIFY: add "mode": "japanese"
web/app.py                     # MODIFY: /api/tracks returns mode; /api/analyze forwards mode
engine/content.py              # MODIFY: ContentFeedback.kind = "interview"
engine/proficiency.py          # NEW
engine/report.py               # MODIFY: analyze_answer routes by mode
engine/coach.py                # MODIFY: summarize by content.kind
web/static/index.html          # MODIFY: mode <select>
web/static/recorder.js         # MODIFY: mode grouping + send mode
web/static/results.js          # MODIFY: proficiency card by content.kind
tests/test_proficiency.py      # NEW
tests/test_content.py          # MODIFY: kind assertion
tests/test_coach.py            # MODIFY: proficiency-branch test
tests/test_web.py              # MODIFY: /api/tracks mode + /api/analyze mode forwarding
```

**Pre-req:** the Japanese free-response track is built; 66 tests pass.

---

## Task 1: `mode` field on tracks + `/api/tracks` exposes it

**Files:** Modify `questions/interview_en.json`, `questions/language_jp.json`, `web/app.py`, `tests/test_web.py`.

- [ ] **Step 1: Add `"mode"` to both track files.**

In `questions/interview_en.json`, add a `"mode": "interview"` field next to `"track"` and `"language"` (top level). The top of the file becomes:
```json
{
  "track": "interview_en",
  "language": "en",
  "mode": "interview",
  "questions": [
```
In `questions/language_jp.json`, likewise add `"mode": "japanese"`:
```json
{
  "track": "language_jp",
  "language": "ja",
  "mode": "japanese",
  "questions": [
```
(Leave the `questions` arrays exactly as they are.)

- [ ] **Step 2: Validate both JSON files**

Run: `.venv/bin/python -c "import json; print(json.load(open('questions/interview_en.json'))['mode'], json.load(open('questions/language_jp.json'))['mode'])"`
Expected: `interview japanese`.

- [ ] **Step 3: Write a failing test** — append to `tests/test_web.py`:
```python
def test_tracks_endpoint_includes_mode():
    client = TestClient(appmod.app)
    body = client.get("/api/tracks").json()
    by_track = {t["track"]: t for t in body["tracks"]}
    assert by_track["interview_en"]["mode"] == "interview"
    assert by_track["language_jp"]["mode"] == "japanese"
```

- [ ] **Step 4: Run to verify failure**

Run: `.venv/bin/pytest tests/test_web.py::test_tracks_endpoint_includes_mode -v`
Expected: FAIL — `KeyError: 'mode'` (the endpoint doesn't return it yet).

- [ ] **Step 5: Update the `/api/tracks` route in `web/app.py`** to include `mode`:
```python
@app.get("/api/tracks")
def get_tracks():
    tracks = []
    for path in sorted(QUESTIONS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        tracks.append({"track": data["track"], "language": data["language"],
                       "mode": data.get("mode", "interview"),
                       "count": len(data.get("questions", []))})
    return {"tracks": tracks}
```

- [ ] **Step 6: Run + commit**

Run: `.venv/bin/pytest tests/test_web.py -v` then `.venv/bin/pytest -q` (all green).
```bash
git add questions/interview_en.json questions/language_jp.json web/app.py tests/test_web.py
git commit -m "feat: mode field on tracks + /api/tracks exposes mode"
```

---

## Task 2: Japanese proficiency module

**Files:** Create `engine/proficiency.py`, `tests/test_proficiency.py`.

- [ ] **Step 1: Write failing tests** in `tests/test_proficiency.py`:
```python
import json

from engine.proficiency import (build_proficiency_prompt,
                                 parse_proficiency_response, analyze_proficiency)


def test_prompt_includes_question_answer_and_language():
    p = build_proficiency_prompt("好きな食べ物は？", "寿司が好きです", language="ja")
    assert "好きな食べ物は？" in p
    assert "寿司が好きです" in p
    assert "Japanese" in p


def test_parse_sets_kind_and_caps_lists():
    raw = json.dumps({
        "level": "Intermediate-Mid",
        "task_completion": "addressed the prompt",
        "grammar": "mostly accurate",
        "vocabulary": "adequate range",
        "coherence": "well organized",
        "strengths": ["clear", "fluent", "natural", "extra"],
        "suggestions": ["use connectors", "vary vocab", "slow down", "extra"],
    })
    fb = parse_proficiency_response(raw)
    assert fb.kind == "proficiency"
    assert fb.level == "Intermediate-Mid"
    assert len(fb.strengths) == 3
    assert len(fb.suggestions) == 3


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.kw = None

    def chat(self, **kw):
        self.kw = kw
        return {"message": {"content": self.payload}}


def test_analyze_uses_client_and_json_format():
    payload = json.dumps({"level": "Novice-High", "task_completion": "partial",
                          "grammar": "", "vocabulary": "", "coherence": "",
                          "strengths": [], "suggestions": []})
    client = FakeClient(payload)
    fb = analyze_proficiency("質問", "答え", language="ja", client=client)
    assert fb.kind == "proficiency"
    assert fb.level == "Novice-High"
    assert client.kw["format"] == "json"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_proficiency.py -v`
Expected: FAIL — `No module named 'engine.proficiency'`.

- [ ] **Step 3: Create `engine/proficiency.py`**:
```python
import json
from dataclasses import dataclass

import ollama

LANGUAGE_NAMES = {"ja": "Japanese", "en": "English"}

SYSTEM = (
    "You are a supportive language-proficiency assessor. You evaluate a transcribed "
    "spoken answer to a prompt and return structured JSON. You estimate an ACTFL-style "
    "proficiency level and give specific, kind, actionable feedback. You are NOT an "
    "official scorer — this is a practice estimate. Never invent content the speaker "
    "did not say."
)


@dataclass
class ProficiencyFeedback:
    kind: str
    level: str
    task_completion: str
    grammar: str
    vocabulary: str
    coherence: str
    strengths: list
    suggestions: list


def build_proficiency_prompt(question: str, answer: str, language: str = "ja") -> str:
    lang_name = LANGUAGE_NAMES.get(language, "the target language")
    return (
        f"Prompt ({lang_name}):\n{question}\n\n"
        f"Speaker's transcribed answer:\n{answer}\n\n"
        "Return ONLY JSON with these keys:\n"
        "- level (string): estimated ACTFL-style level, e.g. 'Novice-High', "
        "'Intermediate-Mid', 'Advanced-Low'\n"
        "- task_completion (string): did they address the prompt; one sentence\n"
        "- grammar (string): grammatical range and accuracy; one sentence\n"
        "- vocabulary (string): lexical range; one sentence\n"
        "- coherence (string): organization and flow; one sentence\n"
        "- strengths (array of 2-3 short strings)\n"
        "- suggestions (array of 2-3 short, actionable strings)"
    )


def parse_proficiency_response(raw: str) -> ProficiencyFeedback:
    data = json.loads(raw)
    return ProficiencyFeedback(
        kind="proficiency",
        level=data.get("level", ""),
        task_completion=data.get("task_completion", ""),
        grammar=data.get("grammar", ""),
        vocabulary=data.get("vocabulary", ""),
        coherence=data.get("coherence", ""),
        strengths=list(data.get("strengths", []))[:3],
        suggestions=list(data.get("suggestions", []))[:3],
    )


def analyze_proficiency(question: str, answer: str, language: str = "ja",
                        model: str = "llama3.1", client=ollama) -> ProficiencyFeedback:
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

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_proficiency.py -v`
Expected: PASS (no Ollama needed — client is faked).

- [ ] **Step 5: Commit**

```bash
git add engine/proficiency.py tests/test_proficiency.py
git commit -m "feat: Japanese proficiency rubric module (local Ollama)"
```

---

## Task 3: `kind` discriminator on `ContentFeedback`

**Files:** Modify `engine/content.py`, `tests/test_content.py`.

- [ ] **Step 1: Append a failing test** to `tests/test_content.py`:
```python
def test_parse_response_sets_interview_kind():
    raw = json.dumps({"answered_question": True, "answered_explanation": "ok",
                      "star_present": {}, "issues": [], "tighter_rewrite": "",
                      "coaching_notes": []})
    fb = parse_response(raw)
    assert fb.kind == "interview"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_content.py::test_parse_response_sets_interview_kind -v`
Expected: FAIL — `ContentFeedback` has no attribute `kind`.

- [ ] **Step 3: Edit `engine/content.py`.** Add a `kind` field to the dataclass (at the END so positional construction stays valid):
```python
@dataclass
class ContentFeedback:
    answered_question: bool
    answered_explanation: str
    star_present: dict
    star_missing: list
    issues: list
    tighter_rewrite: str
    coaching_notes: list
    kind: str = "interview"
```
In `parse_response`, set it explicitly on the returned object — add `kind="interview"` as the last argument of the `ContentFeedback(...)` constructor call:
```python
    return ContentFeedback(
        answered_question=bool(data.get("answered_question", False)),
        answered_explanation=data.get("answered_explanation", ""),
        star_present=star_present,
        star_missing=star_missing,
        issues=list(data.get("issues", [])),
        tighter_rewrite=data.get("tighter_rewrite", ""),
        coaching_notes=list(data.get("coaching_notes", []))[:3],
        kind="interview",
    )
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `.venv/bin/pytest tests/test_content.py -v` then `.venv/bin/pytest -q`
Expected: all green. Existing `test_report.py` (constructs `ContentFeedback(...)` by keyword) still works — `kind` defaults to `"interview"`.

- [ ] **Step 5: Commit**

```bash
git add engine/content.py tests/test_content.py
git commit -m "feat: kind=interview discriminator on ContentFeedback"
```

---

## Task 4: Route content by mode in the orchestrator + `/api/analyze`

**Files:** Modify `engine/report.py`, `web/app.py`, `tests/test_web.py`.

- [ ] **Step 1: Edit `engine/report.py`.** Add the proficiency import next to the content import:
```python
from engine.proficiency import analyze_proficiency
```
Replace the `analyze_answer` function with this version (adds a `mode` param and routes the analyzer; everything else unchanged):
```python
def analyze_answer(audio_path: str, question: str, *, language: str = "en",
                   mode: str = "interview", run_content: bool = True,
                   content_model: str = "llama3.1") -> dict:
    wav = to_wav(audio_path)
    transcript = transcribe(wav, language=language)
    delivery = analyze_delivery(transcript)
    fillers = detect_fillers(transcript, wav_path=wav)
    prosody = analyze_prosody(wav)
    content = None
    if run_content and transcript.text:
        if mode == "japanese":
            content = analyze_proficiency(question, transcript.text,
                                          language=language, model=content_model)
        else:
            content = analyze_content(question, transcript.text, model=content_model)
    report = build_report(transcript, delivery, fillers, prosody, content)
    report["spoken_summary"] = (
        compose_spoken_summary(report, language=language, model=content_model)
        if run_content and transcript.text else None
    )
    return report
```

- [ ] **Step 2: Forward `mode` from `/api/analyze` in `web/app.py`.** Add the `mode` form field to the handler signature and pass it through:
```python
async def analyze(
    question: str = Form(...),
    audio: UploadFile = File(...),
    language: str = Form("en"),
    mode: str = Form("interview"),
    run_content: bool = Form(True),
):
```
```python
        report = analyze_answer(tmp_path, question, language=language, mode=mode,
                                run_content=run_content)
```

- [ ] **Step 3: Add a mode-forwarding test** to `tests/test_web.py`:
```python
def test_analyze_forwards_mode(monkeypatch):
    captured = {}

    def fake_analyze(audio_path, question, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(appmod, "analyze_answer", fake_analyze)
    client = TestClient(appmod.app)
    resp = client.post(
        "/api/analyze",
        data={"question": "Q", "mode": "japanese", "language": "ja"},
        files={"audio": ("a.webm", b"x", "audio/webm")},
    )
    assert resp.status_code == 200
    assert captured["mode"] == "japanese"
    assert captured["language"] == "ja"
```

- [ ] **Step 4: Run + full suite**

Run: `.venv/bin/pytest tests/test_web.py -v` then `.venv/bin/pytest -q`
Expected: all green. The existing `test_analyze_endpoint_calls_engine` still passes — its `fake_analyze(audio_path, question, **kwargs)` absorbs the new `mode` kwarg, and `mode` defaults to `"interview"`.

- [ ] **Step 5: Commit**

```bash
git add engine/report.py web/app.py tests/test_web.py
git commit -m "feat: route content analysis by mode (interview vs proficiency)"
```

---

## Task 5: Coach summarizes by `content.kind`

**Files:** Modify `engine/coach.py`, `tests/test_coach.py`.

- [ ] **Step 1: Append a failing test** to `tests/test_coach.py`:
```python
def test_prompt_uses_proficiency_branch():
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 120.0, "long_pause_count": 1,
                     "time_to_first_word": 0.3},
        "fillers": {"count": 2, "per_minute": 3.0},
        "prosody": {"monotone": False},
        "content": {"kind": "proficiency", "level": "Intermediate-Mid",
                    "task_completion": "addressed the prompt well"},
    }
    p = build_summary_prompt(report, language="ja")
    assert "Intermediate-Mid" in p
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_coach.py::test_prompt_uses_proficiency_branch -v`
Expected: FAIL — the level string isn't in the prompt (the current code only reads interview fields).

- [ ] **Step 3: Edit `engine/coach.py`.** The function already assigns `c = report.get("content")` near the top — leave that line in place. Replace only the existing `if c:` block (the one that appends the `answered_question` / `star_missing` lines) with this `kind`-aware branch (it reuses the existing `c`; do NOT add a second `c = report.get("content")`):
```python
    if c:
        if c.get("kind") == "proficiency":
            lines.append(f"- Estimated level: {c.get('level', '')}")
            lines.append(f"- Task completion: {c.get('task_completion', '')}")
        else:
            lines.append(
                f"- Answered the question: {'yes' if c.get('answered_question') else 'no'}"
            )
            if c.get("star_missing"):
                lines.append(f"- Missing STAR parts: {', '.join(c['star_missing'])}")
```
(If the current code used bracket access like `c['answered_question']`, switch to `c.get(...)` as shown. Keep the `c = report.get("content")` assignment, the clarity line, and everything else in the function unchanged.)

- [ ] **Step 4: Run to verify pass + full suite**

Run: `.venv/bin/pytest tests/test_coach.py -v` then `.venv/bin/pytest -q`
Expected: all green. The existing coach tests use an interview-shaped `content` with no `kind`, so `c.get("kind") == "proficiency"` is False → interview branch → unchanged behavior.

- [ ] **Step 5: Commit**

```bash
git add engine/coach.py tests/test_coach.py
git commit -m "feat: coach summarizes by content.kind (interview vs proficiency)"
```

---

## Task 6: Frontend mode selector + proficiency card

**Files:** Modify `web/static/index.html`, `web/static/recorder.js`, `web/static/results.js`.

- [ ] **Step 1: Add a mode selector to `web/static/index.html`** — insert ABOVE the existing `<label>Track: …</label>`:
```html
  <label>Mode:
    <select id="modeSelect"></select>
  </label>
```

- [ ] **Step 2: Update `web/static/recorder.js`** for mode-aware loading. Add element + globals near the top (after the existing `const trackSelect = ...` and globals):
```javascript
const modeSelect = document.getElementById("modeSelect");
let allTracks = [];
let trackMode = "interview";
const MODE_LABELS = { interview: "Interview Coach", japanese: "Japanese Practice" };
```
Replace the existing `loadTracks` function with:
```javascript
async function loadTracks() {
  try {
    const cfg = await (await fetch("/api/config")).json();
    window.ttsEnabled = !!cfg.tts_enabled;
  } catch (e) {
    window.ttsEnabled = false;
  }
  const data = await (await fetch("/api/tracks")).json();
  allTracks = data.tracks;
  const modes = [...new Set(allTracks.map((t) => t.mode))];
  modeSelect.innerHTML = "";
  modes.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = MODE_LABELS[m] || m;
    modeSelect.appendChild(opt);
  });
  populateTracksForMode(modeSelect.value);
}

function populateTracksForMode(mode) {
  const forMode = allTracks.filter((t) => t.mode === mode);
  trackSelect.innerHTML = "";
  forMode.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.track;
    opt.textContent = `${t.track} (${t.language})`;
    trackSelect.appendChild(opt);
  });
  loadQuestions(trackSelect.value);
}

modeSelect.addEventListener("change", () => populateTracksForMode(modeSelect.value));
```
Update the `loadQuestions(track)` function to capture the mode of the selected track (add these two lines after `trackLanguage = data.language || "en";`):
```javascript
  const t = allTracks.find((x) => x.track === track);
  trackMode = t ? t.mode : "interview";
  window.trackLanguage = trackLanguage;
```
(The `trackSelect` change listener stays `() => loadQuestions(trackSelect.value);`.)
In the `analyzeBtn` handler, add the mode field next to the others:
```javascript
  form.append("mode", trackMode);
```

- [ ] **Step 3: Render a proficiency card in `web/static/results.js`.** In `renderResults`, replace the existing `if (c) { … }` interview-content block with a `kind`-aware version:
```javascript
  if (c && c.kind === "proficiency") {
    html += `<div class="card"><h2>Proficiency <small>(practice estimate, not an official score)</small></h2>
      <p><b>Estimated level:</b> ${c.level}</p>
      <p><b>Task:</b> ${c.task_completion}</p>
      <p><b>Grammar:</b> ${c.grammar}</p>
      <p><b>Vocabulary:</b> ${c.vocabulary}</p>
      <p><b>Coherence:</b> ${c.coherence}</p>
      ${c.strengths && c.strengths.length ? `<p><b>Strengths:</b> ${c.strengths.join("; ")}</p>` : ""}
      <p><b>Suggestions:</b></p>
      <ul>${(c.suggestions || []).map((s) => `<li>${s}</li>`).join("")}</ul>
    </div>`;
  } else if (c) {
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
```
(This preserves the existing interview card exactly in the `else if` branch; only adds the proficiency branch ahead of it.)

- [ ] **Step 4: Headless verification**

```bash
.venv/bin/uvicorn web.app:app --port 8015 &
sleep 2
curl -s "http://localhost:8015/api/tracks" | python3 -c "import sys,json; d=json.load(sys.stdin); print({t['track']: t['mode'] for t in d['tracks']})"
curl -s -o /dev/null -w "index:%{http_code}\n" http://localhost:8015/
curl -s -o /dev/null -w "recorder:%{http_code}\n" http://localhost:8015/recorder.js
pkill -f "uvicorn web.app:app"
```
Expected: `{'interview_en': 'interview', 'language_jp': 'japanese'}`; both 200. Then `.venv/bin/pytest -q` → still green. KILL the server.

- [ ] **Step 5: Commit**

```bash
git add web/static/index.html web/static/recorder.js web/static/results.js
git commit -m "feat: frontend mode selector + proficiency results card"
```

---

## Definition of done

- [ ] `.venv/bin/pytest -q` fully green (≈73 tests: 66 prior + 7 new — 1 mode endpoint, 3 proficiency, 1 content-kind, 1 mode-forwarding, 1 coach-proficiency; the JP transcription integration test may skip if Kyoko isn't installed).
- [ ] Interview mode is byte-unchanged: English answers still get the STAR/interview rubric; existing interview tests pass untouched; `build_report` untouched.
- [ ] Japanese mode now routes to the **proficiency** analyzer (ACTFL-style practice estimate), not interview STAR; the coach summary and the results card reflect proficiency.
- [ ] `/api/tracks` returns `mode`; the frontend mode selector (Interview Coach / Japanese Practice) filters tracks and the analyze upload sends `mode`.
- [ ] The proficiency output is clearly labeled in the UI as a practice estimate, not an official score.
- [ ] `engine/` still has zero imports from `web/`.
- [ ] Manual (Dan): with Ollama running, switch to Japanese Practice, record a JP answer, confirm a proficiency card (level + dimensions + suggestions) and a Japanese coach summary.
- [ ] Azure per-phoneme pronunciation remains a separate future optional add-on.
