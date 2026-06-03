# Acoustic Filler Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover fillers Whisper drops by adding an acoustic voiced-gap detector (parselmouth) unioned with the existing lexicon detector, behind a pluggable `engine/fillers/` package — with measurable lift via the eval harness.

**Architecture:** Convert `engine/fillers.py` → `engine/fillers/` package (`types`, `lexicon`, `acoustic`, orchestrator in `__init__`). `detect_fillers(transcript, wav_path=None, ...)` stays backward-compatible (no wav → lexicon only). The acoustic detector classifies inter-word gaps as silence vs filled pause from voicing + energy + pitch-steadiness. A `source` field on `FillerHit` drives frontend rendering (highlight word vs gap chip).

**Tech Stack:** Python 3.11+, parselmouth (already a dep — no new deps), pytest. Reuses `engine/transcribe.py`, `engine/types.py`.

---

## File structure

```
engine/fillers/            # was engine/fillers.py
  __init__.py              # detect_fillers() orchestrator + merge_hits(); re-exports
  types.py                 # FillerHit (+source), FillerReport
  lexicon.py               # detect_lexicon_fillers() — moved current logic
  acoustic.py              # classify_gap() [pure], candidate_gaps() [pure], detect_acoustic_fillers()
engine/report.py           # MODIFY: pass wav_path to detect_fillers; serialize source
scripts/filler_eval.py     # MODIFY: lexicon-only vs combined columns
web/static/results.js      # MODIFY: render acoustic hits as gap chips
web/static/index.html      # MODIFY: .acoustic chip style
tests/test_fillers.py            # existing — stays green; +source assertion
tests/test_fillers_acoustic.py   # NEW — classify_gap, candidate_gaps, merge, smoke
docs/superpowers/fillers-spike.md  # MODIFY: before/after + thresholds
```

**Pre-req:** the interview track is built and all 38 tests pass.

---

## Task 1: Refactor fillers → package + `source` field (no behavior change)

**Files:**
- Remove: `engine/fillers.py`
- Create: `engine/fillers/__init__.py`, `engine/fillers/types.py`, `engine/fillers/lexicon.py`
- Modify: `engine/report.py`, `tests/test_fillers.py`

- [ ] **Step 1: Add a failing test** for the new `source` field — append to `tests/test_fillers.py`:

```python
def test_filler_hits_have_lexicon_source(make_transcript):
    tr = make_transcript([("um", 0.0, 0.3)], duration=2.0)
    r = detect_fillers(tr)
    assert r.hits[0].source == "lexicon"
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/pytest tests/test_fillers.py::test_filler_hits_have_lexicon_source -v`
Expected: FAIL — `FillerHit` has no attribute `source` (or AttributeError).

- [ ] **Step 3: Remove the old module and create the package**

Run: `git rm engine/fillers.py`

Create `engine/fillers/types.py`:
```python
from dataclasses import dataclass


@dataclass
class FillerHit:
    text: str
    start: float
    end: float
    source: str = "lexicon"


@dataclass
class FillerReport:
    hits: list
    count: int
    per_minute: float
```

Create `engine/fillers/lexicon.py` (the current logic, now returning a list and stamping source):
```python
from engine.types import Transcript
from engine.fillers.types import FillerHit

SINGLE_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mhm", "mm"}
PHRASE_FILLERS = [("you", "know"), ("i", "mean"), ("sort", "of"), ("kind", "of")]
LIKE = "like"


def _norm(s: str) -> str:
    return s.lower().strip().strip(".,!?;:\"'").strip()


def detect_lexicon_fillers(transcript: Transcript,
                           include_like: bool = False) -> list[FillerHit]:
    words = transcript.words
    norms = [_norm(w.text) for w in words]
    hits: list[FillerHit] = []
    used: set[int] = set()

    for i in range(len(words) - 1):
        if i in used or i + 1 in used:
            continue
        if (norms[i], norms[i + 1]) in PHRASE_FILLERS:
            hits.append(FillerHit(f"{words[i].text} {words[i + 1].text}",
                                  words[i].start, words[i + 1].end, source="lexicon"))
            used.add(i)
            used.add(i + 1)

    for i, w in enumerate(words):
        if i in used:
            continue
        if norms[i] in SINGLE_FILLERS or (include_like and norms[i] == LIKE):
            hits.append(FillerHit(w.text, w.start, w.end, source="lexicon"))
            used.add(i)

    hits.sort(key=lambda h: h.start)
    return hits
```

