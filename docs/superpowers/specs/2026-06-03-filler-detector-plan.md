# Transcript-independent filled-pause detector — build plan

> **Status:** blocked on data. The detector needs NATURAL child speech to tune/validate; the
> synthetic TTS fixtures actively mislead (see `docs/superpowers/fillers-spike.md` iteration 4).
> Gate: `python -m web.reprocess --status` must report **READY** (>= 25 natural clips) first.
> This plan is execute-ready so the build can start the moment data exists.

## Why this exists

Cloud-lite filler detection is structurally blind: every Whisper-family model normalizes/deletes
fillers (`えーと`→`いいと`/`先週末`; `um`→gone), and the existing acoustic detector only recovers
fillers that leave a *silence gap* — not ones the ASR writes as a content word. Catching `えーと`
needs a detector that works on the **audio itself**, independent of the transcript.

## Prerequisite (the blocker)

A labeled set of the son's real recordings. The data pipeline already exists:
- Recordings auto-save to `s3://rehearsal-recordings-<acct>/recordings/` (encrypted).
- `python -m web.reprocess` writes `report_native.json` per clip (native pipeline: prosody +
  gap-fillers) — the dataset foundation.
- `python -m web.reprocess --status` reports natural-clip count vs the build threshold.

**First build step:** hand-label a small gold set from the real clips — for ~20–30 clips, mark
the true filled-pause spans (listen + look at the audio). Store `tests/fixtures/filler_gold.json`
(`{clip, spans:[{start,end,text}]}`). Without this, precision/recall is unmeasurable.

## The detector (approach B)

A filled pause (`えー`, `あー`, `um`) is acoustically: a **sustained, steady, monophthong vowel**,
typically **longer** than a normal syllable, with **flat pitch AND flat formants** (no diphthong
movement), often **lower energy** than stressed speech. Steady pitch ALONE is insufficient —
Japanese content syllables are also flat-pitched (proven: the naive prototype false-flagged
content at 1.3s/1.9–2.4s and missed `えーと`). Combine features:

1. Decode audio → mono PCM (16 kHz).
2. Per 10 ms frame: voiced/unvoiced (autocorrelation or YIN pitch), F0, RMS energy, and the
   first 1–2 formants (LPC) or MFCC stability as a monophthong proxy.
3. Candidate filled pause = a contiguous voiced run where, for >= ~250 ms: F0 CV is low AND
   formant/MFCC drift is low (monophthong) AND duration exceeds the speaker's median syllable
   length AND it isn't a pitch-accented peak. Tune thresholds against the gold set.
4. Map spans back to time; merge with the lexicon hits (`merge_hits`); emit `source="acoustic"`.

**Precision over recall** — a fabricated "(uh)" told to a 7-year-old is worse than a miss.
Target: precision >= 0.9 on the gold set first, then push recall.

## Where it slots in

- New module `engine/fillers/filled_pause.py` (pure numpy/scipy — NO parselmouth, so it can run
  in Lambda later). Keep the existing parselmouth `acoustic.py` for the native batch.
- Wire into `engine/fillers/__init__.detect_fillers` as a third source, gated so native vs
  cloud-lite can each choose detectors.
- TDD against `filler_gold.json` (real clips), not synthetic fixtures.

## Cloud-lite deployment (only after it validates natively)

The Lambda needs PCM, which means bundling a **static arm64 ffmpeg** (the lite build dropped
ffmpeg). Add it to the zip/layer, decode in-process, run `filled_pause.py`. Measure cold-start +
latency. **Do NOT ship to the son's production app until precision is validated on his real
clips.** Until then, the detector runs in the offline batch only.

## Validation & rollout

1. Build + tune natively against `filler_gold.json` (precision-first).
2. Report precision/recall honestly; if precision < ~0.9, keep iterating, don't ship.
3. Once solid: bundle ffmpeg, enable in lite mode behind a flag, A/B on a few clips, then deploy.
4. Update `fillers-spike.md` with the measured real-world numbers.
