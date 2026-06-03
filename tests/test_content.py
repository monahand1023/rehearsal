import json

from engine.content import build_prompt, parse_response, analyze_content


def test_build_prompt_includes_question_and_answer():
    p = build_prompt("Tell me about a conflict", "I had a disagreement once")
    assert "Tell me about a conflict" in p
    assert "I had a disagreement once" in p


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
