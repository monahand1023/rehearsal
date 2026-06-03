import statistics

from engine.types import Transcript
from engine.fillers.types import FillerHit


def classify_gap(voiced_frac: float, gap_db: float, speech_db: float,
                 pitch_std: float, duration: float,
                 min_dur: float = 0.12, max_dur: float = 2.0,
                 min_voiced_frac: float = 0.65, db_margin: float = 15.0,
                 max_pitch_std: float = 70.0) -> bool:
    """True when a gap looks like a filled pause (um/uh) rather than silence.

    ``min_voiced_frac`` is 0.65 (not 0.5): a genuine filled pause is a SUSTAINED
    vowel and is predominantly voiced, whereas a clause-boundary pause often carries
    a partly-voiced decay tail from the preceding word (e.g. the long vowel + voiced
    /v/ of "leave"). Requiring majority-plus voicing rejects those tail artifacts.
    """
    if duration < min_dur or duration > max_dur:
        return False
    if voiced_frac < min_voiced_frac:
        return False
    if gap_db < speech_db - db_margin:
        return False
    if pitch_std > max_pitch_std:
        return False
    return True


def candidate_gaps(words, audio_start: float = 0.0):
    """Leading gap + every inter-word gap (trailing excluded)."""
    gaps = []
    if not words:
        return gaps
    if words[0].start > audio_start:
        gaps.append((audio_start, words[0].start))
    for a, b in zip(words, words[1:]):
        if b.start > a.end:
            gaps.append((a.end, b.start))
    return gaps


def _gap_features(pitch, intensity, t0, t1):
    from parselmouth.praat import call
    times = pitch.xs()
    freqs = pitch.selected_array["frequency"]
    in_window = [f for t, f in zip(times, freqs) if t0 <= t <= t1]
    total = len(in_window)
    voiced = [f for f in in_window if f and f > 0]
    voiced_frac = (len(voiced) / total) if total else 0.0
    pitch_std = statistics.pstdev(voiced) if len(voiced) > 1 else 0.0
    try:
        gap_db = float(call(intensity, "Get mean", t0, t1, "dB"))
    except Exception:
        gap_db = 0.0
    return voiced_frac, gap_db, pitch_std


def detect_acoustic_fillers(transcript: Transcript, wav_path: str,
                            **thresholds) -> list[FillerHit]:
    words = transcript.words
    if not words:
        return []
    import parselmouth  # lazy: cloud "lite" mode never calls this
    from parselmouth.praat import call
    snd = parselmouth.Sound(wav_path)
    pitch = snd.to_pitch()
    intensity = snd.to_intensity()
    speech_db = float(call(intensity, "Get mean", 0, 0, "dB"))

    hits: list[FillerHit] = []
    for t0, t1 in candidate_gaps(words):
        voiced_frac, gap_db, pitch_std = _gap_features(pitch, intensity, t0, t1)
        if classify_gap(voiced_frac, gap_db, speech_db, pitch_std, t1 - t0,
                        **thresholds):
            hits.append(FillerHit(text="(uh)", start=round(t0, 2),
                                  end=round(t1, 2), source="acoustic"))
    return hits
