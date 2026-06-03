from dataclasses import dataclass

from engine.types import Transcript


@dataclass
class Pause:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class DeliveryMetrics:
    total_audio_time: float
    talk_time: float
    time_to_first_word: float
    words_per_minute: float
    pauses: list[Pause]
    long_pause_count: int


def analyze_delivery(
    transcript: Transcript,
    gap_threshold: float = 0.5,
    long_pause_threshold: float = 2.0,
) -> DeliveryMetrics:
    words = transcript.words
    if not words:
        return DeliveryMetrics(
            total_audio_time=transcript.duration,
            talk_time=0.0,
            time_to_first_word=transcript.duration,
            words_per_minute=0.0,
            pauses=[],
            long_pause_count=0,
        )

    first = words[0].start
    last = words[-1].end
    talk_time = last - first
    wpm = len(words) / (talk_time / 60) if talk_time > 0 else 0.0

    pauses = []
    for a, b in zip(words, words[1:]):
        gap = b.start - a.end
        if gap >= gap_threshold:
            pauses.append(Pause(a.end, b.start))
    long_pause_count = sum(1 for p in pauses if p.duration >= long_pause_threshold)

    return DeliveryMetrics(
        total_audio_time=transcript.duration,
        talk_time=round(talk_time, 2),
        time_to_first_word=round(first, 2),
        words_per_minute=round(wpm, 1),
        pauses=pauses,
        long_pause_count=long_pause_count,
    )
