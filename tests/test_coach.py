from engine.coach import build_summary_prompt, compose_spoken_summary


def _report():
    return {
        "delivery": {"words_per_minute": 165.0, "long_pause_count": 2,
                     "time_to_first_word": 0.5},
        "fillers": {"count": 4, "per_minute": 6.0},
        "prosody": {"monotone": True},
        "content": {"answered_question": True, "star_missing": ["result"]},
    }


def test_prompt_includes_metrics_and_language():
    p = build_summary_prompt(_report(), language="en")
    assert "165" in p
    assert "English" in p


def test_prompt_japanese_language_name():
    p = build_summary_prompt(_report(), language="ja")
    assert "Japanese" in p


def test_prompt_handles_missing_content():
    report = _report()
    report["content"] = None
    p = build_summary_prompt(report, language="en")
    assert "165" in p  # still summarizes delivery without content


def test_prompt_includes_clarity_when_present():
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 150.0, "long_pause_count": 0,
                     "time_to_first_word": 0.2},
        "fillers": {"count": 0, "per_minute": 0.0},
        "prosody": {"monotone": False},
        "content": None,
        "clarity": {"mean_confidence": 0.82, "low_confidence_words": []},
    }
    p = build_summary_prompt(report, language="en")
    assert "0.82" in p


class FakeClient:
    def __init__(self, text):
        self.text = text
        self.kw = None

    def chat(self, **kw):
        self.kw = kw
        return {"message": {"content": self.text}}


def test_compose_strips_and_returns_text():
    client = FakeClient("  You spoke at a nice pace. Try a breath next time.  ")
    out = compose_spoken_summary(_report(), language="en", client=client)
    assert out == "You spoke at a nice pace. Try a breath next time."
    # prose generation, not JSON mode
    assert "format" not in client.kw


def test_prompt_uses_proficiency_branch():
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 120.0, "long_pause_count": 1,
                     "time_to_first_word": 0.3},
        "fillers": {"count": 2, "per_minute": 3.0},
        "prosody": {"monotone": False},
        "content": {"kind": "proficiency", "level": "Intermediate-Mid",
                    "functions": "described the routine and gave reasons"},
    }
    p = build_summary_prompt(report, language="ja")
    assert "Intermediate-Mid" in p


def test_prompt_handles_missing_prosody():
    # Cloud "lite" mode has no prosody — the coach prompt must not crash.
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 150.0, "long_pause_count": 0,
                     "time_to_first_word": 0.2},
        "fillers": {"count": 0, "per_minute": 0.0},
        "prosody": None,
        "content": None,
    }
    out = build_summary_prompt(report, language="ja")
    assert "150" in out
