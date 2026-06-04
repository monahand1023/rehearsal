"""Opt-in calibration test for the STAMP rater.

Runs your configured model against a small gold set and asserts within-one-level agreement
(the standard bar for rater calibration). Skipped by default — enable with REHEARSAL_RUN_
CALIBRATION=1. It runs against whatever REHEARSAL_LLM_PROVIDER points at, so you can validate
EITHER deployment:

  # local model (Ollama) — the default; a weaker model may not pass, which tells you to use
  # a more capable one (REHEARSAL_LLM_MODEL=...):
  REHEARSAL_RUN_CALIBRATION=1 pytest tests/test_calibration.py
  # cloud (gpt-4o):
  REHEARSAL_RUN_CALIBRATION=1 REHEARSAL_LLM_PROVIDER=openai OPENAI_API_KEY=sk-... pytest tests/test_calibration.py

Re-run whenever the prompt or model changes — the regression guard against miscalibrated scores.
"""
import json
import os
from pathlib import Path

import pytest

GOLD = json.loads((Path(__file__).parent / "fixtures" / "proficiency_gold.json").read_text())["cases"]

pytestmark = pytest.mark.skipif(
    os.environ.get("REHEARSAL_RUN_CALIBRATION") != "1",
    reason="opt-in: set REHEARSAL_RUN_CALIBRATION=1 to run live calibration",
)


@pytest.mark.parametrize("case", GOLD, ids=[c["id"] for c in GOLD])
def test_calibration_within_one_level(case):
    from engine.llm import get_client, default_model
    from engine.proficiency import analyze_proficiency
    fb = analyze_proficiency(case["question"], case["transcript"], language="ja",
                             model=default_model(), client=get_client())
    delta = abs(fb.stamp_level - case["stamp_level"])
    assert delta <= 1, (f"{case['id']}: predicted STAMP {fb.stamp_level} ({fb.level}), "
                        f"expected ~{case['stamp_level']} (off by {delta})")
