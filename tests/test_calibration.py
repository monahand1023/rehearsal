"""Opt-in calibration test for the STAMP rater.

Runs the REAL model against a small gold set and asserts within-one-level agreement (the
standard bar for rater calibration). Skipped by default because it costs API calls — enable
with:  REHEARSAL_RUN_CALIBRATION=1 OPENAI_API_KEY=sk-... pytest tests/test_calibration.py

Re-run whenever the proficiency prompt or model changes — it's the regression guard against
silently miscalibrating a kid's scores.
"""
import json
import os
from pathlib import Path

import pytest

GOLD = json.loads((Path(__file__).parent / "fixtures" / "proficiency_gold.json").read_text())["cases"]

pytestmark = pytest.mark.skipif(
    os.environ.get("REHEARSAL_RUN_CALIBRATION") != "1",
    reason="opt-in: set REHEARSAL_RUN_CALIBRATION=1 (+OPENAI_API_KEY) to run live calibration",
)


@pytest.mark.parametrize("case", GOLD, ids=[c["id"] for c in GOLD])
def test_calibration_within_one_level(case):
    from engine.llm_openai import OpenAIChatClient
    from engine.proficiency import analyze_proficiency
    fb = analyze_proficiency(case["question"], case["transcript"], language="ja",
                             model="gpt-4o", client=OpenAIChatClient())
    delta = abs(fb.stamp_level - case["stamp_level"])
    assert delta <= 1, (f"{case['id']}: predicted STAMP {fb.stamp_level} ({fb.level}), "
                        f"expected ~{case['stamp_level']} (off by {delta})")
