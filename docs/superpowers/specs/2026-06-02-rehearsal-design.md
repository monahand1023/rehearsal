# rehearsal — Design

**Date:** 2026-06-02
**Status:** Approved (design); pending spec review before planning
**Working name:** `rehearsal` (rename freely)

## One-line

A local web app where you pick a practice question, record your spoken answer, and
get AI feedback on **how you said it** (pace, pauses, filler words, monotone) and
**what you said** (did you answer, STAR structure, conciseness) — built for job
interview prep and, later, language speaking tests (e.g. a Japanese STAMP-style test).

## Goals

- Practice answering real interview / speaking-test questions out loud.
- Get feedback on **delivery** derived from the *audio itself*, not just the transcript:
  filler words ("um/uh/like"), speaking too fast/slow, long dead-air pauses, monotone.
- Get feedback on **content** (interview track): whether the question was actually
  answered, STAR structure, rambling/hedging.
- Run locally and privately by default, with clean boundaries so it could become a
  shareable web app later.

## Non-goals (v1, explicitly out — YAGNI)

- ❌ Webcam / video / body-language analysis (eye contact, posture, fidgeting).
- ❌ Real-time live metering while you speak. v1 is **record → analyze → feedback**.
- ❌ Accounts, hosting, multi-user, persistent cross-session history. Recordings are
  analyzed then discarded unless explicitly saved.
- ❌ Mobile-optimized UI. Desktop browser only.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | Personal-first, but clean boundaries so it can become shareable ("me now, others later") |
| Use cases | Both interview + language test eventually; **shared delivery core first**, then branch |
| Local vs cloud | **Hybrid** — local by default; pronunciation is a pluggable provider with optional cloud (Azure) |
| Capture | **Audio only** (mic). No video in v1. |
| Feedback timing | **Post-hoc** (record then analyze), not real-time |
| First build target | **Interview / English track end-to-end first**, then JP / pronunciation |

## Architecture

```
Browser (record)  ──audio blob──►  Python backend (FastAPI)  ──►  Analysis engine (importable package)
   MediaRecorder                      receives, orchestrates          returns structured JSON
   ◄──────────────────── feedback JSON ──────────────────────────────────┘
```

The **analysis engine is a standalone, importable Python package**. The web layer only
orchestrates (receive upload → call engine → return JSON). The engine has no web
dependencies, so the same code could later sit behind a multi-user backend unchanged.

### Engine layers

1. **Delivery core** — language-agnostic, runs for every recording. Feeds both tracks.
2. **Content module** — interview track. LLM over transcript. Pluggable.
3. **Pronunciation module** — language-test track. Pluggable; local-default with an
   optional Azure provider behind a `Provider` interface.

### Data flow

Pick a question → record answer in browser → stop → upload audio to local server →
engine transcribes + analyzes → feedback screen. A "processing…" state covers the
few seconds of analysis.

## Feedback produced

### Delivery core (every answer, both tracks)

| Metric | How | Reliability |
|---|---|---|
| Speaking rate (WPM / syllables·sec) over time | Whisper word timestamps | High |
| Pause map — location, length, dead-air flags | Word timestamps + VAD | High |
| Filler words (um, uh, like, you know) — count + timeline | **Dedicated detector** (Whisper drops these) | ⚠️ Needs tuning |
| Monotone / pitch range / energy | parselmouth (Praat) | High |
| Time-to-first-word, total talk time | Word timestamps | High |

### Content module (interviews) — LLM over transcript

- Did you actually answer the question that was asked?
- STAR structure detection (Situation / Task / Action / Result) and what's missing.
- Conciseness / rambling, hedging, vague-claim flags.
- One example "tighter rewrite" of an answer.

### Pronunciation module (language tests — later)

- Per-phoneme / per-word goodness scores, mispronunciation flags, fluency & prosody
  score (STAMP-style). Local forced-alignment + goodness-of-pronunciation by default;
  Azure Speech as an opt-in provider for sharper scoring.

### Output

One feedback screen:

- Overall scores up top.
- Annotated transcript: fillers highlighted, long pauses marked, (later) mispronounced
  words flagged.
- 3 concrete "next time, try…" coaching notes from the LLM.

## Tech stack

- **Backend:** FastAPI (async, simple file upload; also serves the static frontend so
  it's one process to run).
- **Frontend:** plain HTML + vanilla JS, no framework. `MediaRecorder` capture, `fetch`
  upload, render feedback JSON.
- **Engine deps:** `faster-whisper` (word timestamps, fast on Apple Silicon),
  `parselmouth` (Praat prosody), `Ollama` (local content LLM, same pattern as cleancut),
  forced-alignment for pronunciation, Azure Speech SDK behind an optional provider.

## Project layout

```
rehearsal/
  engine/
    transcribe.py      # faster-whisper wrapper → words + timestamps
    delivery.py        # pace, pauses, prosody, talk-time
    fillers.py         # filler detection (isolated risk module)
    content.py         # interview LLM analysis
    pronunciation/
      base.py          # Provider interface
      local.py         # forced-alignment + GOP
      azure.py         # optional cloud provider
    report.py          # merge module outputs → one feedback JSON
  web/
    app.py             # FastAPI: /questions, /analyze
    static/            # index.html, recorder.js, results.js
  questions/
    interview_en.json  # seeded, editable
    language_jp.json
  tests/
    fixtures/          # short labeled audio clips
```

Each engine module is independently testable: audio (+ optional reference text) in →
typed result out. That isolation keeps the system reliable as it grows.

## Risks

1. **Filler detection (highest risk).** Whisper omits most "um"s, so this needs its own
   approach and accuracy bar. **Plan:** isolate in `fillers.py`; start with a **spike** —
   record ~10 scripted clips with known counts of "um/uh/like", build a tiny labeled
   fixture set, measure precision/recall before trusting it. Expect iteration here.
2. **Local pronunciation scoring (medium risk).** Forced-alignment + GOP is rougher than
   Azure. The provider interface lets us ship local, judge "good enough", and flip to
   Azure for the JP track without rework. (Deferred to the second build target.)
3. **Whisper latency on long answers.** Mitigation: `faster-whisper` + a "processing…"
   state. A 2-minute answer should analyze in a few seconds on Apple Silicon.

## Testing approach

- Per-module unit tests against fixed audio fixtures (deterministic: same clip → same
  numbers).
- The filler labeled-set doubles as a regression guard.
- A couple of end-to-end tests: known clip → expected feedback JSON shape.

## Build order

1. **Interview / English track, end-to-end** — shared delivery core + content module +
   web shell + seeded `interview_en.json`. Exercises delivery + content with the least
   language-specific risk.
2. **JP / language-test track** — pronunciation module (local provider first, optional
   Azure), seeded `language_jp.json`.
