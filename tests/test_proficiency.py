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
                "next_steps", "english_words"):
        assert key in p


def test_prompt_asks_for_english_words_and_sentence_coaching():
    p = build_proficiency_prompt("質問", "答え", language="ja")
    assert "english_words" in p              # flags English used instead of Japanese
    assert "sentence" in p.lower()           # coaches on sentence structure / length


def test_parse_sets_kind_and_caps_lists():
    raw = json.dumps({
        "level": "Intermediate-Mid",
        "level_explanation": "sustains sentence-level description across everyday topics",
        "functions": "described the daily routine and gave reasons",
        "accuracy": "understandable to a sympathetic listener; minor particle errors",
        "context_content": "everyday, concrete topics",
        "text_type": "connected sentences; a few run-ons, sparse connectives",
        "strengths": ["clear", "fluent", "natural", "extra"],
        "next_steps": ["a", "b", "c", "d", "e", "f"],
    })
    fb = parse_proficiency_response(raw)
    assert fb.kind == "proficiency"
    assert fb.level == "Intermediate-Mid"
    assert len(fb.strengths) == 3
    assert len(fb.next_steps) == 5      # next_steps now allows up to 5 coaching items
    assert fb.english_words == []        # absent -> empty list


def test_parse_extracts_english_words():
    raw = json.dumps({
        "level": "Novice-High",
        "english_words": ['"weekend" → 週末 (しゅうまつ)', '"fun" → 楽しい'],
    })
    fb = parse_proficiency_response(raw)
    assert fb.english_words == ['"weekend" → 週末 (しゅうまつ)', '"fun" → 楽しい']


def test_prompt_includes_stamp_benchmark():
    p = build_proficiency_prompt("質問", "答え", language="ja")
    assert "stamp_level" in p                 # reports the STAMP 1-8 benchmark number
    assert "Novice-Low" in p and "Advanced-Mid" in p   # the 1-8 -> ACTFL map is spelled out


def test_parse_extracts_and_clamps_stamp_level():
    assert parse_proficiency_response(json.dumps({"stamp_level": 5})).stamp_level == 5
    assert parse_proficiency_response(json.dumps({"stamp_level": 99})).stamp_level == 8
    assert parse_proficiency_response(json.dumps({})).stamp_level == 0   # absent -> unknown
    assert parse_proficiency_response(json.dumps({"stamp_level": "4"})).stamp_level == 4


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
