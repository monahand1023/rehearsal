import json

from engine.proficiency import (build_proficiency_prompt,
                                 parse_proficiency_response, analyze_proficiency)


def test_prompt_includes_question_answer_and_language():
    p = build_proficiency_prompt("好きな食べ物は？", "寿司が好きです", language="ja")
    assert "好きな食べ物は？" in p
    assert "寿司が好きです" in p
    assert "Japanese" in p


def test_prompt_references_fact_criteria():
    p = build_proficiency_prompt("質問", "答え", language="ja")
    for key in ("level", "functions", "accuracy", "context_content", "text_type",
                "next_steps"):
        assert key in p


def test_parse_sets_kind_and_caps_lists():
    raw = json.dumps({
        "level": "Intermediate-Mid",
        "level_explanation": "sustains sentence-level description across everyday topics",
        "functions": "described the daily routine and gave reasons",
        "accuracy": "understandable to a sympathetic listener; minor particle errors",
        "context_content": "everyday, concrete topics",
        "text_type": "strings of connected sentences",
        "strengths": ["clear", "fluent", "natural", "extra"],
        "next_steps": ["use connectors", "narrate in past", "expand vocabulary", "extra"],
    })
    fb = parse_proficiency_response(raw)
    assert fb.kind == "proficiency"
    assert fb.level == "Intermediate-Mid"
    assert fb.text_type == "strings of connected sentences"
    assert len(fb.strengths) == 3
    assert len(fb.next_steps) == 3


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.kw = None

    def chat(self, **kw):
        self.kw = kw
        return {"message": {"content": self.payload}}


def test_analyze_uses_client_and_json_format():
    payload = json.dumps({"level": "Novice-High", "level_explanation": "", "functions": "",
                          "accuracy": "", "context_content": "", "text_type": "",
                          "strengths": [], "next_steps": []})
    client = FakeClient(payload)
    fb = analyze_proficiency("質問", "答え", language="ja", client=client)
    assert fb.kind == "proficiency"
    assert fb.level == "Novice-High"
    assert client.kw["format"] == "json"
