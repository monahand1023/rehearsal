from dataclasses import dataclass


@dataclass
class Word:
    text: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class Transcript:
    words: list[Word]
    text: str
    duration: float
    language: str = "en"