Create `engine/fillers/__init__.py` (orchestrator — lexicon only for now; wav_path/acoustic accepted so `report.py` updates once and Task 4 wires the acoustic path):
```python
from engine.types import Transcript
from engine.fillers.types import FillerHit, FillerReport
from engine.fillers.lexicon import detect_lexicon_fillers

__all__ = ["FillerHit", "FillerReport", "detect_fillers", "detect_lexicon_fillers"]


def detect_fillers(transcript: Transcript, wav_path: str | None = None,
                   include_like: bool = False, acoustic: bool = True) -> FillerReport:
    hits = detect_lexicon_fillers(transcript, include_like=include_like)
    hits.sort(key=lambda h: h.start)
    minutes = transcript.duration / 60 if transcript.duration > 0 else 1e-9
    return FillerReport(hits=hits, count=len(hits),
                        per_minute=round(len(hits) / minutes, 1))
```

- [ ] **Step 4: Update `engine/report.py`** — pass the wav and serialize `source`.

Change the `detect_fillers(transcript)` call inside `analyze_answer` to:
```python
    fillers = detect_fillers(transcript, wav_path=wav)
```
Change the fillers serialization in `build_report` to include `source`:
```python
        "fillers": {
            "count": fillers.count,
            "per_minute": fillers.per_minute,
            "hits": [{"text": h.text, "start": round(h.start, 2),
                      "end": round(h.end, 2), "source": h.source}
                     for h in fillers.hits],
        },
```

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all pass (39 — the 38 existing + the new source test). The existing `test_fillers.py` and `test_report.py` keep passing: `detect_fillers(tr)` still works (wav_path defaults None), and `FillerHit("um", 0.4, 0.6)` still constructs (source defaults).

- [ ] **Step 6: Commit**

```bash
git add engine/fillers engine/report.py tests/test_fillers.py
git commit -m "refactor: fillers package + source field (no behavior change)"
```

---

## Task 2: Acoustic gap classifier — pure `classify_gap`

**Files:**
- Create: `engine/fillers/acoustic.py`
- Create: `tests/test_fillers_acoustic.py`

- [ ] **Step 1: Write failing tests** in `tests/test_fillers_acoustic.py`:

```python
from engine.fillers.acoustic import classify_gap


def test_voiced_filled_pause_is_filler():
    assert classify_gap(voiced_frac=0.8, gap_db=60, speech_db=65,
                        pitch_std=20, duration=0.4) is True


def test_silent_gap_is_not_filler():
    assert classify_gap(voiced_frac=0.05, gap_db=35, speech_db=65,
                        pitch_std=0, duration=0.6) is False


def test_too_short_gap_rejected():
    assert classify_gap(voiced_frac=0.9, gap_db=64, speech_db=65,
                        pitch_std=10, duration=0.05) is False


def test_too_long_gap_rejected():
    assert classify_gap(voiced_frac=0.9, gap_db=64, speech_db=65,
                        pitch_std=10, duration=3.0) is False


def test_loud_but_unvoiced_rejected():
    assert classify_gap(voiced_frac=0.1, gap_db=64, speech_db=65,
                        pitch_std=10, duration=0.4) is False


def test_voiced_but_too_quiet_rejected():
    assert classify_gap(voiced_frac=0.6, gap_db=40, speech_db=65,
                        pitch_std=10, duration=0.4) is False


def test_unsteady_pitch_rejected():
    assert classify_gap(voiced_frac=0.7, gap_db=62, speech_db=65,
                        pitch_std=120, duration=0.4) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_fillers_acoustic.py -v`
Expected: FAIL — `cannot import name 'classify_gap'`.

- [ ] **Step 3: Create `engine/fillers/acoustic.py`** with the pure classifier:

```python
def classify_gap(voiced_frac: float, gap_db: float, speech_db: float,
                 pitch_std: float, duration: float,
                 min_dur: float = 0.12, max_dur: float = 2.0,
                 min_voiced_frac: float = 0.45, db_margin: float = 15.0,
                 max_pitch_std: float = 70.0) -> bool:
    """True when a gap looks like a filled pause (um/uh) rather than silence."""
    if duration < min_dur or duration > max_dur:
        return False
    if voiced_frac < min_voiced_frac:
        return False
    if gap_db < speech_db - db_margin:
        return False
    if pitch_std > max_pitch_std:
        return False
    return True
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_fillers_acoustic.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add engine/fillers/acoustic.py tests/test_fillers_acoustic.py
git commit -m "feat: pure classify_gap filled-pause heuristic"
```

---

## Task 3: Gap candidates + parselmouth feature wrapper

