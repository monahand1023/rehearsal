from dataclasses import dataclass

STAR_KEYS = ("situation", "task", "action", "result")

SYSTEM = (
    "You are a concise, candid interview coach analyzing a transcribed spoken answer to an "
    "interview question (often behavioral/STAR). Return structured JSON feedback. Be specific "
    "and practical; never invent facts the candidate did not say. Work step by step: first "
    "decide whether they actually ANSWERED the question asked; then identify which STAR "
    "elements (Situation, Task, Action, Result) are present; then name the single most "
    "important issue and how to fix it. If the response is too short, off-topic, silent, or "
    "not a real attempt, say so plainly — set answered_question false, leave the STAR elements "
    "empty, and do NOT fabricate a situation, action, or result that was not actually said. "
    "Put your step-by-step reasoning in the `reasoning` field first."
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
    reasoning: str = ""      # the coach's step-by-step working (audit trail; not displayed)


def build_prompt(question: str, answer: str, category: str = "") -> str:
    # Behavioral questions are engineered to elicit a STAR story; tell the rater so it knows
    # whether to expect all four elements (a "greatest strength" question may not need them).
    cat_note = (f"(Question type: {category}. Behavioral questions expect a full STAR story; "
                "general questions may not.)\n\n" if category else "")
    return (
        f"Interview question:\n{question}\n\n"
        f"Candidate's transcribed answer:\n{answer}\n\n"
        f"{cat_note}"
        "Return ONLY JSON with these keys:\n"
        "- reasoning (string): think step by step FIRST — did they answer the question, which "
        "STAR elements are present, and the single most important issue\n"
        "- answered_question (boolean): did they actually answer what was asked\n"
        "- answered_explanation (string, one sentence)\n"
        "- star_present (object with booleans: situation, task, action, result)\n"
        "- issues (array of short strings: rambling, hedging, vague claims, etc.)\n"
        "- tighter_rewrite (string, an improved answer, <=120 words)\n"
        "- coaching_notes (array of exactly 3 short actionable tips)"
    )


def parse_response(raw: str) -> ContentFeedback:
    from engine.llm import salvage_json
    data = salvage_json(raw)
    if data is None:  # never 500 the user on a bad model response
        return ContentFeedback(
            answered_question=False,
            answered_explanation="Couldn't analyze this one — please try recording again.",
            star_present={k: False for k in STAR_KEYS},
            star_missing=list(STAR_KEYS), issues=[], tighter_rewrite="",
            coaching_notes=[], reasoning="")
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
        reasoning=data.get("reasoning", ""),
    )


def analyze_content(question: str, answer: str, model: str = "llama3.1",
                    client=None, temperature: float = 0.0,
                    category: str = "") -> ContentFeedback:
    # temperature=0 for a stable, reproducible assessment of the same answer.
    if client is None:
        from engine.llm import OllamaChatClient
        client = OllamaChatClient()
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(question, answer, category)},
        ],
        format="json",
        temperature=temperature,
    )
    return parse_response(resp["message"]["content"])
