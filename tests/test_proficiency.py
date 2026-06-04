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


def test_system_has_calibration_anchors_and_thin_answer_floor():
    from engine.proficiency import SYSTEM
    assert "Calibration anchors" in SYSTEM
    assert "→ 1" in SYSTEM and "→ 7" in SYSTEM           # anchored across the scale
    assert "not enough language to rate" in SYSTEM       # thin/off-topic/silent floor


def test_prompt_excludes_proper_nouns_from_english_words():
    p = build_proficiency_prompt("質問", "答え", language="ja")
    assert "proper noun" in p.lower()


def test_prompt_asks_for_reasoning_first():
    p = build_proficiency_prompt("質問", "答え", language="ja")
    assert "reasoning" in p
    assert p.index("reasoning") < p.index("- level")   # reasoning requested before the level


def test_parse_extracts_reasoning():
    fb = parse_proficiency_response(json.dumps({"level": "Novice-High",
                                                "reasoning": "floor is simple sentences"}))
    assert fb.reasoning == "floor is simple sentences"


def test_prompt_includes_target_level_as_context():
    p = build_proficiency_prompt("質問", "答え", language="ja",
                                 target="Intermediate-High · 過去のナレーション")
    assert "Intermediate-High" in p and "do NOT inflate" in p
    assert "designed to elicit" not in build_proficiency_prompt("質問", "答え", language="ja")


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


def test_stamp_level_falls_back_to_model_number_when_level_unknown():
    # With no recognizable `level`, fall back to the model's clamped stamp_level (0 = unknown).
    assert parse_proficiency_response(json.dumps({"stamp_level": 5})).stamp_level == 5
    assert parse_proficiency_response(json.dumps({"stamp_level": 99})).stamp_level == 8
    assert parse_proficiency_response(json.dumps({})).stamp_level == 0
    assert parse_proficiency_response(json.dumps({"stamp_level": "4"})).stamp_level == 4


def test_stamp_level_derived_from_actfl_level():
    # `level` is the source of truth — derive STAMP from it in code, ignoring the model's
    # own number, so the two badges can never contradict each other.
    assert parse_proficiency_response(
        json.dumps({"level": "Intermediate-Mid", "stamp_level": 99})).stamp_level == 5
    assert parse_proficiency_response(json.dumps({"level": "Novice-Low"})).stamp_level == 1
    assert parse_proficiency_response(json.dumps({"level": "Advanced-Mid"})).stamp_level == 8


def test_parse_salvages_malformed_json():
    # LLMs sometimes wrap JSON in prose; parse must recover it, not raise.
    fb = parse_proficiency_response('Sure! {"level": "Novice-High"} hope that helps')
    assert fb.level == "Novice-High"
    assert fb.stamp_level == 3


def test_parse_returns_fallback_on_unparseable():
    fb = parse_proficiency_response("totally not json")
    assert fb.kind == "proficiency"
    assert fb.stamp_level == 0
    assert "try" in fb.level_explanation.lower()


def test_analyze_pins_temperature_zero():
    # Scoring must be deterministic: same recording -> same level run to run.
    client = FakeClient(json.dumps({"level": "Novice-High"}))
    analyze_proficiency("質問", "答え", language="ja", client=client)
    assert client.kw["temperature"] == 0


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
