import json
from dataclasses import dataclass

import ollama

LANGUAGE_NAMES = {"ja": "Japanese", "en": "English"}

SYSTEM = (
    "You are a supportive language-proficiency assessor. You evaluate a transcribed "
    "spoken answer to a prompt and return structured JSON. You estimate an ACTFL-style "
    "proficiency level and give specific, kind, actionable feedback. You are NOT an "
    "official scorer — this is a practice estimate. Never invent content the speaker "
    "did not say."
)


@dataclass
class ProficiencyFeedback:
    kind: str
    level: str
    task_completion: str
    grammar: str
    vocabulary: str
    coherence: str
    strengths: list
    suggestions: list


def build_proficiency_prompt(question: str, answer: str, language: str = "ja") -> str:
    lang_name = LANGUAGE_NAMES.get(language, "the target language")
    return (
        f"Prompt ({lang_name}):\n{question}\n\n"
        f"Speaker's transcribed answer:\n{answer}\n\n"
        "Return ONLY JSON with these keys:\n"
        "- level (string): estimated ACTFL-style level, e.g. 'Novice-High', "
        "'Intermediate-Mid', 'Advanced-Low'\n"
        "- task_completion (string): did they address the prompt; one sentence\n"
        "- grammar (string): grammatical range and accuracy; one sentence\n"
        "- vocabulary (string): lexical range; one sentence\n"
        "- coherence (string): organization and flow; one sentence\n"
        "- strengths (array of 2-3 short strings)\n"
        "- suggestions (array of 2-3 short, actionable strings)"
    )


def parse_proficiency_response(raw: str) -> ProficiencyFeedback:
    data = json.loads(raw)
    return ProficiencyFeedback(
        kind="proficiency",
        level=data.get("level", ""),
        task_completion=data.get("task_completion", ""),
        grammar=data.get("grammar", ""),
        vocabulary=data.get("vocabulary", ""),
        coherence=data.get("coherence", ""),
        strengths=list(data.get("strengths", []))[:3],
        suggestions=list(data.get("suggestions", []))[:3],
    )


def analyze_proficiency(question: str, answer: str, language: str = "ja",
                        model: str = "llama3.1", client=ollama) -> ProficiencyFeedback:
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
