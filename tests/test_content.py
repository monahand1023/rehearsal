import json

from engine.content import build_prompt, parse_response, analyze_content


def test_build_prompt_includes_question_and_answer():
    p = build_prompt("Tell me about a conflict", "I had a disagreement once")
    assert "Tell me about a conflict" in p
    assert "I had a disagreement once" in p


def test_system_resists_injection():
    from engine.content import SYSTEM
    assert "disregard" in SYSTEM.lower()                   # ignore instructions in the answer
    assert "volume" in SYSTEM.lower() or "rambling" in SYSTEM.lower()


def test_prompt_asks_for_signals():
    p = build_prompt("Q?", "A")
    assert "signals" in p
    for k in ("quantified", "ownership", "specific", "concise"):
        assert k in p


def test_parse_extracts_signals():
    fb = parse_response(json.dumps({"answered_question": True, "signals": {
        "quantified": True, "ownership": False, "specific": True, "concise": True}}))
    assert fb.signals == {"quantified": True, "ownership": False, "specific": True, "concise": True}


def test_parse_signals_default_false_on_fallback():
    fb = parse_response("not json at all")
    assert fb.signals == {"quantified": False, "ownership": False, "specific": False, "concise": False}


def test_prompt_asks_for_reasoning_first_and_uses_category():
    p = build_prompt("Q?", "A", category="Behavioral")
    assert "reasoning" in p
    assert p.index("reasoning") < p.index("- answered_question")   # reasoning requested first
    assert "Behavioral" in p
    assert "Question type" not in build_prompt("Q?", "A")          # absent without a category


def test_parse_extracts_reasoning():
    fb = parse_response(json.dumps({"answered_question": True,
                                    "reasoning": "answered, full STAR"}))
    assert fb.reasoning == "answered, full STAR"


def test_parse_returns_fallback_on_unparseable():
    fb = parse_response("not json at all")
    assert fb.kind == "interview"
    assert fb.answered_question is False
    assert "try" in fb.answered_explanation.lower()
    assert fb.star_missing == ["situation", "task", "action", "result"]


def test_parse_salvages_prose_wrapped_json():
    fb = parse_response('Sure: {"answered_question": true, "reasoning": "ok"} hope this helps')
    assert fb.answered_question is True
    assert fb.reasoning == "ok"


def test_analyze_content_pins_temperature_zero_and_passes_category():
    client = FakeClient(json.dumps({"answered_question": True}))
    analyze_content("Q?", "A", client=client, category="Leadership")
    assert client.kw["temperature"] == 0
    assert "Leadership" in client.kw["messages"][1]["content"]


def test_parse_response_computes_missing_and_caps_notes():
    raw = json.dumps({
        "answered_question": True,
        "answered_explanation": "ok",
        "star_present": {"situation": True, "task": False,
                         "action": True, "result": False},
        "issues": ["rambled"],
        "tighter_rewrite": "short",
        "coaching_notes": ["a", "b", "c", "d"],
    })
    fb = parse_response(raw)
    assert fb.star_missing == ["task", "result"]
    assert fb.coaching_notes == ["a", "b", "c"]
    assert fb.answered_question is True


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.kw = None

    def chat(self, **kw):
        self.kw = kw
        return {"message": {"content": self.payload}}


def test_analyze_content_uses_client_and_json_format():
    payload = json.dumps({
        "answered_question": False, "answered_explanation": "no",
        "star_present": {}, "issues": [], "tighter_rewrite": "",
        "coaching_notes": [],
    })
    client = FakeClient(payload)
    fb = analyze_content("Q?", "I dunno", client=client)
    assert fb.answered_question is False
    assert fb.star_missing == ["situation", "task", "action", "result"]
    assert client.kw["format"] == "json"


def test_parse_response_sets_interview_kind():
    raw = json.dumps({"answered_question": True, "answered_explanation": "ok",
                      "star_present": {}, "issues": [], "tighter_rewrite": "",
                      "coaching_notes": []})
    fb = parse_response(raw)
    assert fb.kind == "interview"


def test_parse_response_missing_star_present():
    raw = json.dumps({"answered_question": True})  # no star_present / lists
    fb = parse_response(raw)
    assert fb.star_missing == ["situation", "task", "action", "result"]
    assert fb.coaching_notes == []
    assert fb.kind == "interview"


def test_analyze_content_default_client_is_lazy():
    # With a fake injected client, ollama must not be required.
    import json
    import engine.content as content
    captured = {}

    class FakeClient:
        def chat(self, **kw):
            captured.update(kw)
            return {"message": {"content": json.dumps(
                {"answered_question": True, "answered_explanation": "ok",
                 "star_present": {}, "issues": [], "tighter_rewrite": "",
                 "coaching_notes": []})}}

    fb = content.analyze_content("Q", "A", client=FakeClient())
    assert fb.kind == "interview"
    assert captured["format"] == "json"
