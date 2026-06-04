import json
from dataclasses import dataclass, field

LANGUAGE_NAMES = {"ja": "Japanese", "en": "English"}

# Scored the way Avant's STAMP test scores speaking: a 1-8 Benchmark Level that maps 1:1 to
# ACTFL sublevels, rated on two axes — Text Type (amount/connectedness of language) and
# Accuracy (comprehensibility judged by audience). Text Type dominates at levels 1-6; the two
# are balanced at 7-8. (See docs/superpowers/STAMP-rubric.md for sources.)
SYSTEM = (
    "You are a certified rater scoring a spoken response the way Avant's STAMP test scores "
    "speaking. STAMP reports a Benchmark Level from 1 to 8 that maps one-to-one to ACTFL "
    "sublevels: 1=Novice-Low, 2=Novice-Mid, 3=Novice-High, 4=Intermediate-Low, "
    "5=Intermediate-Mid, 6=Intermediate-High, 7=Advanced-Low, 8=Advanced-Mid (speaking does "
    "not score higher). Rate on TWO axes. (1) TEXT TYPE — how much language and how "
    "connected, on this ladder: 1 isolated words; 2 phrases (words grammatically joined); "
    "3 simple, mostly memorized sentences in the present; 4 detailed but UNCONNECTED "
    "sentences; 5 loosely connected sentence groups with SOME transitions, other tenses "
    "attempted with errors; 6 pre-paragraph flow with VARIED connectors, beginning to switch "
    "past/present/future but breaking down; 7 full paragraph, time frames switched "
    "accurately, narration and description handled separately, can handle a complication; "
    "8 extended dense paragraph, narration and description interwoven, time frames near "
    "error-free, native-like flow. (2) ACCURACY = comprehensibility judged by AUDIENCE: can "
    "only someone ACCUSTOMED to language learners understand it (and with how much effort), "
    "or could someone UNACCUSTOMED to learners understand it easily? Weight TEXT TYPE more "
    "heavily for levels 1-6; weight the two axes roughly equally for 7-8 — a response cannot "
    "reach 7-8 on length alone, control and time-frame accuracy must hold. The biggest level "
    "discriminators are the amount of connected language, the density and variety of "
    "connectors, and control of time frames (present-only caps around 4-5; accurate "
    "past+present+future enables 6-7). Judge ONLY what was actually said; never invent "
    "errors. Treat self-correction and talking around an unknown word (circumlocution) as "
    "POSITIVES, not penalties. Be encouraging, specific, and honest. Also coach on HOW "
    "sentences are built (length, variety, connectors), and when the speaker uses English "
    "instead of the target language, name each English word and give the natural "
    "target-language equivalent."
)


@dataclass
class ProficiencyFeedback:
    kind: str
    level: str
    stamp_level: int          # STAMP benchmark 1-8 (0 = unknown); maps 1:1 to `level`
    level_explanation: str
    functions: str
    accuracy: str
    context_content: str
    text_type: str
    strengths: list
    next_steps: list
    english_words: list = field(default_factory=list)


