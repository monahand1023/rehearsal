from dataclasses import dataclass

from engine.types import Transcript


@dataclass
class ClarityMetrics:
    mean_confidence: float
    low_confidence_words: list


def analyze_clarity(transcript: Transcript, low_threshold: float = 0.5) -> ClarityMetrics:
    words = transcript.words
    if not words:
        return ClarityMetrics(mean_confidence=0.0, low_confidence_words=[])
    confs = [w.probability for w in words]
    mean = round(sum(confs) / len(confs), 3)
    low = [w.text for w in words if w.probability < low_threshold]
    return ClarityMetrics(mean_confidence=mean, low_confidence_words=low)
