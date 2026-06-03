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
