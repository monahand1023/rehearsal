# Audio Integration Testing + Coverage Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add end-to-end integration testing that runs the real `analyze_answer` orchestrator on known-content ElevenLabs audio fixtures with tolerant assertions, plus a coverage audit (pytest-cov) and targeted unit gap-fills.

**Architecture:** A committed ground-truth manifest + a generation script (ElevenLabs) produce labeled `.mp3` clips under `tests/fixtures/generated/`. Integration tests run the real engine on those clips and assert tolerant, ground-truth-based properties (keyword presence, filler-count ranges, plausible WPM/clarity, complete report structure). The audio tests use `run_content=False` (no Ollama); one Ollama-gated test exercises the full pipeline incl. the LLM + coach. pytest-cov measures coverage and drives the unit gap-fills.

**Tech Stack:** Python 3.11+, pytest, pytest-cov (new), the existing ElevenLabs provider, faster-whisper, ffmpeg. No engine code changes.

---

## File structure

```
requirements.txt                        # MODIFY: + pytest-cov
pyproject.toml                          # MODIFY: + [tool.coverage.run]
scripts/gen_test_audio.py               # NEW
tests/fixtures/generated/manifest.json  # NEW (committed ground truth)
tests/fixtures/generated/<id>.mp3       # NEW (generated, committed; Task 4)
tests/test_gen_manifest.py              # NEW (manifest validity)
tests/test_integration_audio.py         # NEW (e2e + Ollama-gated)
tests/test_audio.py                     # MODIFY: default-dst test
tests/test_fillers_acoustic.py          # MODIFY: acoustic on/off branch
tests/test_content.py                   # MODIFY: missing star_present
tests/test_web.py                       # MODIFY: /api/speak 502; /api/questions JP
```

**Pre-req:** the two-mode app is built; 73 tests pass. `.mp3` is NOT gitignored, so generated clips commit cleanly; `.wav` IS gitignored, so converted WAVs (written to tmp dirs in tests) never get committed.

---

## Task 1: pytest-cov setup + coverage baseline

**Files:** Modify `requirements.txt`, `pyproject.toml`.

- [ ] **Step 1: Add `pytest-cov` to `requirements.txt`** (append a line):
```
pytest-cov
```

- [ ] **Step 2: Add coverage config to `pyproject.toml`** (append):
```toml
[tool.coverage.run]
source = ["engine", "web"]
omit = ["tests/*"]
```

- [ ] **Step 3: Install it**

Run: `.venv/bin/pip install pytest-cov`
Expected: installs without error.

- [ ] **Step 4: Run the coverage baseline**

Run: `.venv/bin/pytest --cov --cov-report=term-missing -q`
Expected: all 73 tests pass and a coverage table prints. Note the total % and the lowest-covered files (you'll use this to confirm Task 2's targets are the right ones).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pyproject.toml
git commit -m "test: add pytest-cov coverage tooling"
```

---

## Task 2: Fill unit-test gaps

**Files:** Modify `tests/test_audio.py`, `tests/test_fillers_acoustic.py`, `tests/test_content.py`, `tests/test_web.py`.

- [ ] **Step 1: `to_wav` default destination** — append to `tests/test_audio.py`:
```python
def test_to_wav_default_dst(tmp_path):
    import os, subprocess
    src = tmp_path / "in.m4a"
    subprocess.run(["ffmpeg", "-y", "-i", FIXTURE, str(src)],
                   check=True, capture_output=True)
    out = to_wav(str(src))  # no dst_path -> <src>.converted.wav
    assert out.endswith(".converted.wav")
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
```

- [ ] **Step 2: `detect_fillers` acoustic on/off branch** — append to `tests/test_fillers_acoustic.py`:
```python
def test_detect_fillers_acoustic_off_skips_acoustic(make_transcript, monkeypatch):
    from engine.fillers import detect_fillers
    calls = {"n": 0}

    def spy(tr, wav, **kw):
        calls["n"] += 1
        return []

    monkeypatch.setattr("engine.fillers.acoustic.detect_acoustic_fillers", spy)
    tr = make_transcript([("um", 0.0, 0.3)], duration=2.0)
    detect_fillers(tr, wav_path="x.wav", acoustic=False)
    assert calls["n"] == 0


