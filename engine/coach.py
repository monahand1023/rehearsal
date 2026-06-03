import ollama

COACH_SYSTEM = (
    "You are a warm, patient, encouraging speaking coach. You address the person "
    "directly as 'you'. You are kind and never harsh. Your summary will be read "
    "aloud, so write natural flowing spoken sentences — no lists, no markdown, no "
    "headings, no emoji."
)

LANGUAGE_NAMES = {"en": "English", "ja": "Japanese"}


def build_summary_prompt(report: dict, language: str = "en") -> str:
    d = report["delivery"]
    f = report["fillers"]
    p = report["prosody"]
    c = report.get("content")
    lang_name = LANGUAGE_NAMES.get(language, "English")

    lines = [
        "Metrics from the person's spoken answer:",
        f"- Speaking rate: {d['words_per_minute']} words per minute",
        f"- Filler words: {f['count']} total",
        f"- Long pauses: {d['long_pause_count']}",
        f"- Monotone delivery: {'yes' if p['monotone'] else 'no'}",
    ]
    if c:
        lines.append(
            f"- Answered the question: {'yes' if c['answered_question'] else 'no'}"
        )
        if c.get("star_missing"):
            lines.append(f"- Missing STAR parts: {', '.join(c['star_missing'])}")
    cl = report.get("clarity")
    if cl:
        lines.append(f"- Clarity (confidence proxy): {cl['mean_confidence']}")
    metrics = "\n".join(lines)

    return (
        f"{metrics}\n\n"
        f"Write a short spoken summary in {lang_name}, 3 to 5 sentences, in a kind and "
        f"patient tone. Touch on their pace, the one or two most important delivery "
        f"notes, and end with one encouraging, specific thing to try next time. Plain "
        f"spoken prose only."
    )


def compose_spoken_summary(report: dict, language: str = "en",
                           model: str = "llama3.1", client=ollama) -> str:
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": COACH_SYSTEM},
            {"role": "user", "content": build_summary_prompt(report, language)},
        ],
    )
    return resp["message"]["content"].strip()
