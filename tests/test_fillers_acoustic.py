from engine.fillers.acoustic import classify_gap


def test_voiced_filled_pause_is_filler():
    assert classify_gap(voiced_frac=0.8, gap_db=60, speech_db=65,
                        pitch_std=20, duration=0.4) is True


def test_silent_gap_is_not_filler():
    assert classify_gap(voiced_frac=0.05, gap_db=35, speech_db=65,
                        pitch_std=0, duration=0.6) is False


def test_too_short_gap_rejected():
    assert classify_gap(voiced_frac=0.9, gap_db=64, speech_db=65,
                        pitch_std=10, duration=0.05) is False


def test_too_long_gap_rejected():
    assert classify_gap(voiced_frac=0.9, gap_db=64, speech_db=65,
                        pitch_std=10, duration=3.0) is False


def test_loud_but_unvoiced_rejected():
    assert classify_gap(voiced_frac=0.1, gap_db=64, speech_db=65,
                        pitch_std=10, duration=0.4) is False


def test_voiced_but_too_quiet_rejected():
    assert classify_gap(voiced_frac=0.6, gap_db=40, speech_db=65,
                        pitch_std=10, duration=0.4) is False


def test_unsteady_pitch_rejected():
    assert classify_gap(voiced_frac=0.7, gap_db=62, speech_db=65,
                        pitch_std=120, duration=0.4) is False