**Files:**
- Modify: `engine/fillers/acoustic.py` (add `candidate_gaps`, `detect_acoustic_fillers`)
- Modify: `tests/test_fillers_acoustic.py` (append)

- [ ] **Step 1: Append failing tests** to `tests/test_fillers_acoustic.py`:

```python
import os
import pytest

from engine.types import Word
from engine.fillers.acoustic import candidate_gaps, detect_acoustic_fillers

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")


def test_candidate_gaps_inter_word():
    words = [Word("a", 0.0, 0.5), Word("b", 1.0, 1.5), Word("c", 1.6, 2.0)]
    gaps = candidate_gaps(words)
    assert (0.5, 1.0) in gaps          # real gap kept
    assert (1.5, 1.6) in gaps          # small gap still a candidate
    assert all(g[1] > g[0] for g in gaps)


def test_candidate_gaps_leading():
    words = [Word("a", 0.8, 1.2)]
    gaps = candidate_gaps(words)
    assert (0.0, 0.8) in gaps          # leading gap included


def test_candidate_gaps_empty():
    assert candidate_gaps([]) == []


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture missing")
def test_detect_acoustic_runs_on_fixture():
    from engine.transcribe import transcribe
    tr = transcribe(FIXTURE)
    hits = detect_acoustic_fillers(tr, FIXTURE)
    assert isinstance(hits, list)
    for h in hits:
        assert h.source == "acoustic"
        assert h.end > h.start
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_fillers_acoustic.py -v`
Expected: FAIL — `cannot import name 'candidate_gaps'`.

- [ ] **Step 3: Add to `engine/fillers/acoustic.py`** (above `classify_gap` keep as-is; add imports at top and these functions):

```python
import statistics

import parselmouth
from parselmouth.praat import call

from engine.types import Transcript
from engine.fillers.types import FillerHit
```
```python
def candidate_gaps(words, audio_start: float = 0.0):
    """Leading gap + every inter-word gap (trailing excluded)."""
    gaps = []
    if not words:
        return gaps
    if words[0].start > audio_start:
        gaps.append((audio_start, words[0].start))
    for a, b in zip(words, words[1:]):
        if b.start > a.end:
            gaps.append((a.end, b.start))
    return gaps


def _gap_features(pitch, intensity, t0, t1):
    times = pitch.xs()
    freqs = pitch.selected_array["frequency"]
    in_window = [f for t, f in zip(times, freqs) if t0 <= t <= t1]
    total = len(in_window)
    voiced = [f for f in in_window if f and f > 0]
    voiced_frac = (len(voiced) / total) if total else 0.0
    pitch_std = statistics.pstdev(voiced) if len(voiced) > 1 else 0.0
    try:
        gap_db = float(call(intensity, "Get mean", t0, t1, "dB"))
    except Exception:
        gap_db = 0.0
    return voiced_frac, gap_db, pitch_std


def detect_acoustic_fillers(transcript: Transcript, wav_path: str,
                            **thresholds) -> list[FillerHit]:
    words = transcript.words
    if not words:
        return []
    snd = parselmouth.Sound(wav_path)
    pitch = snd.to_pitch()
    intensity = snd.to_intensity()
    speech_db = float(call(intensity, "Get mean", 0, 0, "dB"))

    hits: list[FillerHit] = []
    for t0, t1 in candidate_gaps(words):
        voiced_frac, gap_db, pitch_std = _gap_features(pitch, intensity, t0, t1)
        if classify_gap(voiced_frac, gap_db, speech_db, pitch_std, t1 - t0,
                        **thresholds):
            hits.append(FillerHit(text="(uh)", start=round(t0, 2),
                                  end=round(t1, 2), source="acoustic"))
    return hits
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_fillers_acoustic.py -v`
Expected: PASS (the 3 gap tests + the fixture smoke test; `detect_acoustic_fillers` returns a list — possibly empty, which is fine for the smoke test).

- [ ] **Step 5: Commit**

```bash
git add engine/fillers/acoustic.py tests/test_fillers_acoustic.py
git commit -m "feat: gap candidates + parselmouth feature extraction for acoustic fillers"
```

---

## Task 4: Merge lexicon + acoustic, wire into orchestrator

**Files:**
- Modify: `engine/fillers/__init__.py`
- Modify: `tests/test_fillers_acoustic.py` (append merge tests)

- [ ] **Step 1: Append failing merge tests** to `tests/test_fillers_acoustic.py`:

