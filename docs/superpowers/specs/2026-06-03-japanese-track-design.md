# Japanese Track — Design (free-response, Phase 1)

**Date:** 2026-06-03
**Status:** Approved (design); pending spec review before planning
**Builds on:** `2026-06-02-rehearsal-design.md` (interview/English track) and the acoustic
filler work (`2026-06-03-acoustic-filler-detection-design.md`).

## Motivation

The second major build target is the Japanese / speaking-test track. The word
"pronunciation" hides a fork: a true **STAMP-style free-response** test has **no reference
text** (you speak freely, scored holistically on fluency/intelligibility/content), whereas
**read-aloud pronunciation scoring** knows the target sentence and scores per-phoneme. They
stress different parts of the system.

**Decision (from brainstorming): both, phased.**
- **Phase 1 (this spec): free-response Japanese** — the coherent, fully-local slice that
  reuses the existing core.
- **Phase 2 (future, separate plan): read-aloud per-phoneme pronunciation** — a pluggable
  provider, Azure-opt-in. Sketched here; planned later.

## Goal (Phase 1)

Make `rehearsal` work for free-response Japanese speaking practice: pick a Japanese
prompt, speak freely, get feedback on delivery (pace, pauses, fillers), a clarity proxy,
and content — with a warm Japanese coach summary and optional Japanese voice.

## Reused as-is (already language-parameterized)

- **Delivery core** (pace, pauses, prosody) — language-agnostic.
- **Acoustic gap-filler detector** — language-agnostic; catches Japanese filled pauses
  (えーと/あのー) with no changes. (Important: lexical filler detection is *harder* in
  Japanese — no word spaces — so the acoustic path carries more weight here.)
- **Coach** (`compose_spoken_summary(report, language="ja")`) and **ElevenLabs voice**
  (`ELEVENLABS_VOICE_JA`, model `eleven_multilingual_v2`).
- `/api/analyze` already forwards `language`.

## New in Phase 1

1. **Multilingual transcription.** `engine/transcribe.py` is hardcoded to `base.en`.
   Generalize to pick a model + language from the track language: English → `base.en`
   (today), non-English → a multilingual model (`small`) with the language forced
   (`language="ja"`). The orchestrator passes the track language through to `transcribe`.
2. **Japanese filler lexicon.** Add a Japanese filler set
   (えーと/えー/ええと/えっと/あの/あのー/その/そのー/まあ/なんか/んー); `detect_lexicon_fillers`
   selects the set by `transcript.language`. The acoustic detector backstops misses.
   `_norm` also strips Japanese punctuation (、。！？「」).
3. **Clarity proxy.** Free-response has no reference text, so "mumbling/clarity" is proxied
   by **mean Whisper word-confidence** (`word.probability`, already captured): a
   `clarity` report section with mean confidence + low-confidence words. Labeled honestly
   as a confidence proxy — NOT a pronunciation score (that's Phase 2).
4. **`questions/language_jp.json`** — STAMP-style prompts (describe a photo, narrate your
   day, give an opinion), `language: "ja"`.
5. **Frontend track switching** — the UI hardcodes `interview_en`; add a track picker
   driven by a new `GET /api/tracks` that lists available question files. Switching a
   track loads its questions and sets the language sent to `/api/analyze`. The results
   view shows the clarity proxy.

## Architecture touch-points

```
engine/transcribe.py   # MODIFY: language-aware model/lang selection (pure _resolve + transcribe)
engine/fillers/lexicon.py  # MODIFY: per-language filler sets; JP punctuation in _norm
engine/clarity.py      # NEW: analyze_clarity(transcript) -> ClarityMetrics (mean confidence)
engine/report.py       # MODIFY: analyze_answer passes language to transcribe; build_report adds clarity
engine/coach.py        # MODIFY (light): mention clarity in the summary prompt when present
web/app.py             # MODIFY: GET /api/tracks
questions/language_jp.json   # NEW
web/static/{index.html,recorder.js,results.js}  # MODIFY: track picker + clarity display
```

Engine stays free of web imports (unchanged boundary).

## Known rough edges (scoped, honest)

- **Pace mis-calibration for Japanese.** Whisper's JP "words" are short, so words/min reads
  high. Phase 1 keeps the metric; the JP coach is told it's approximate and frames pace
  qualitatively. A mora/character-based rate is a later tune (noted, not built).
- **Clarity proxy is rough.** Model confidence ≠ true intelligibility. Real per-phoneme
  scoring is Phase 2.
- **JP filler lexicon recall is limited** by Whisper's spaceless segmentation; the acoustic
  detector is the primary recall mechanism for Japanese.

## Phase 2 sketch (designed, not built here)

Read-aloud pronunciation as a pluggable `PronunciationProvider` (mirrors the TTS provider):
- `AzurePronunciationProvider` — cloud, **opt-in** (key-gated like ElevenLabs), per-phoneme
  goodness + accuracy/fluency/completeness/prosody, strong Japanese support.
- Local forced-alignment + GOP as a rough fallback.
- A read-aloud mode: show a target sentence, score the spoken attempt against it.
Local-vs-Azure default is deferred to the Phase 2 plan.

## Testing

- Pure unit tests: `_resolve` (model/lang selection), JP filler detection (synthetic JP
  transcript), `analyze_clarity` (synthetic word confidences), `/api/tracks` (TestClient).
- Integration (best-effort, skip if unavailable): a `say -v Kyoko` Japanese fixture clip →
  `transcribe(wav, language="ja")` produces Japanese text. First JP run downloads the
  multilingual model (~one-time).
- Existing 53 tests stay green (English path defaults unchanged).

## Build order

Single Phase-1 iteration, ~5 tasks: multilingual transcribe + wire → JP fillers → clarity
proxy → JP questions + `/api/tracks` → frontend track switching + clarity display.
Phase 2 (pronunciation provider) is a separate later plan.
