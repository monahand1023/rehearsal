def classify_gap(voiced_frac: float, gap_db: float, speech_db: float,
                 pitch_std: float, duration: float,
                 min_dur: float = 0.12, max_dur: float = 2.0,
                 min_voiced_frac: float = 0.45, db_margin: float = 15.0,
                 max_pitch_std: float = 70.0) -> bool:
    """True when a gap looks like a filled pause (um/uh) rather than silence."""
    if duration < min_dur or duration > max_dur:
        return False
    if voiced_frac < min_voiced_frac:
        return False
    if gap_db < speech_db - db_margin:
        return False
    if pitch_std > max_pitch_std:
        return False
    return True