```python
from engine.fillers.types import FillerHit as FH
from engine.fillers import merge_hits


def test_merge_dedups_overlap():
    lex = [FH("um", 0.4, 0.7, "lexicon")]
    ac = [FH("(uh)", 0.5, 0.8, "acoustic")]      # overlaps the lexicon hit
    merged = merge_hits(lex, ac)
    assert len(merged) == 1
    assert merged[0].source == "lexicon"          # lexicon preferred


def test_merge_keeps_nonoverlapping():
    lex = [FH("um", 0.4, 0.7, "lexicon")]
    ac = [FH("(uh)", 2.0, 2.4, "acoustic")]
    merged = merge_hits(lex, ac)
    assert len(merged) == 2
    assert [h.source for h in merged] == ["lexicon", "acoustic"]


def test_merge_sorts_by_start():
    lex = [FH("um", 3.0, 3.2, "lexicon")]
    ac = [FH("(uh)", 1.0, 1.3, "acoustic")]
    merged = merge_hits(lex, ac)
    assert [h.start for h in merged] == [1.0, 3.0]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_fillers_acoustic.py -k merge -v`
Expected: FAIL — `cannot import name 'merge_hits'`.

- [ ] **Step 3: Update `engine/fillers/__init__.py`** — add `merge_hits` and wire the acoustic path:

```python
from engine.types import Transcript
from engine.fillers.types import FillerHit, FillerReport
from engine.fillers.lexicon import detect_lexicon_fillers

__all__ = ["FillerHit", "FillerReport", "detect_fillers",
           "detect_lexicon_fillers", "merge_hits"]


def _overlaps(a: FillerHit, b: FillerHit) -> bool:
    return a.start < b.end and b.start < a.end


def merge_hits(lexicon_hits, acoustic_hits):
    """Union; drop an acoustic hit that overlaps a lexicon hit (lexicon wins)."""
    merged = list(lexicon_hits)
    for ah in acoustic_hits:
        if not any(_overlaps(ah, lh) for lh in lexicon_hits):
            merged.append(ah)
    merged.sort(key=lambda h: h.start)
    return merged


def detect_fillers(transcript: Transcript, wav_path: str | None = None,
                   include_like: bool = False, acoustic: bool = True) -> FillerReport:
    lex = detect_lexicon_fillers(transcript, include_like=include_like)
    ac = []
    if wav_path and acoustic:
        from engine.fillers.acoustic import detect_acoustic_fillers
        ac = detect_acoustic_fillers(transcript, wav_path)
    hits = merge_hits(lex, ac)
    minutes = transcript.duration / 60 if transcript.duration > 0 else 1e-9
    return FillerReport(hits=hits, count=len(hits),
                        per_minute=round(len(hits) / minutes, 1))
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all pass. The lexicon-only tests (`detect_fillers(tr)` with no wav) are unaffected because `ac` stays empty and `merge_hits(lex, [])` == sorted `lex`.

- [ ] **Step 5: Commit**

```bash
git add engine/fillers/__init__.py tests/test_fillers_acoustic.py
git commit -m "feat: union lexicon+acoustic fillers in detect_fillers orchestrator"
```

---

## Task 5: Eval harness lift, frontend gap chips, docs

**Files:**
- Modify: `scripts/filler_eval.py`, `web/static/results.js`, `web/static/index.html`, `docs/superpowers/fillers-spike.md`

- [ ] **Step 1: Update `scripts/filler_eval.py`** to compare lexicon-only vs combined:

```python
import json
import os
import sys

from engine.audio import to_wav
from engine.transcribe import transcribe
from engine.fillers.lexicon import detect_lexicon_fillers
from engine.fillers.acoustic import detect_acoustic_fillers
from engine.fillers import merge_hits

SPIKE = os.path.join("tests", "fixtures", "spike")


def main():
    labels = json.load(open(os.path.join(SPIKE, "labels.json")))
    tot_true = tot_lex = tot_comb = 0
    print(f"{'file':16} {'expected':>8} {'lexicon':>8} {'combined':>9}")
    for item in labels:
        wav = to_wav(os.path.join(SPIKE, item["file"]))
        tr = transcribe(wav)
        lex = detect_lexicon_fillers(tr)
        comb = merge_hits(lex, detect_acoustic_fillers(tr, wav))
        tot_true += item["fillers"]
        tot_lex += len(lex)
        tot_comb += len(comb)
        print(f"{item['file']:16} {item['fillers']:>8} {len(lex):>8} {len(comb):>9}")
    lex_ratio = tot_lex / tot_true if tot_true else 0.0
    comb_ratio = tot_comb / tot_true if tot_true else 0.0
    print(f"\nExpected: {tot_true}")
    print(f"Lexicon detected:  {tot_lex}  (detected/expected = {lex_ratio:.2f})")
    print(f"Combined detected: {tot_comb}  (detected/expected = {comb_ratio:.2f})")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the harness** (synthetic clips from the earlier spike still exist locally; if `tests/fixtures/spike/` is empty, regenerate a couple with `say` as in the first spike, or skip with a note):

