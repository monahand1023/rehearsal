# Acoustic Filler Detection — Design (iteration 2)

**Date:** 2026-06-03
**Status:** Approved (design); pending spec review before planning
**Builds on:** `2026-06-02-rehearsal-design.md` (interview/English track) and the finding in
`docs/superpowers/fillers-spike.md`.

## Motivation

The filler-accuracy spike showed the transcript-lexicon detector recovered only ~0.25 of
fillers **even on clean synthesized speech**, because Whisper rewrites/drops "um"/"uh" at
the transcript layer ("um"→"I'm", "uh"→dropped) before `detect_fillers` ever sees them.
The detection *logic* is fine; the bottleneck is upstream ASR.

**Key insight:** a dropped filler doesn't leave the audio — it becomes a **voiced gap**
between two transcribed words. We already compute inter-word gaps (for pause detection)
and already depend on parselmouth. So we can re-examine each gap acoustically and decide
*silence* (a real pause) vs *voiced* (a filled pause Whisper swallowed).

## Goal

Improve filler **recall** by adding an acoustic voiced-gap detector that recovers dropped
fillers, unioned with the existing lexicon detector. Stay fully local (no new
dependencies). Make filler detection pluggable so a trained model can replace/augment it
later without touching the report or web layers.

## Non-goals (this iteration)

- ❌ A trained ML filler model (wav2vec2 / PodcastFillers). That is the documented
  escalation (approach B) if acoustic recall on natural clips still falls short.
- ❌ Catching fillers Whisper **substituted into a real word** ("um"→"I'm"). Those leave
  no gap and are out of reach for a gap-based detector — they are the trigger for B.
- ❌ Distinguishing "um" vs "uh" acoustically (needs phonetics). Acoustic hits are
  labeled generically.

## Decision (from brainstorming)

Approach **A** — acoustic voiced-gap detector, pluggable, unioned with the lexicon. (B and
C were considered; B is the future escalation.)

## Architecture

Convert `engine/fillers.py` into an `engine/fillers/` package, backward-compatible:

```
engine/fillers/
  __init__.py     # orchestrator detect_fillers(); re-exports public names
  types.py        # FillerHit, FillerReport
  lexicon.py      # detect_lexicon_fillers(transcript, include_like=False) -> list[FillerHit]
  acoustic.py     # classify_gap() [pure] + detect_acoustic_fillers(transcript, wav_path)
```

**Public API (unchanged signature, extended):**
```
detect_fillers(transcript, wav_path=None, include_like=False, acoustic=True) -> FillerReport
```
- `wav_path=None` → lexicon only (exactly today's behavior; keeps all 38 tests green).
- `wav_path` given + `acoustic=True` → lexicon ∪ acoustic, merged.
- Re-exports `FillerHit`, `FillerReport` so `from engine.fillers import ...` is unchanged.

The orchestrator (`engine/report.py::analyze_answer`) already has the wav; it passes
`wav_path=wav` so the acoustic path lights up in the real app.

No abstract provider class — "pluggable" = separate functions + a merge step. Adding a
model later = add `model.py` with `detect_model_fillers()` and include it in the merge.

## Acoustic algorithm (`acoustic.py`)

**Candidate gaps:** the leading gap `(0, words[0].start)` and every inter-word gap
`(words[i].end, words[i+1].start)`. (Trailing gap excluded — usually breath/silence.)

**Pure decision function (unit-tested):**
```
classify_gap(voiced_frac, gap_db, speech_db, pitch_std, duration,
             min_dur=0.12, max_dur=2.0, min_voiced_frac=0.45,
             db_margin=15.0, max_pitch_std=70.0) -> bool
```
A gap is a filled pause when:
- `min_dur <= duration <= max_dur`, AND
- `voiced_frac >= min_voiced_frac` (it's voiced, not silence), AND
- `gap_db >= speech_db - db_margin` (energy near speech level, not the silence floor), AND
- `pitch_std <= max_pitch_std` (steady-ish — a sustained vowel, not a word).

**Feature-extraction wrapper (smoke-tested on a fixture):**
`detect_acoustic_fillers(transcript, wav_path)` loads the Sound once, computes pitch +
intensity once, derives `speech_db` from the overall mean intensity, then for each
candidate gap extracts `voiced_frac`, `gap_db`, `pitch_std`, and calls `classify_gap`.
Each positive → `FillerHit(text="(uh)", start, end, source="acoustic")`.

This mirrors `prosody.py` (pure `summarize_pitch` + thin parselmouth wrapper).

## Merge + labeling

- `FillerHit` gains a field: `source: str = "lexicon"` (default keeps positional
  construction in existing tests valid; `"acoustic"` for gap hits).
- Merge: union lexicon + acoustic hits; drop an acoustic hit that **overlaps in time**
  with a lexicon hit (prefer lexicon — it carries the real word). Sort by `start`.
- `FillerReport.count` / `per_minute` computed over the merged hits.
- Report serialization (`engine/report.py`) includes `source` per hit.

## Frontend (`web/static/results.js`)

Acoustic hits sit in transcript gaps (no word to highlight). Render by `source`:
- `source == "lexicon"` → highlight the matching transcript word (today's behavior).
- `source == "acoustic"` → insert an inline chip (e.g. a styled `(uh)`) at the gap,
  the same way pause markers are inserted between words by time.

## Validation

Extend `scripts/filler_eval.py` to print **lexicon-only vs lexicon+acoustic** detected
counts side by side, so the lift is measurable and thresholds can be tuned on the
synthetic clips now and Dan's natural clips later. Update `fillers-spike.md` with the
before/after table and the chosen thresholds.

## Testing

- **Pure unit tests** for `classify_gap` (synthetic feature values: voiced filled pause →
  True; silent gap → False; too-short/too-long → False; loud but unvoiced → False).
- **Pure unit tests** for the merge/dedup (overlapping lexicon+acoustic → one hit; source
  preserved; sorted).
- **Smoke integration test**: `detect_acoustic_fillers(transcript, fixture_wav)` runs and
  returns a `list[FillerHit]` without error.
- Existing `detect_fillers(transcript)` (no wav) tests stay green unchanged.
- Real accuracy is measured by the eval harness on labeled clips, not unit tests
  (consistent with how transcribe/prosody integration is handled).

## Risks

- **Threshold tuning (main risk).** Mitigated by the eval harness: tune against labeled
  clips; report the lift. If natural-clip recall stays low, escalate to approach B.
- **False positives on voiced breath / between-word coarticulation.** Mitigated by the
  duration bounds + steadiness (pitch_std) test; tune on real clips.

## Build order

Single coherent iteration, ~5 TDD tasks: package refactor → lexicon move → acoustic
(pure classify_gap → wrapper) → merge + orchestrator + report `source` → eval harness +
frontend chips.
