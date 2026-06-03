# Modes + Japanese Proficiency Rubric — Design

**Date:** 2026-06-03
**Status:** Approved (design); pending spec review before planning
**Builds on:** the interview track, acoustic fillers, and the Japanese free-response track
(`2026-06-03-japanese-track-design.md`).

## Motivation

`rehearsal` serves two goals for two people: **interview prep** (Dan, English) and
**STAMP/Japanese proficiency practice** (his son). These share ~90% of the machinery
(capture, transcription, delivery, fillers, clarity, coach, voice) and differ in ~10%
(content rubric, question library, persona). Forking would duplicate the hard 90% to vary
the easy 10%. Decision: **one app, two modes**, with the per-goal differences as
configuration.

Separately, the current orchestrator runs the **English interview STAR** analyzer on
**every** answer — including Japanese ones. That is wrong for the Japanese goal (STAMP is
free-response proficiency, not STAR). This iteration routes content analysis by mode and
adds an on-target Japanese **proficiency rubric** (local LLM).

## Goals

- Generalize the existing track system into **modes**: Interview Coach / Japanese Practice.
- Add a local Ollama **proficiency** analyzer (ACTFL-style practice estimate) for Japanese.
- Route content analysis + coach summary + frontend rendering by mode, with the interview
  path byte-unchanged.

## Non-goals (this iteration)

- ❌ Azure per-phoneme pronunciation — remains a future *optional* add-on (opt-in, accent
  drilling). Everything here is local; the recording never leaves the machine.
- ❌ Claiming official STAMP scores. The proficiency output is an honest **LLM practice
  estimate**, labeled as such — not an official/human rating.
- ❌ Heavy persona divergence. The existing warm/patient coach serves both; persona-per-mode
  is a noted cheap refinement, not built here.

## The mode model

A **mode** bundles `{tracks, content analyzer, persona}`. Implemented as a `"mode"` field
on each track JSON:
- `interview_en` → `"mode": "interview"`
- `language_jp` → `"mode": "japanese"`

`GET /api/tracks` exposes `mode` per track. The frontend adds a **mode selector** that
filters the track list and frames the experience. No new infrastructure — just
generalizing the track system already in place.

## Content routing (no `build_report` churn)

Both analyzers' result dataclasses carry a `kind` field:
- `ContentFeedback.kind = "interview"` (new field, default — positional construction stays valid)
- `ProficiencyFeedback.kind = "proficiency"`

`analyze_answer(audio_path, question, *, language, mode="interview", ...)` picks the
analyzer by mode and drops its result into the report's **existing `content` slot**
(`asdict` serializes either dataclass, including `kind`). `build_report` is untouched, and
the interview path is byte-identical. The coach and frontend read `content.kind` to decide
how to summarize/render.

`/api/analyze` gains a `mode` form field (default `"interview"` for back-compat) and
forwards it.

## Japanese proficiency module (`engine/proficiency.py`)

Local Ollama, mirrors `content.py`'s pure-prompt-build + parse + fake-client-testable
shape. `analyze_proficiency(question, answer, language="ja", model="llama3.1",
client=ollama) -> ProficiencyFeedback`:

```
ProficiencyFeedback(kind="proficiency", level, task_completion, grammar,
                    vocabulary, coherence, strengths: list, suggestions: list)
```
- `level`: estimated ACTFL-style level (e.g. "Intermediate-Mid").
- `task_completion`, `grammar`, `vocabulary`, `coherence`: one-sentence notes each.
- `strengths` / `suggestions`: 2-3 short items each (capped).
- The system prompt states it is a supportive practice estimate, not an official score, and
  must not invent content the speaker did not say.

## Coach + frontend by `kind`

- `coach.build_summary_prompt` branches: interview → "answered? / STAR missing"; proficiency
  → "estimated level / task completion". Existing interview coach tests (content without a
  `kind`) keep working (absence of `kind` ⇒ interview branch).
- `results.js` renders an interview card or a proficiency card based on `content.kind`.
- `recorder.js`: a mode selector groups tracks by mode; selecting a mode filters the track
  list, sets the language, and the analyze upload includes `mode`.

## Architecture touch-points

```
questions/interview_en.json   # MODIFY: add "mode": "interview"
questions/language_jp.json     # MODIFY: add "mode": "japanese"
web/app.py                     # MODIFY: /api/tracks returns mode; /api/analyze forwards mode
engine/content.py              # MODIFY: ContentFeedback.kind = "interview"
engine/proficiency.py          # NEW: analyze_proficiency + ProficiencyFeedback
engine/report.py               # MODIFY: analyze_answer picks analyzer by mode
engine/coach.py                # MODIFY: summarize by content.kind
web/static/{index.html,recorder.js,results.js}  # MODIFY: mode selector + proficiency card
```

Engine keeps zero web imports. `build_report` unchanged.

## Testing

- Pure/fake-client unit tests: `analyze_proficiency` (prompt build + parse + fake client),
  `ContentFeedback.kind`, coach proficiency branch, `/api/tracks` mode + `/api/analyze`
  mode forwarding (TestClient, monkeypatched engine).
- Existing 66 tests stay green: interview path unchanged; coach interview branch unaffected;
  `build_report` untouched.

## Build order

~6 tasks: mode field + `/api/tracks` → proficiency module → `ContentFeedback.kind` → route
by mode in `analyze_answer` + `/api/analyze` → coach by kind → frontend mode selector +
proficiency card. Azure pronunciation remains a separate future optional add-on.