def test_detect_fillers_acoustic_on_merges(make_transcript, monkeypatch):
    from engine.fillers import detect_fillers
    from engine.fillers.types import FillerHit
    monkeypatch.setattr("engine.fillers.acoustic.detect_acoustic_fillers",
                        lambda tr, wav: [FillerHit("(uh)", 5.0, 5.3, "acoustic")])
    tr = make_transcript([("um", 0.0, 0.3)], duration=10.0)
    r = detect_fillers(tr, wav_path="x.wav")  # acoustic defaults True
    assert sorted(h.source for h in r.hits) == ["acoustic", "lexicon"]
```

- [ ] **Step 3: `parse_response` with missing `star_present`** — append to `tests/test_content.py`:
```python
def test_parse_response_missing_star_present():
    raw = json.dumps({"answered_question": True})  # no star_present / lists
    fb = parse_response(raw)
    assert fb.star_missing == ["situation", "task", "action", "result"]
    assert fb.coaching_notes == []
    assert fb.kind == "interview"
```

- [ ] **Step 4: `/api/speak` 502 + JP questions** — append to `tests/test_web.py`:
```python
def test_speak_provider_error_returns_502(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    import engine.tts.elevenlabs as el
    from engine.tts.base import TTSError

    def boom(self, text, language="en"):
        raise TTSError("bad voice")

    monkeypatch.setattr(el.ElevenLabsProvider, "synthesize", boom)
    client = TestClient(appmod.app)
    resp = client.post("/api/speak", data={"text": "hi", "language": "en"})
    assert resp.status_code == 502


def test_questions_japanese_track():
    client = TestClient(appmod.app)
    body = client.get("/api/questions?track=language_jp").json()
    assert body["language"] == "ja"
    assert len(body["questions"]) >= 1
```

- [ ] **Step 5: Run + re-check coverage**

Run: `.venv/bin/pytest -q` (expect all green, 73 + 6 = 79).
Then `.venv/bin/pytest --cov --cov-report=term-missing -q` and confirm the targeted files moved up (audio.py, fillers, content.py, web/app.py).

- [ ] **Step 6: Commit**

```bash
git add tests/test_audio.py tests/test_fillers_acoustic.py tests/test_content.py tests/test_web.py
git commit -m "test: fill unit-coverage gaps (to_wav default, acoustic branch, parse edge, speak 502)"
```

---

## Task 3: Ground-truth manifest + ElevenLabs generation script

**Files:** Create `tests/fixtures/generated/manifest.json`, `scripts/gen_test_audio.py`, `tests/test_gen_manifest.py`.

- [ ] **Step 1: Create `tests/fixtures/generated/manifest.json`** (committed ground truth):
```json
[
  {"id": "en_clean", "language": "en", "mode": "interview",
   "text": "I led a team of five engineers to deliver the new platform on time and under budget.",
   "expected_fillers": 0, "keywords": ["team", "platform"]},
  {"id": "en_fillers", "language": "en", "mode": "interview",
   "text": "So, um, in my last role I, uh, led a project, and, you know, we shipped a new feature.",
   "expected_fillers": 3, "keywords": ["project", "feature"]},
  {"id": "en_story", "language": "en", "mode": "interview",
   "text": "When our biggest customer threatened to leave, I organized a cross team response, rebuilt the integration, and we retained the account within two weeks.",
   "expected_fillers": 0, "keywords": ["customer", "integration"]},
  {"id": "ja_clean", "language": "ja", "mode": "japanese",
   "text": "私は毎日日本語を勉強しています。趣味は読書と音楽です。",
   "expected_fillers": 0, "keywords": ["日本語", "趣味"]},
  {"id": "ja_fillers", "language": "ja", "mode": "japanese",
   "text": "えーと、週末は友達と買い物に行きました。あのー、とても楽しかったです。",
   "expected_fillers": 2, "keywords": ["週末", "友達"]}
]
```

- [ ] **Step 2: Create `scripts/gen_test_audio.py`**:
```python
import json
import os
import sys

from engine.tts.elevenlabs import ElevenLabsProvider

GEN_DIR = os.path.join("tests", "fixtures", "generated")

# Default to a stock ElevenLabs voice so only ELEVENLABS_API_KEY is required.
# Override with ELEVENLABS_VOICE_EN / ELEVENLABS_VOICE_JA if you prefer other voices.
os.environ.setdefault("ELEVENLABS_VOICE_EN", "21m00Tcm4TlvDq8ikWAM")  # Rachel (stock)
os.environ.setdefault("ELEVENLABS_VOICE_JA", "21m00Tcm4TlvDq8ikWAM")  # multilingual_v2 handles JP


def main():
    manifest = json.load(open(os.path.join(GEN_DIR, "manifest.json")))
    provider = ElevenLabsProvider()
    made = 0
    for entry in manifest:
        out = os.path.join(GEN_DIR, entry["id"] + ".mp3")
        if os.path.exists(out):
            print("skip (exists):", out)
            continue
        audio = provider.synthesize(entry["text"], entry["language"])
        with open(out, "wb") as f:
            f.write(audio)
        made += 1
        print(f"generated: {out} ({len(audio)} bytes)")
    print(f"\nDone. {made} new clip(s).")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Create `tests/test_gen_manifest.py`** (validates the manifest without generating):
```python
import json
import os

MANIFEST = os.path.join(os.path.dirname(__file__), "fixtures", "generated", "manifest.json")
REQUIRED = {"id", "language", "mode", "text", "expected_fillers", "keywords"}


def test_manifest_valid():
    entries = json.load(open(MANIFEST))
    assert len(entries) >= 3
    ids = set()
    for e in entries:
        assert REQUIRED <= set(e), f"missing keys in {e.get('id')}"
        assert e["language"] in ("en", "ja")
        assert isinstance(e["keywords"], list) and e["keywords"]
        ids.add(e["id"])
    assert len(ids) == len(entries)  # ids unique
```

- [ ] **Step 4: Validate + run**

Run: `.venv/bin/python -c "import json; print(len(json.load(open('tests/fixtures/generated/manifest.json'))), 'entries')"` (expect `5 entries`).
Then `.venv/bin/pytest tests/test_gen_manifest.py -v` (expect PASS) and `.venv/bin/pytest -q` (all green).

- [ ] **Step 5: Commit** (script + manifest + manifest test — no audio yet):
```bash
git add scripts/gen_test_audio.py tests/fixtures/generated/manifest.json tests/test_gen_manifest.py
git commit -m "test: ElevenLabs audio fixture manifest + generation script"
```

---

## Task 4: Generate + commit the audio fixtures (KEY-ASSISTED — controller handles)

> This task needs `ELEVENLABS_API_KEY`. It is performed by the controller together with Dan (a subagent cannot prompt for the key). Do NOT dispatch a subagent for this task.

- [ ] **Step 1: Dan sets the key and runs generation** (one shell invocation so the env var applies):
```
!ELEVENLABS_API_KEY=<your-key> .venv/bin/python scripts/gen_test_audio.py
```
Expected output: 5 `generated: tests/fixtures/generated/<id>.mp3` lines.

- [ ] **Step 2: Verify the clips exist and are non-empty**

Run: `ls -la tests/fixtures/generated/*.mp3` — expect 5 files, each > 0 bytes.

- [ ] **Step 3: Commit the generated clips** (they are synthetic and `.mp3` is not gitignored):
```bash
git add tests/fixtures/generated/*.mp3
git commit -m "test: committed ElevenLabs audio fixtures"
```

---

## Task 5: Audio end-to-end integration tests

**Files:** Create `tests/test_integration_audio.py`.

- [ ] **Step 1: Create `tests/test_integration_audio.py`**:
```python
import json
import os
import shutil

import pytest

from engine.report import analyze_answer

GEN_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "generated")
MANIFEST = os.path.join(GEN_DIR, "manifest.json")


def _entries():
    if not os.path.exists(MANIFEST):
        return []
    return json.load(open(MANIFEST))


def _clip(entry):
    return os.path.join(GEN_DIR, entry["id"] + ".mp3")


def _has_kana_kanji(s):
    return any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in s)


_ENTRIES = _entries()


@pytest.mark.parametrize("entry", _ENTRIES, ids=[e["id"] for e in _ENTRIES])
def test_engine_on_generated_clip(entry, tmp_path):
    clip = _clip(entry)
    if not os.path.exists(clip):
        pytest.skip(f"clip not generated: {entry['id']} (run scripts/gen_test_audio.py)")
    # Copy into tmp so the converted .wav lands in tmp, not the fixtures dir.
    local = tmp_path / (entry["id"] + ".mp3")
    shutil.copy(clip, local)

    report = analyze_answer(str(local), "", language=entry["language"],
                            mode=entry["mode"], run_content=False)

    text = report["transcript"]["text"].lower()
    assert sum(kw.lower() in text for kw in entry["keywords"]) >= 1, \
        f"no keyword found in: {report['transcript']['text']!r}"
    if entry["language"] == "ja":
        assert _has_kana_kanji(report["transcript"]["text"])

    # Filler detection: hard-assert only the reliable positive case (English with
    # fillers). Clean-clip upper bounds and JP filler detection are FP-sensitive /
    # experimental on natural TTS audio, so just assert the pipeline produced a count.
    count = report["fillers"]["count"]
    assert isinstance(count, int) and count >= 0
    if entry["language"] == "en" and entry["expected_fillers"] > 0:
        assert count >= 1, "expected to detect at least one filler in a fillered English clip"

    # WPM: English in a plausible band; Japanese reads high (short Whisper "words" —
    # a known rough edge), so only assert it's positive there.
    wpm = report["delivery"]["words_per_minute"]
    if entry["language"] == "en":
        assert 40 <= wpm <= 320
    else:
        assert wpm > 0
    assert 0 < report["clarity"]["mean_confidence"] <= 1

    for k in ("transcript", "delivery", "fillers", "prosody", "clarity"):
        assert k in report
    assert report["content"] is None
    assert report["spoken_summary"] is None
```

- [ ] **Step 2: Run the integration tests**

Run: `.venv/bin/pytest tests/test_integration_audio.py -v`
Expected (with Task 4 done): one passing test per manifest entry (5). If the clips were not generated, the tests SKIP cleanly — in that case note it and proceed (the harness is correct; generation is the gate). The first English clip downloads nothing new (base.en cached); Japanese clips use the cached `small` model.

- [ ] **Step 3: Full suite + commit**

Run: `.venv/bin/pytest -q` (all green; integration tests pass if clips exist, else skip).
```bash
git add tests/test_integration_audio.py
git commit -m "test: end-to-end audio integration tests over generated fixtures"
```

---

## Task 6: Ollama-gated full-orchestrator e2e

**Files:** Modify `tests/test_integration_audio.py` (append).

- [ ] **Step 1: Append the Ollama-gated tests** to `tests/test_integration_audio.py`:
```python
def _ollama_up():
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def _find(entry_id):
    for e in _ENTRIES:
        if e["id"] == entry_id:
            return e
    return None


def _run_full(entry, question, mode, language, tmp_path):
    clip = _clip(entry)
    if not os.path.exists(clip):
        pytest.skip(f"clip not generated: {entry['id']}")
    local = tmp_path / (entry["id"] + ".mp3")
    shutil.copy(clip, local)
    return analyze_answer(str(local), question, language=language, mode=mode,
                          run_content=True)


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not running")
def test_full_analyze_interview_with_ollama(tmp_path):
    entry = _find("en_story") or (_ENTRIES[0] if _ENTRIES else None)
    if not entry:
        pytest.skip("no manifest entries")
    report = _run_full(entry, "Tell me about a challenge you faced.",
                       "interview", "en", tmp_path)
    assert report["content"] is not None
    assert report["content"]["kind"] == "interview"
    assert report["spoken_summary"]


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not running")
def test_full_analyze_japanese_with_ollama(tmp_path):
    entry = _find("ja_clean") or _find("ja_fillers")
    if not entry:
        pytest.skip("no JP manifest entries")
    report = _run_full(entry, "あなたの趣味について話してください。",
                       "japanese", "ja", tmp_path)
    assert report["content"] is not None
    assert report["content"]["kind"] == "proficiency"
    assert report["spoken_summary"]
```

- [ ] **Step 2: Run**

Run: `.venv/bin/pytest tests/test_integration_audio.py -v`
Expected: the two `*_with_ollama` tests PASS if Ollama is running with `llama3.1` and the clips exist; otherwise they SKIP cleanly. Either outcome is acceptable for a green suite.

- [ ] **Step 3: Full suite + commit**

Run: `.venv/bin/pytest -q` (all green).
```bash
git add tests/test_integration_audio.py
git commit -m "test: Ollama-gated full-orchestrator e2e (interview + proficiency)"
```

---

## Definition of done

- [ ] `.venv/bin/pytest -q` fully green. With fixtures generated + Ollama running, the new
  integration + e2e tests pass; without them they SKIP cleanly (never fail).
- [ ] `pytest --cov` reports coverage for `engine` + `web`; the Task 2 gap-fills raised the
  previously-thin spots (audio default path, acoustic branch, parse edge, speak 502).
- [ ] The orchestrator `analyze_answer` is now genuinely exercised end-to-end (Task 5 with
  `run_content=False`; Task 6 with the full LLM + coach), not just monkeypatched.
- [ ] Generated `.mp3` fixtures are committed; converted `.wav` files are written only to tmp
  dirs and never committed.
- [ ] Assertions are tolerant (keywords / ranges), so TTS+ASR variance doesn't cause flakes.
- [ ] `engine/` still has zero imports from `web/`; no engine behavior changed (tests only).
