# Audio Integration Testing + Coverage Audit — Design

**Date:** 2026-06-03
**Status:** Approved (design); pending spec review before planning

## Motivation

The suite has strong **unit** coverage (73 tests) but two real gaps:
1. **The orchestrator `analyze_answer` is never actually run** — it's only monkeypatched in
   web tests. The full pipeline (audio → transcribe → delivery → fillers → prosody →
   clarity → report) is never exercised end-to-end.
2. **No validation against known-content audio.** The acoustic filler detector is only
   *smoke*-tested (returns a list); it's never checked against audio with a known filler
   count. Existing fixtures are robotic `say` clips.

Idea (Dan's): use **ElevenLabs to synthesize known-content speech**, run it through the real
engine, and assert the feedback is sensible. This gives realistic audio with ground truth.

## Goals

- A repeatable way to generate **labeled, realistic audio fixtures** (ElevenLabs) with known
  text / language / filler-count / keywords.
- **End-to-end integration tests** that run the real engine on those fixtures and assert
  tolerant, ground-truth-based properties — finally exercising `analyze_answer`.
- A **coverage audit** (pytest-cov) + filling the unit gaps it surfaces.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Audio source | **ElevenLabs only** (Dan provides the key for a one-time generation) |
| Fixture strategy | **Generate-and-commit** — `.mp3` clips committed (synthetic, not personal; `.mp3` isn't gitignored) so tests run with **no key/cost at test time** |
| Assertions | **Tolerant** (keyword presence, count ranges, plausible bands) — TTS + Whisper both vary, so exact equality would be flaky |
| Ollama | Audio integration tests run with `run_content=False` (no Ollama). One **separate Ollama-gated** full-orchestrator test covers content/proficiency + coach |
| Scope | Audio e2e **+ coverage audit** (pytest-cov + fill unit gaps) |

## Components

### 1. Ground-truth manifest — `tests/fixtures/generated/manifest.json` (committed)
A small set (~5) of entries: `{id, language, mode, text, expected_fillers, keywords}`.
Mix of English (clean / with fillers / a STAR story) and Japanese (clean / with fillers).
The manifest is the source of truth for both generation and assertions.

### 2. Generation script — `scripts/gen_test_audio.py`
Reads the manifest, and for each entry calls the existing `ElevenLabsProvider.synthesize(
text, language)` to produce `tests/fixtures/generated/<id>.mp3`. Idempotent (skips clips
that already exist). Defaults to a stock ElevenLabs voice so only `ELEVENLABS_API_KEY` is
required (voices overridable via env). Run **once** with the key; output committed.

### 3. Audio integration tests — `tests/test_integration_audio.py`
Parametrized over the manifest, `skipif` a clip's `.mp3` is missing. For each clip, run the
**real orchestrator** `analyze_answer(clip, question, mode=mode, run_content=False)` (which
runs to_wav → transcribe → delivery → fillers[lexicon+acoustic] → prosody → clarity →
build_report) and assert:
- transcript contains **≥1** expected keyword (kana/kanji present for JP);
- fillers: clips **with** fillers detect **≥1**; clips **without** detect **≤1** (allow one
  acoustic false positive);
- WPM in a wide plausible band; clarity ∈ (0, 1];
- every report section present; `content` and `spoken_summary` are `None` (content off).
(Converted WAV written to a tmp dir, never into the fixtures dir.)

### 4. Ollama-gated full e2e — in `tests/test_integration_audio.py`
`skipif` Ollama isn't reachable. Runs `analyze_answer(..., run_content=True)` on one English
interview clip (assert `content.kind == "interview"`, non-empty `spoken_summary`) and one
Japanese clip (assert `content.kind == "proficiency"`). This is the first true full-pipeline
test including the LLM + coach.

### 5. Coverage audit — pytest-cov + gap-fill
Add `pytest-cov` + config (`source = ["engine", "web"]`). Measure, then add targeted unit
tests for the under-covered spots, known candidates being: `audio.to_wav` default dst path;
`detect_fillers` acoustic-on/off branching; `content.parse_response` missing-`star_present`;
`/api/speak` 502-on-`TTSError` path; a direct `/api/questions` JP test.

## Non-goals

- ❌ A `say` fallback backend (Dan will provide the ElevenLabs key).
- ❌ Replacing the existing `say` fixtures (`hello.wav`, `hello_ja.wav`) — they keep serving
  the transcribe/prosody integration tests.
- ❌ 100% coverage targets — fill meaningful gaps, don't chase vanity numbers.

## Risks

- **TTS/ASR variance → flaky tests.** Mitigated by tolerant assertions (ranges/keywords,
  never exact strings/counts).
- **Generation needs the key + a few cents of credit (one-time).** Mitigated by committing
  the clips so the suite runs keyless thereafter.
- **ElevenLabs may render fillers cleanly** (like `say`) — so detection on these clips is an
  optimistic check, not a real-world accuracy number (that still needs Dan's natural clips
  via the spike). The integration tests assert *detection happens*, not a recall figure.

## Build order

~6 tasks: pytest-cov setup → unit gap-fill → manifest + generation script → generate +
commit fixtures (key-assisted) → audio integration tests → Ollama-gated full e2e.
