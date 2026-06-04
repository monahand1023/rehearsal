"""Opt-in END-TO-END test of the deployed cloud pipeline against generated audio.

Runs the REAL cloud stack (OpenAI Whisper + gpt-4o, lite mode) on the feature clips in
tests/fixtures/generated/ and asserts the behaviors we built this round — English-word
flagging, STAMP level ordering, thin-answer flooring, filler detection, interview STAR
detection. This is what catches regressions like the per-character tokenization / language
/ clarity bugs we found by hand.

Skipped by default (it makes API calls). Enable with:
  REHEARSAL_RUN_E2E=1 OPENAI_API_KEY=sk-... pytest tests/test_e2e_cloud.py -v
"""
import json
import os
from pathlib import Path

import pytest

GEN = Path(__file__).parent / "fixtures" / "generated"
MANIFEST = {e["id"]: e for e in json.loads((GEN / "manifest.json").read_text())}

pytestmark = pytest.mark.skipif(
    os.environ.get("REHEARSAL_RUN_E2E") != "1",
    reason="opt-in: set REHEARSAL_RUN_E2E=1 (+OPENAI_API_KEY) for the live cloud E2E test",
)


@pytest.fixture(scope="module", autouse=True)
def _cloud_env():
    keys = ("REHEARSAL_LLM_PROVIDER", "REHEARSAL_TRANSCRIBE_PROVIDER", "REHEARSAL_AUDIO_NATIVE")
    old = {k: os.environ.get(k) for k in keys}
    os.environ.update({"REHEARSAL_LLM_PROVIDER": "openai",
                       "REHEARSAL_TRANSCRIBE_PROVIDER": "openai",
                       "REHEARSAL_AUDIO_NATIVE": "false"})
    yield
    for k, v in old.items():
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


_cache = {}


def analyze(clip_id):
    """Run the full cloud pipeline on a clip once (cached to keep API spend down)."""
    if clip_id not in _cache:
        from engine.report import analyze_answer
        e = MANIFEST[clip_id]
        _cache[clip_id] = analyze_answer(str(GEN / (clip_id + ".mp3")), e.get("question", ""),
                                         language=e["language"], mode=e["mode"],
                                         category=e.get("category", ""))
    return _cache[clip_id]


def test_japanese_pipeline_shape():
    r = analyze("ja_simple")
    assert r["transcript"]["text"]                       # transcribed something
    assert r["delivery"]["words_per_minute"] == 0.0      # JP wpm zeroed (per-char tokenization)
    assert r["delivery"]["chars_per_minute"] > 0         # real rate reported as cpm
    assert r["clarity"] is None                          # no fake 100% — cloud has no confidence
    assert r["content"]["kind"] == "proficiency"
    assert r["spoken_summary"]


def test_english_words_flagged_on_mixed_answer():
    # "土曜日に friends と park に行きました。とても fun でした。" → flag the English.
    r = analyze("ja_english_mix")
    assert r["content"]["english_words"], "expected English words to be flagged"


def test_connected_scores_higher_than_simple():
    simple = analyze("ja_simple")["content"]["stamp_level"]
    connected = analyze("ja_connected")["content"]["stamp_level"]
    assert connected > simple, f"connected ({connected}) should outscore simple ({simple})"
    assert simple <= MANIFEST["ja_simple"]["expect"]["stamp_max"]
    assert connected >= MANIFEST["ja_connected"]["expect"]["stamp_min"]


def test_thin_answer_floored_not_fabricated():
    r = analyze("ja_thin")
    c = r["content"]
    assert c["stamp_level"] <= MANIFEST["ja_thin"]["expect"]["stamp_max"]


def test_fillers_detected_on_filler_clip():
    r = analyze("ja_fillers")
    assert r["fillers"]["count"] >= MANIFEST["ja_fillers"]["expect"]["fillers_min"]


def test_interview_star_answer_recognized():
    c = analyze("en_story")["content"]
    assert c["kind"] == "interview"
    assert c["answered_question"] is True
    present = sum(1 for v in c["star_present"].values() if v)
    assert present >= MANIFEST["en_story"]["expect"]["star_min"]


def test_interview_nonanswer_flagged():
    c = analyze("en_nonanswer")["content"]
    assert c["answered_question"] is False
