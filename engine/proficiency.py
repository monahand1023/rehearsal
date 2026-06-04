import json
from dataclasses import dataclass, field

LANGUAGE_NAMES = {"ja": "Japanese", "en": "English"}

# Scored the way STAMP/ACTFL does: holistically on the FACT criteria, awarding the level
# the speaker SUSTAINS across all four (capped by the weakest, not the best).
SYSTEM = (
    "You are a certified ACTFL-style proficiency rater scoring a spoken response the way "
    "the STAMP test does: holistically, using the FACT criteria — Functions/tasks, "
    "Accuracy, Context/content, and Text type. Assign the proficiency level the speaker "
    "SUSTAINS across ALL four criteria; a speaker is capped by their weakest criterion, "
    "not their best. Accuracy means being understood by a sympathetic listener accustomed "
    "to language learners — NOT being error-free; do not penalize minor errors that don't "
    "impede communication, and never invent mistakes the speaker did not make. Judge only "
    "what was actually said. Be encouraging, specific, and honest. Coach actively: comment "
    "on HOW the speaker builds sentences — their length, variety, and use of connecting "
    "words — and when the speaker falls back on English instead of the target language, "
    "name each English word and supply the natural target-language equivalent. Levels run "
    "Novice-Low through Advanced-Mid."
)


@dataclass
class ProficiencyFeedback:
    kind: str
    level: str
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
        "Rate this response using the ACTFL FACT criteria and return ONLY JSON with:\n"
        "- level (string): the sustained ACTFL level, e.g. 'Novice-High', "
        "'Intermediate-Mid', 'Advanced-Low'\n"
        "- level_explanation (string): one or two sentences on why this level — what they "
        "sustain and what currently caps them\n"
        "- functions (string): did they accomplish the task's function (describe, narrate, "
        "give a supported opinion, resolve the complication)? one to two sentences\n"
        "- accuracy (string): control of grammar and vocabulary AND how understandable they "
        "are to a sympathetic listener; one to two sentences\n"
        "- context_content (string): the topics and settings they handled; one sentence\n"
        "- text_type (string): the discourse level produced — isolated words/phrases, "
        "discrete sentences, or connected paragraph-length speech — AND a brief note on "
        "sentence length and structure: are the sentences too short and choppy, run-ons, "
        "all the same pattern, or well connected with conjunctions? one to two sentences\n"
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


def parse_proficiency_response(raw: str) -> ProficiencyFeedback:
    data = json.loads(raw)
    return ProficiencyFeedback(
        kind="proficiency",
        level=data.get("level", ""),
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
                        model: str = "llama3.1", client=None) -> ProficiencyFeedback:
    if client is None:
        import ollama
        client = ollama
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",
             "content": build_proficiency_prompt(question, answer, language)},
        ],
        format="json",
    )
    return parse_proficiency_response(resp["message"]["content"])