def build_proficiency_prompt(question: str, answer: str, language: str = "ja") -> str:
    lang_name = LANGUAGE_NAMES.get(language, "the target language")
    return (
        f"Speaking task ({lang_name}):\n{question}\n\n"
        f"Speaker's transcribed response:\n{answer}\n\n"
        "Score this response the STAMP way (Text Type + Accuracy) and return ONLY JSON with:\n"
        "- level (string): the ACTFL level, e.g. 'Novice-High', 'Intermediate-Mid', "
        "'Advanced-Low'\n"
        "- stamp_level (integer 1-8): the STAMP benchmark number matching `level` "
        "(1=Novice-Low, 2=Novice-Mid, 3=Novice-High, 4=Intermediate-Low, 5=Intermediate-Mid, "
        "6=Intermediate-High, 7=Advanced-Low, 8=Advanced-Mid)\n"
        "- level_explanation (string): one or two sentences on why this level — the text "
        "type they sustain and what currently caps them\n"
        "- functions (string): did they accomplish the task's function (describe, narrate "
        "across time frames, give a supported opinion, handle a complication)? one to two "
        "sentences\n"
        "- accuracy (string): control of grammar, vocabulary, and pronunciation AND — most "
        "importantly — WHO could understand this: only someone accustomed to language "
        "learners (and with how much effort), or someone unaccustomed to learners too? one "
        "to two sentences\n"
        "- context_content (string): the topics and settings they handled; one sentence\n"
        "- text_type (string): where the response sits on the text-type ladder (isolated "
        "words, phrases, simple sentences, detailed unconnected sentences, connected groups, "
        "pre-paragraph, paragraph); the time frames used (present only, or past/present/"
        "future); and how ideas are connected (no links, some transitions, or varied "
        "connectors); also note sentence length and variety. two to three sentences\n"
        "- english_words (array of strings): any words or short phrases the speaker said in "
        f"ENGLISH instead of {lang_name}. These may appear in the transcript as English, as "
        "romaji, or as a katakana approximation of an English word. For EACH one give the "
        "English the speaker used and the natural " + lang_name + " they should have used, "
        'formatted exactly like: "weekend" → 週末 (しゅうまつ). '
        f"Do NOT flag established loanwords that are already normal, natural {lang_name} "
        "(e.g. テレビ, コンビニ, アニメ). Empty "
        f"array if the speaker stayed in {lang_name} throughout.\n"
        "- strengths (array of 2-3 short strings)\n"
        "- next_steps (array of 3-5 short, concrete things to practice to reach the next "
        "level. Include at least one tip on sentence structure or length — e.g. joining "
        "short sentences with connectives, varying sentence patterns, or building toward "
        "paragraph-length speech — and, when english_words is non-empty, a tip to say those "
        "words in " + lang_name + " instead.)"
    )


# `level` is the single source of truth; the STAMP number is derived from it in code so the
# two can never disagree on the one badge users fixate on.
ACTFL_TO_STAMP = {"novice-low": 1, "novice-mid": 2, "novice-high": 3,
                  "intermediate-low": 4, "intermediate-mid": 5, "intermediate-high": 6,
                  "advanced-low": 7, "advanced-mid": 8}


def _stamp_level(data: dict) -> int:
    """Derive the STAMP benchmark (1-8) from the ACTFL `level`. Falls back to the model's
    own `stamp_level` (clamped) only when `level` is unrecognized; 0 = unknown."""
    level = str(data.get("level", "")).strip().lower().replace("–", "-").replace("—", "-")
    if level in ACTFL_TO_STAMP:
        return ACTFL_TO_STAMP[level]
    try:
        return max(0, min(8, int(data.get("stamp_level") or 0)))
    except (TypeError, ValueError):
        return 0


def _salvage_json(raw: str):
    """LLMs (esp. local Ollama) sometimes wrap JSON in prose or truncate it. Try a strict
    parse, then a brace-substring salvage. Returns the dict, or None if unrecoverable."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def parse_proficiency_response(raw: str) -> ProficiencyFeedback:
    data = _salvage_json(raw)
    if data is None:  # never 500 the learner on a bad model response
        return ProficiencyFeedback(
            kind="proficiency", level="", stamp_level=0,
            level_explanation="Couldn't score this one — please try recording again.",
            functions="", accuracy="", context_content="", text_type="",
            strengths=[], next_steps=[], english_words=[])
    return ProficiencyFeedback(
        kind="proficiency",
        level=data.get("level", ""),
        stamp_level=_stamp_level(data),
        level_explanation=data.get("level_explanation", ""),
        functions=data.get("functions", ""),
        accuracy=data.get("accuracy", ""),
        context_content=data.get("context_content", ""),
        text_type=data.get("text_type", ""),
        strengths=list(data.get("strengths", []))[:3],
        next_steps=list(data.get("next_steps", []))[:5],
        english_words=list(data.get("english_words", []))[:10],
    )


def analyze_proficiency(question: str, answer: str, language: str = "ja",
                        model: str = "llama3.1", client=None,
                        temperature: float = 0.0) -> ProficiencyFeedback:
    # temperature=0 so the same recording scores the same level run-to-run (a kid
    # re-recording must not get a different number).
    if client is None:
        from engine.llm import OllamaChatClient
        client = OllamaChatClient()
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",
             "content": build_proficiency_prompt(question, answer, language)},
        ],
        format="json",
        temperature=temperature,
    )
    return parse_proficiency_response(resp["message"]["content"])
