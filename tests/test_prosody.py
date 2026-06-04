import os

import pytest

from engine.prosody import summarize_pitch, analyze_prosody

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")


def test_summarize_ignores_unvoiced_zeros():
    mean, std, rng, monotone = summarize_pitch([0, 0, 100, 100, 100])
    assert mean == 100.0
    assert std == 0.0
    assert monotone is True


def test_summarize_varied_not_monotone():
    mean, std, rng, monotone = summarize_pitch([80, 120, 160, 200, 240])
    assert monotone is False
    assert rng == 160.0


def test_summarize_empty():
    assert summarize_pitch([]) == (0.0, 0.0, 0.0, True)


def test_high_pitch_child_varied_not_monotone():
    # A child's voice sits ~300 Hz; varied delivery must not read as "flat" the way a fixed
    # 20 Hz threshold would (it would mislabel this monotone).
    _, _, _, monotone = summarize_pitch([250, 350, 300, 420, 280])
    assert monotone is False


def test_high_pitch_flat_is_monotone():
    _, _, _, monotone = summarize_pitch([300, 302, 298, 301, 299])
    assert monotone is True


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture missing")
def test_analyze_prosody_on_fixture():
    m = analyze_prosody(FIXTURE)
    assert m.mean_pitch_hz > 0          # voiced speech detected
    assert m.mean_intensity_db > 0