Run: `.venv/bin/python scripts/filler_eval.py`
Capture the lexicon-vs-combined table and both ratios.

- [ ] **Step 3: Update `web/static/index.html`** — add an acoustic-chip style. Inside the `<style>` block, after the `.filler` rule, add:

```css
    .filler.acoustic { background: #fef3c7; border: 1px dashed #b45309; font-style: italic; }
```

- [ ] **Step 4: Update `web/static/results.js`** — render acoustic hits as gap chips. Replace the whole `annotateTranscript` function with:

```javascript
function annotateTranscript(report) {
  const words = report.transcript.words;
  const hits = report.fillers.hits || [];
  const lexStarts = new Set(
    hits.filter((h) => h.source !== "acoustic").map((h) => h.start)
  );
  const acoustic = hits.filter((h) => h.source === "acoustic");

  function chipsInGap(lo, hi) {
    // acoustic hits whose start falls within (lo, hi]
    return acoustic
      .filter((h) => h.start >= lo - 0.001 && h.start < hi)
      .map((h) => `<span class="filler acoustic">${h.text}</span>`);
  }

  const parts = [];
  // leading acoustic fillers (before the first word)
  const firstStart = words.length ? words[0].start : Infinity;
  parts.push(...chipsInGap(-1, firstStart));

  words.forEach((w, i) => {
    if (lexStarts.has(w.start)) {
      parts.push(`<span class="filler">${w.text}</span>`);
    } else {
      parts.push(w.text);
    }
    const nextStart = i + 1 < words.length ? words[i + 1].start : Infinity;
    // acoustic chips that sit in the gap after this word
    parts.push(...chipsInGap(w.end, nextStart));
    // existing pause marker
    if (i + 1 < words.length) {
      const gap = words[i + 1].start - w.end;
      if (gap >= 0.5) {
        parts.push(`<span class="pause"> …(${gap.toFixed(1)}s)… </span>`);
      }
    }
  });
  return parts.join(" ");
}
```

(The rest of `results.js` — `window.renderResults`, the Coach card, etc. — is unchanged. The Delivery card's filler count already comes from `report.fillers.count`, which now includes acoustic hits.)

- [ ] **Step 5: Headless check the frontend still serves**

Run (kill the server after):
```bash
.venv/bin/uvicorn web.app:app --port 8013 &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8013/results.js
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8013/
pkill -f "uvicorn web.app:app"
```
Expected: both `200`. Then `.venv/bin/pytest -q` → still all green (no Python tests added here).

- [ ] **Step 6: Update `docs/superpowers/fillers-spike.md`** — append an "Iteration 2: acoustic gap detector" section with:
  - The lexicon-vs-combined table and both ratios from Step 2.
  - The thresholds used (from `classify_gap` defaults; note any you tuned).
  - The honest caveat that synthetic clips overstate accuracy and that the natural-clip measurement (record into `tests/fixtures/spike/`, re-run the harness) is the real test.
  - The go/no-go for approach B (trained model): if natural-clip combined recall is still well below ~0.7, escalate — gap-based detection cannot catch fillers Whisper substituted into a real word.

- [ ] **Step 7: Commit**

```bash
git add scripts/filler_eval.py web/static/results.js web/static/index.html docs/superpowers/fillers-spike.md
git commit -m "feat: acoustic filler eval lift + frontend gap chips + spike findings"
```

---

## Definition of done

- [ ] `.venv/bin/pytest -q` fully green (≈53 tests: 38 prior + 15 new — 1 source, 7 classify_gap, 3 candidate_gaps, 1 smoke, 3 merge).
- [ ] `detect_fillers(transcript)` with no wav is byte-for-byte the old lexicon behavior (backward compatible); with a wav it adds acoustic hits.
- [ ] `engine/fillers/` is a clean package; `engine/` still has zero imports from `web/`.
- [ ] The eval harness prints lexicon-vs-combined and the lift is recorded in `fillers-spike.md`, with the approach-B go/no-go stated.
- [ ] Frontend renders acoustic fillers as gap chips (distinct from lexicon word-highlights) and the Delivery filler count reflects the union.
- [ ] Manual (Dan): record natural clips into `tests/fixtures/spike/`, re-run `scripts/filler_eval.py` for the real-world combined recall.
