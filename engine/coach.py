COACH_SYSTEM = (
    "You are a candid but supportive speaking coach. You address the person directly "
    "as 'you'. Be warm, but HONEST and specific — do not inflate or over-praise. A "
    "vague 'great job' helps no one: name the one or two most important things to "
    "improve and exactly how to fix them. If they used filler words, spoke too fast, "
    "or were flat, say so plainly and kindly. If a proficiency level is provided, use exactly "
    "that level — never restate or imply a different one. Your summary will be read aloud, so "
    "write natural flowing spoken sentences — no lists, no markdown, no headings, no emoji."
)

# The Japanese track is a young learner. Praise is the reinforcement that keeps a kid
# practicing, so lead with a genuine specific win and give exactly ONE fun next step —
# honest, but never discouraging.
COACH_SYSTEM_KID = (
    "You are a warm, encouraging speaking coach for a YOUNG learner (a child) practicing "
    "Japanese. You address them directly as 'you'. Always start with genuine, SPECIFIC "
    "praise about something real they did (a topic they covered, speaking in Japanese at "
    "all, a good pace). Then give EXACTLY ONE thing to try next time, framed as a fun, "
    "doable challenge — never more than one. Be honest (if there is a real problem, pick "
    "the single most important one), but kind and motivating: a discouraged child stops "
    "practicing. Keep it short. If a proficiency level is provided, use exactly that level — "
    "never restate or imply a different one. Your summary will be read aloud, so write natural "
    "spoken sentences — no lists, no markdown, no headings, no emoji."
)

from engine.constants import LANG_EN, LANG_JA, MODE_INTERVIEW, MODE_JAPANESE

LANGUAGE_NAMES = {LANG_EN: "English", LANG_JA: "Japanese"}


def build_summary_prompt(report: dict, language: str = LANG_EN, mode: str = MODE_INTERVIEW) -> str:
    d = report["delivery"]
    f = report["fillers"]
    p = report.get("prosody")  # None in cloud "lite" mode
    c = report.get("content")
    lang_name = LANGUAGE_NAMES.get(language, "English")

    # Japanese is measured in characters/min (per-character tokenization makes wpm meaningless).
    rate = (f"- Speaking rate: {d.get('chars_per_minute', 0)} characters per minute"
            if language == LANG_JA
            else f"- Speaking rate: {d['words_per_minute']} words per minute")
    lines = [
        "Metrics from the person's spoken answer:",
        rate,
        f"- Filler words: {f['count']} total",
    ]
    # Pauses are unreliable for cloud-lite Japanese — OpenAI Whisper emits no inter-character
    # silence, so long_pause_count is systematically under-counted. Only tell the coach about
    # pauses when the signal is trustworthy (native mode has prosody; non-JP has real word gaps).
    if p or language != LANG_JA:
        lines.append(f"- Long pauses: {d['long_pause_count']}")
    if p:
        lines.append(f"- Monotone delivery: {'yes' if p['monotone'] else 'no'}")
    if c:
        if c.get("kind") == "proficiency":
            lines.append(f"- Estimated level: {c.get('level', '')}")
            lines.append(f"- How they did on the task: {c.get('functions', '')}")
            if c.get("english_words"):
                ew = "; ".join(c["english_words"][:4])
                lines.append(f"- Said in English instead of {lang_name}: {ew}")
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

    if mode == MODE_JAPANESE:   # young learner: one specific strength + one fun next step
        closing = (
            f"Write a short, friendly spoken summary in {lang_name}, 2 to 4 sentences, for a "
            f"young learner. Start with ONE genuine, specific thing they did well. Then give "
            f"EXACTLY ONE fun thing to try next time (for example: joining two sentences with "
            f"a connective, using a past-tense verb, or saying one of the English words in "
            f"{lang_name}). Only one suggestion. Be encouraging and honest. Plain spoken "
            f"prose only."
        )
    else:
        closing = (
            f"Write a short spoken summary in {lang_name}, 4 to 6 sentences, warm but candid. "
            f"Briefly note one genuine strength, then focus on the one or two most important, "
            f"SPECIFIC things to improve — name the actual issue (e.g. the fast pace, the "
            f"filler words, the flat delivery, a missing part of the answer, or any English "
            f"words used instead of {lang_name}) and how to fix it. Be honest; do not "
            f"over-praise. End with one concrete thing to practice next time. Plain spoken "
            f"prose only."
        )
    return f"{metrics}\n\n{closing}"


def compose_spoken_summary(report: dict, language: str = LANG_EN, mode: str = MODE_INTERVIEW,
                           model: str = "llama3.1", client=None) -> str:
    if client is None:
        from engine.llm import OllamaChatClient
        client = OllamaChatClient()
    system = COACH_SYSTEM_KID if mode == MODE_JAPANESE else COACH_SYSTEM
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": build_summary_prompt(report, language, mode)},
        ],
    )
    return resp["message"]["content"].strip()
