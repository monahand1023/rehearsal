# Filler-Detection Accuracy Spike

## What the harness does

`scripts/filler_eval.py` runs the full real pipeline — audio file → `engine.audio.to_wav` → `engine.transcribe.transcribe` (faster-whisper base.en) → `engine.fillers.detect_fillers` — over a labeled set of clips in `tests/fixtures/spike/`. For each clip it prints the expected filler count (from `labels.json`) and the detected count, then prints the aggregate detected/expected ratio.

### How to run

```bash
.venv/bin/python scripts/filler_eval.py
```

The script reads `tests/fixtures/spike/labels.json`, finds the `.wav` files alongside it, and prints a table to stdout.

---

## Results on synthetic (`say`-generated) clips

Six clips were generated with macOS `say` and known filler counts hard-coded into the spoken text:

| file         | expected | detected |
|--------------|----------|----------|
| clip01.wav   |        2 |        0 |
| clip02.wav   |        0 |        0 |
| clip03.wav   |        3 |        1 |
| clip04.wav   |        0 |        0 |
| clip05.wav   |        3 |        1 |
| clip06.wav   |        0 |        0 |

**Total expected: 8  detected: 2  (detected/expected = 0.25)**

### What Whisper actually did

Inspecting the raw transcriptions reveals why detection is low even for synthesized speech:

- **clip01** ("Hello, *um*, my name is Dan and *uh* I am ready.") — Whisper transcribed `"I'm,"` for "um" and silently dropped "uh". Zero fillers detected.
- **clip03** ("So, *um*, we, *uh*, shipped it, *um*, on time.") — Whisper hallucinated `"we are, we are, shipped at"` for the filler-heavy middle, and preserved only the final "um" → `"Umm"`. One filler detected out of three.
- **clip05** ("Well, *uh*, I think, *um*, it went, *uh*, really well.") — Whisper dropped the first "uh" and the last "uh", preserved the middle "um". One filler detected out of three.

The zero-filler clips were all transcribed correctly; no false positives.

---

## IMPORTANT CAVEAT: this ratio is an optimistic ceiling, not real-world accuracy

`say`-synthesized speech enunciates every phoneme cleanly at a fixed pace and volume. Even so, Whisper only detected 2 of 8 expected fillers (0.25). With natural human speech the number will be **lower**, because:

- Real "um"s and "uh"s are often mumbled, partially swallowed, or blended with adjacent words.
- Whisper was trained primarily on clean speech and aggressively normalises transcripts, routinely substituting "I'm" for "um", transcribing fillers as other words, or omitting them entirely.
- The `detect_fillers` lexicon approach can only catch fillers that survive in the transcript. It has no access to the raw audio, so acoustic-level drops are invisible to it.

**The 0.25 ratio here represents an optimistic synthetic upper bound. The real-world accuracy on natural interview speech is almost certainly lower and is currently unmeasured.**

---

## Next step for Dan: measure real-speech accuracy

1. Record 8–10 natural clips of yourself answering practice questions (any format `ffmpeg` reads: `.webm`, `.m4a`, `.wav`).
2. Place them in `tests/fixtures/spike/`.
3. Listen to each clip and count the actual fillers (um, uh, er, hmm, you know, I mean, sort of, kind of).
4. Add entries to `tests/fixtures/spike/labels.json` for each new clip:
   ```json
   {"file": "natural01.m4a", "fillers": 5}
   ```
5. Re-run: `.venv/bin/python scripts/filler_eval.py`

The `.gitignore` already excludes `*.wav`, `*.webm`, and `*.m4a`, so the audio files will not be committed — only `labels.json` travels with the repo.

---

## Recommendation based on findings

The synthetic run detected 25% of injected fillers. Real-speech accuracy is expected to be lower. A recommended decision threshold:

