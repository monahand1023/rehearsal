from engine.coach import build_summary_prompt, compose_spoken_summary


def _report():
    return {
        "delivery": {"words_per_minute": 165.0, "chars_per_minute": 320.0,
                     "long_pause_count": 2, "time_to_first_word": 0.5},
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


def test_prompt_japanese_uses_characters_per_minute():
    # JP rate is reported in characters/min, not the meaningless words/min.
    p = build_summary_prompt(_report(), language="ja")
    assert "320.0 characters per minute" in p
    assert "165.0 words per minute" not in p


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


def test_japanese_mode_uses_kid_tuned_prompt_and_persona():
    # The Japanese track is a young learner: one strength + exactly one next step.
    from engine.coach import build_summary_prompt, compose_spoken_summary, COACH_SYSTEM_KID
    p = build_summary_prompt(_report(), language="ja", mode="japanese")
    assert "young learner" in p
    assert "ONE" in p  # exactly one suggestion

    class Cap:
        def __init__(self): self.kw = None
        def chat(self, **kw): self.kw = kw; return {"message": {"content": "いいね！"}}
    cap = Cap()
    compose_spoken_summary(_report(), language="ja", mode="japanese", client=cap)
    assert cap.kw["messages"][0]["content"] == COACH_SYSTEM_KID


def test_interview_mode_keeps_candid_persona():
    from engine.coach import compose_spoken_summary, COACH_SYSTEM

    class Cap:
        def __init__(self): self.kw = None
        def chat(self, **kw): self.kw = kw; return {"message": {"content": "ok"}}
    cap = Cap()
    compose_spoken_summary(_report(), language="en", mode="interview", client=cap)
    assert cap.kw["messages"][0]["content"] == COACH_SYSTEM


def test_prompt_mentions_english_words_when_present():
    # When the proficiency rater flags English used instead of Japanese, the spoken
    # coach should know about it so it can call it out.
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 120.0, "long_pause_count": 1,
                     "time_to_first_word": 0.3},
        "fillers": {"count": 2, "per_minute": 3.0},
        "prosody": None,
        "content": {"kind": "proficiency", "level": "Novice-High", "functions": "",
                    "english_words": ['"weekend" → 週末', '"fun" → 楽しい']},
    }
    p = build_summary_prompt(report, language="ja")
    assert "週末" in p


def test_lite_japanese_omits_unreliable_pauses():
    # Cloud-lite JP has no reliable pause signal — don't feed long_pause_count to the coach.
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 0.0, "chars_per_minute": 300.0,
                     "long_pause_count": 0, "time_to_first_word": 0.0},
        "fillers": {"count": 1, "per_minute": 2.0}, "prosody": None, "content": None,
    }
    assert "Long pauses" not in build_summary_prompt(report, language="ja", mode="japanese")


def test_native_japanese_keeps_pauses():
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 0.0, "chars_per_minute": 300.0,
                     "long_pause_count": 2, "time_to_first_word": 0.3},
        "fillers": {"count": 1, "per_minute": 2.0},
        "prosody": {"monotone": False}, "content": None,
    }
    assert "Long pauses" in build_summary_prompt(report, language="ja", mode="japanese")


def test_prompt_handles_missing_prosody():
    # Cloud "lite" mode has no prosody — the coach prompt must not crash.
    from engine.coach import build_summary_prompt
    report = {
        "delivery": {"words_per_minute": 150.0, "chars_per_minute": 300.0,
                     "long_pause_count": 0, "time_to_first_word": 0.2},
        "fillers": {"count": 0, "per_minute": 0.0},
        "prosody": None,
        "content": None,
    }
    out = build_summary_prompt(report, language="ja")
    assert "300" in out  # delivery still summarized (JP rate in characters/min)
