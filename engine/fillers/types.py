from dataclasses import dataclass


@dataclass
class FillerHit:
    text: str
    start: float
    end: float
    source: str = "lexicon"


@dataclass
class FillerReport:
    hits: list
    count: int
    per_minute: float
