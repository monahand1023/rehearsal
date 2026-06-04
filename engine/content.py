import json
from dataclasses import dataclass

STAR_KEYS = ("situation", "task", "action", "result")

SYSTEM = (
    "You are a concise, candid interview coach. You analyze a transcribed spoken "
    "answer to an interview question and return structured JSON feedback. Be "
    "specific and practical. Never invent facts the candidate did not say."
)


@dataclass
class ContentFeedback:
    answered_question: bool
    answered_explanation: str
    star_present: dict
    star_missing: list
    issues: list
    tighter_rewrite: str
    coaching_notes: list
    kind: str = "interview"


def build_prompt(question: str, answer: str) -> str:
    return (
        f"Interview question:\n{question}\n\n"
        f"Candidate's transcribed answer:\n{answer}\n\n"
        "Return ONLY JSON with these keys:\n"
        "- answered_question (boolean): did they actually answer what was asked\n"
        "- answered_explanation (string, one sentence)\n"
        "- star_present (object with booleans: situation, task, action, result)\n"
        "- issues (array of short strings: rambling, hedging, vague claims, etc.)\n"
        "- tighter_rewrite (string, an improved answer, <=120 words)\n"
        "- coaching_notes (array of exactly 3 short actionable tips)"
    )


def parse_response(raw: str) -> ContentFeedback:
    data = json.loads(raw)
    star_raw = data.get("star_present", {}) or {}
    star_present = {k: bool(star_raw.get(k)) for k in STAR_KEYS}
    star_missing = [k for k in STAR_KEYS if not star_present[k]]
    return ContentFeedback(
        answered_question=bool(data.get("answered_question", False)),
        answered_explanation=data.get("answered_explanation", ""),
        star_present=star_present,
        star_missing=star_missing,
        issues=list(data.get("issues", [])),
        tighter_rewrite=data.get("tighter_rewrite", ""),
        coaching_notes=list(data.get("coaching_notes", []))[:3],
        kind="interview",
    )


def analyze_content(question: str, answer: str, model: str = "llama3.1",
                    client=None, temperature: float = 0.0) -> ContentFeedback:
    # temperature=0 for a stable, reproducible assessment of the same answer.
    if client is None:
        from engine.llm import OllamaChatClient
        client = OllamaChatClient()
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(question, answer)},
        ],
        format="json",
        temperature=temperature,
    )
    return parse_response(resp["message"]["content"])
