from dataclasses import dataclass

from engine.constants import LANG_EN


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
    language: str = LANG_EN
