COACH_SYSTEM = (
    "You are a candid but supportive speaking coach. You address the person directly "
    "as 'you'. Be warm, but HONEST and specific — do not inflate or over-praise. A "
    "vague 'great job' helps no one: name the one or two most important things to "
    "improve and exactly how to fix them. If they used filler words, spoke too fast, "
    "or were flat, say so plainly and kindly. Your summary will be read aloud, so "
    "write natural flowing spoken sentences — no lists, no markdown, no headings, no emoji."
)

LANGUAGE_NAMES = {"en": "English", "ja": "Japanese"}


def build_summary_prompt(report: dict, language: str = "en") -> str:
    d = report["delivery"]
    f = report["fillers"]
    p = report.get("prosody")  # None in cloud "lite" mode
    c = report.get("content")
    lang_name = LANGUAGE_NAMES.get(language, "English")

    lines = [
        "Metrics from the person's spoken answer:",
        f"- Speaking rate: {d['words_per_minute']} words per minute",
        f"- Filler words: {f['count']} total",
        f"- Long pauses: {d['long_pause_count']}",
    ]
    if p:
        lines.append(f"- Monotone delivery: {'yes' if p['monotone'] else 'no'}")
    if c:
        if c.get("kind") == "proficiency":
            lines.append(f"- Estimated level: {c.get('level', '')}")
            lines.append(f"- How they did on the task: {c.get('functions', '')}")
        else:
            lines.append(
                f"- Answered the question: {'yes' if c.get('answered_question') else 'no'}"
            )
            if c.get("star_missing"):
                lines.append(f"- Missing STAR parts: {', '.join(c['star_missing'])}")
    cl = report.get("clarity")
    if cl:
        lines.append(f"- Clarity (confidence proxy): {cl['mean_confidence']}")
    metrics = "\n".join(lines)

    return (
        f"{metrics}\n\n"
        f"Write a short spoken summary in {lang_name}, 4 to 6 sentences, warm but candid. "
        f"Briefly note one genuine strength, then focus on the one or two most important, "
        f"SPECIFIC things to improve — name the actual issue (e.g. the fast pace, the "
        f"filler words, the flat delivery, a missing part of the answer) and how to fix "
        f"it. Be honest; do not over-praise. End with one concrete thing to practice next "
        f"time. Plain spoken prose only."
    )


def compose_spoken_summary(report: dict, language: str = "en",
                           model: str = "llama3.1", client=None) -> str:
    if client is None:
        import ollama
        client = ollama
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": COACH_SYSTEM},
            {"role": "user", "content": build_summary_prompt(report, language)},
        ],
    )
    return resp["message"]["content"].strip()
