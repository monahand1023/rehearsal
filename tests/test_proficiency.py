import json

from engine.proficiency import (build_proficiency_prompt,
                                 parse_proficiency_response, analyze_proficiency)


def test_prompt_includes_question_answer_and_language():
    p = build_proficiency_prompt("好きな食べ物は？", "寿司が好きです", language="ja")
    assert "好きな食べ物は？" in p
    assert "寿司が好きです" in p
    assert "Japanese" in p


def test_parse_sets_kind_and_caps_lists():
    raw = json.dumps({
        "level": "Intermediate-Mid",
        "task_completion": "addressed the prompt",
        "grammar": "mostly accurate",
        "vocabulary": "adequate range",
        "coherence": "well organized",
        "strengths": ["clear", "fluent", "natural", "extra"],
        "suggestions": ["use connectors", "vary vocab", "slow down", "extra"],
    })
    fb = parse_proficiency_response(raw)
    assert fb.kind == "proficiency"
    assert fb.level == "Intermediate-Mid"
    assert len(fb.strengths) == 3
    assert len(fb.suggestions) == 3


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.kw = None

    def chat(self, **kw):
        self.kw = kw
        return {"message": {"content": self.payload}}


def test_analyze_uses_client_and_json_format():
    payload = json.dumps({"level": "Novice-High", "task_completion": "partial",
                          "grammar": "", "vocabulary": "", "coherence": "",
                          "strengths": [], "suggestions": []})
    client = FakeClient(payload)
    fb = analyze_proficiency("質問", "答え", language="ja", client=client)
    assert fb.kind == "proficiency"
    assert fb.level == "Novice-High"
    assert client.kw["format"] == "json"