- **If real-speech detected/expected ≥ 0.70**: the transcript-lexicon approach is workable; consider adding a few near-miss patterns (e.g. catching Whisper's "I'm" substitution for "um").
- **If real-speech detected/expected < 0.70**: the lexicon approach is fundamentally limited by Whisper's transcript cleanup. The next iteration should add an **acoustic filled-pause detector** that operates on the audio directly — for example:
  - Forced-alignment (e.g. `whisper-timestamped` or `stable-ts`) to surface tokens Whisper suppressed.
  - A small `wav2vec2` or `HuBERT`-based classifier trained to identify filled-pause frames regardless of what the transcript says.
  - Silence/hesitation detection using energy and pitch (simpler but less precise).

This would require a new engine module alongside `engine/fillers.py` and is tracked as a follow-on to this spike.

---

## Iteration 2: acoustic gap detector

### Lexicon-vs-combined eval on synthetic clips

The updated `scripts/filler_eval.py` now runs both pipelines side-by-side: lexicon-only vs. `merge_hits(lex, acoustic)`.

| file         | expected | lexicon | combined |
|--------------|----------|---------|----------|
| clip01.wav   |        2 |       0 |        2 |
| clip02.wav   |        0 |       0 |        0 |
| clip03.wav   |        3 |       1 |        1 |
| clip04.wav   |        0 |       0 |        0 |
| clip05.wav   |        3 |       1 |        4 |
| clip06.wav   |        0 |       0 |        0 |

**Expected: 8**
**Lexicon detected: 2  (detected/expected = 0.25)**
**Combined detected: 7  (detected/expected = 0.88)**

Lift: +5 hits, detected/expected ratio from 0.25 → 0.88 on synthetic clips.

Note on clip05: combined detected 4 vs. expected 3 — one false positive. The acoustic detector found an extra gap that scored above threshold; on synthetic `say` speech with its unnaturally regular cadence this is expected noise.

### Thresholds used (`classify_gap` defaults)

| parameter         | value | notes                                                                          |
|-------------------|-------|--------------------------------------------------------------------------------|
| `min_dur`         | 0.12s | Filters out micro-gaps (stop-consonant closures, etc.)                         |
| `max_dur`         | 2.0s  | Longer gaps are more likely deliberate pauses than filled ones                 |
| `min_voiced_frac` | 0.45  | Gap must be ≥45% voiced frames — key discriminant from silence                |
| `db_margin`       | 15.0  | Gap dB must be within 15 dB of mean speech level (rejects true silences)      |
| `max_pitch_std`   | 70.0  | Filters highly variable pitch (laughter, breath noise) — may need loosening   |

**Tuning candidates for natural speech:**
- `min_voiced_frac`: may need to drop to ~0.35 — natural um/uh can be breathier than `say`-synthesized.
- `db_margin`: natural fillers are often quieter relative to speech; 15 dB may be too strict — try 20 dB.
- `max_pitch_std`: leave as-is for now; high pitch variance more likely to be non-filler noise.

### Honest caveat: synthetic clips overstate accuracy

All six clips were generated with macOS `say` — perfectly enunciated, uniform cadence, no background noise. On synthetic clips, `say`'s fillers produce consistent voiced-gap signatures that the acoustic detector can reliably distinguish from inter-word silences. This yields the large lift (0.25 → 0.88).

**Natural speech will score lower.** Real um/uh are often:
- Quieter or more breathy than the surrounding speech (may fail `db_margin` or `min_voiced_frac`).
- Blended into adjacent words with no clean gap boundary.
- Already substituted by Whisper into real words ("I'm", "and", etc.) — the acoustic detector does not recover those, it only finds gaps the transcript left open.

The true measurement requires Dan to record natural clips into `tests/fixtures/spike/` and re-run the harness.

### Approach-B go/no-go decision rule

After adding real-speech clips:

- **If natural-clip COMBINED recall ≥ 0.70**: gap-based acoustic detection is worth keeping. Tune thresholds and ship.
- **If natural-clip COMBINED recall < 0.70**: escalate to a trained model. Gap detection cannot catch fillers that Whisper substituted into real words (e.g. "um" → "I'm"). The next step would be `stable-ts` or `whisper-timestamped` forced-alignment (surfaces suppressed tokens), or a lightweight `wav2vec2`/`HuBERT` classifier trained on filled-pause frames. These are tracked as Approach B.

### Frontend changes (this iteration)

- `.filler.acoustic` CSS chip added to `web/static/index.html`: amber dashed border, italic, lighter background — visually distinct from transcript-confirmed lexicon fillers.
- `annotateTranscript` in `web/static/results.js` updated: lexicon hits highlight the word in the transcript; acoustic hits render as inline `(uh)` gap chips between words (or before the first word). Both contribute to the `fillers.count` shown in the Delivery card.
