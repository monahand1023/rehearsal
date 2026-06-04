"""Opt-in calibration test for the interview (STAR) rubric.

Runs the REAL model against a small gold set: asserts answered_question exactly and STAR-part
detection within one. Skipped by default (costs API calls) — enable with:
  REHEARSAL_RUN_CALIBRATION=1 OPENAI_API_KEY=sk-... pytest tests/test_interview_calibration.py

Re-run whenever the interview prompt or model changes.
"""
import json
import os
from pathlib import Path

import pytest

GOLD = json.loads((Path(__file__).parent / "fixtures" / "interview_gold.json").read_text())["cases"]

pytestmark = pytest.mark.skipif(
    os.environ.get("REHEARSAL_RUN_CALIBRATION") != "1",
    reason="opt-in: set REHEARSAL_RUN_CALIBRATION=1 (+OPENAI_API_KEY) to run live calibration",
)


@pytest.mark.parametrize("case", GOLD, ids=[c["id"] for c in GOLD])
def test_interview_calibration(case):
    from engine.llm_openai import OpenAIChatClient
    from engine.content import analyze_content
    fb = analyze_content(case["question"], case["answer"], model="gpt-4o",
                         client=OpenAIChatClient(), category=case.get("category", ""))
    assert fb.answered_question == case["answered"], \
        f"{case['id']}: answered_question {fb.answered_question}, expected {case['answered']}"
    detected = sum(1 for v in fb.star_present.values() if v)
    expected = len(case["star"])
    assert abs(detected - expected) <= 1, \
        f"{case['id']}: detected {detected} STAR parts, expected ~{expected}"
    for sig, want in case.get("signals_expect", {}).items():
        assert fb.signals.get(sig) == want, \
            f"{case['id']}: signal {sig}={fb.signals.get(sig)}, expected {want}"
