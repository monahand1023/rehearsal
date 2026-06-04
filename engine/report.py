import os
from dataclasses import asdict

from engine.types import Transcript
from engine.delivery import DeliveryMetrics, analyze_delivery
from engine.fillers import FillerReport, detect_fillers
from engine.prosody import ProsodyMetrics, analyze_prosody
from engine.clarity import analyze_clarity
from engine.content import ContentFeedback, analyze_content
from engine.proficiency import analyze_proficiency
from engine.audio import to_wav
from engine.transcribe import transcribe
from engine.coach import compose_spoken_summary
from engine.llm import get_client, default_model


def _pauses_json(pauses):
    return [{"start": round(p.start, 2), "end": round(p.end, 2),
             "duration": round(p.duration, 2)} for p in pauses]


def build_report(transcript: Transcript, delivery: DeliveryMetrics,
                 fillers: FillerReport, prosody: ProsodyMetrics | None,
                 content: ContentFeedback | None) -> dict:
    clarity = analyze_clarity(transcript)
    # The cloud transcriber returns no per-word confidence (every probability defaults to
    # 1.0), so a constant 100% "clarity" would be a fake perfect score. Only report it when
    # the transcriber actually supplied a confidence signal (some word below 1.0).
    has_real_confidence = any(w.probability != 1.0 for w in transcript.words)
    return {
        "transcript": {
            "text": transcript.text,
            "duration": round(transcript.duration, 2),
            "words": [{"text": w.text, "start": round(w.start, 2),
                       "end": round(w.end, 2)} for w in transcript.words],
        },
        "delivery": {
            "words_per_minute": delivery.words_per_minute,
            "talk_time": round(delivery.talk_time, 2),
            "time_to_first_word": round(delivery.time_to_first_word, 2),
            "long_pause_count": delivery.long_pause_count,
            "pauses": _pauses_json(delivery.pauses),
        },
        "fillers": {
            "count": fillers.count,
            "per_minute": fillers.per_minute,
            "hits": [{"text": h.text, "start": round(h.start, 2),
                      "end": round(h.end, 2), "source": h.source}
                     for h in fillers.hits],
        },
        "prosody": None if prosody is None else {
            "mean_pitch_hz": prosody.mean_pitch_hz,
            "pitch_std_hz": prosody.pitch_std_hz,
            "pitch_range_hz": prosody.pitch_range_hz,
            "monotone": prosody.monotone,
            "mean_intensity_db": prosody.mean_intensity_db,
        },
        "clarity": ({"mean_confidence": clarity.mean_confidence,
                     "low_confidence_words": clarity.low_confidence_words}
                    if has_real_confidence else None),
        "content": None if content is None else asdict(content),
    }


def analyze_answer(audio_path: str, question: str, *, language: str = "en",
                   mode: str = "interview", run_content: bool = True,
                   content_model: str | None = None) -> dict:
    # "Lite" mode (cloud): no native audio tools — send the original file to the cloud
    # transcriber, skip parselmouth prosody and the acoustic filler pass (lexicon fillers
    # still run). REHEARSAL_AUDIO_NATIVE defaults to "true" so local is unchanged.
    native = os.environ.get("REHEARSAL_AUDIO_NATIVE", "true").lower() == "true"
    if native:
        wav = to_wav(audio_path)
        transcript = transcribe(wav, language=language)
        prosody = analyze_prosody(wav)
        fillers = detect_fillers(transcript, wav_path=wav)
    else:
        transcript = transcribe(audio_path, language=language)
        prosody = None
        fillers = detect_fillers(transcript)
    delivery = analyze_delivery(transcript)

    client = get_client()
    model = content_model or default_model()
    content = None
    if run_content and transcript.text:
        if mode == "japanese":
            content = analyze_proficiency(question, transcript.text,
                                          language=language, model=model, client=client)
        else:
            content = analyze_content(question, transcript.text, model=model, client=client)
    report = build_report(transcript, delivery, fillers, prosody, content)
    report["spoken_summary"] = (
        compose_spoken_summary(report, language=language, model=model, client=client)
        if run_content and transcript.text else None
    )
    return report
