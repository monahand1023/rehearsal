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
