import statistics
from dataclasses import dataclass


@dataclass
class ProsodyMetrics:
    mean_pitch_hz: float
    pitch_std_hz: float
    pitch_range_hz: float
    monotone: bool
    mean_intensity_db: float


def summarize_pitch(values, monotone_cv_threshold: float = 0.12):
    voiced = [v for v in values if v and v > 0]
    if not voiced:
        return (0.0, 0.0, 0.0, True)
    mean = statistics.fmean(voiced)
    std = statistics.pstdev(voiced) if len(voiced) > 1 else 0.0
    rng = max(voiced) - min(voiced)
    # Monotone is judged RELATIVE to the speaker's pitch (coefficient of variation), not a
    # fixed Hz threshold: a child's voice sits ~300 Hz, where 20 Hz of variation is far flatter
    # than 20 Hz on a ~120 Hz adult voice. CV also suits Japanese pitch-accent's modest range.
    cv = std / mean if mean else 0.0
    return (round(mean, 1), round(std, 1), round(rng, 1), cv < monotone_cv_threshold)


def analyze_prosody(wav_path: str, monotone_cv_threshold: float = 0.12) -> ProsodyMetrics:
    import parselmouth  # lazy: cloud "lite" mode never calls this, so it needn't be installed
    from parselmouth.praat import call
    snd = parselmouth.Sound(wav_path)
    pitch = snd.to_pitch()
    values = list(pitch.selected_array["frequency"])
    mean, std, rng, monotone = summarize_pitch(values, monotone_cv_threshold)
    intensity = snd.to_intensity()
    mean_db = round(float(call(intensity, "Get mean", 0, 0, "dB")), 1)
    return ProsodyMetrics(mean, std, rng, monotone, mean_db)
