"""Opt-in calibration test for the interview (STAR) rubric.

Runs your configured model against a small gold set: asserts answered_question exactly, STAR-
part detection within one, and any signal expectations. Skipped by default — enable with
REHEARSAL_RUN_CALIBRATION=1. Runs against whatever REHEARSAL_LLM_PROVIDER points at:
  REHEARSAL_RUN_CALIBRATION=1 pytest tests/test_interview_calibration.py                 # local Ollama
  REHEARSAL_RUN_CALIBRATION=1 REHEARSAL_LLM_PROVIDER=openai OPENAI_API_KEY=sk-... pytest ...  # gpt-4o
"""
import json
import os
from pathlib import Path

import pytest

GOLD = json.loads((Path(__file__).parent / "fixtures" / "interview_gold.json").read_text())["cases"]

pytestmark = pytest.mark.skipif(
    os.environ.get("REHEARSAL_RUN_CALIBRATION") != "1",
    reason="opt-in: set REHEARSAL_RUN_CALIBRATION=1 to run live calibration",
)


@pytest.mark.parametrize("case", GOLD, ids=[c["id"] for c in GOLD])
def test_interview_calibration(case):
    from engine.llm import get_client, default_model
    from engine.content import analyze_content
    fb = analyze_content(case["question"], case["answer"], model=default_model(),
                         client=get_client(), category=case.get("category", ""))
    assert fb.answered_question == case["answered"], \
        f"{case['id']}: answered_question {fb.answered_question}, expected {case['answered']}"
    detected = sum(1 for v in fb.star_present.values() if v)
    expected = len(case["star"])
    assert abs(detected - expected) <= 1, \
        f"{case['id']}: detected {detected} STAR parts, expected ~{expected}"
    for sig, want in case.get("signals_expect", {}).items():
        assert fb.signals.get(sig) == want, \
            f"{case['id']}: signal {sig}={fb.signals.get(sig)}, expected {want}"
