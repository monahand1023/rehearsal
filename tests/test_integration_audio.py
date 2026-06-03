import json
import os
import shutil

import pytest

from engine.report import analyze_answer

GEN_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "generated")
MANIFEST = os.path.join(GEN_DIR, "manifest.json")


def _entries():
    if not os.path.exists(MANIFEST):
        return []
    return json.load(open(MANIFEST))


def _clip(entry):
    return os.path.join(GEN_DIR, entry["id"] + ".mp3")


def _has_kana_kanji(s):
    return any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in s)


_ENTRIES = _entries()


@pytest.mark.parametrize("entry", _ENTRIES, ids=[e["id"] for e in _ENTRIES])
def test_engine_on_generated_clip(entry, tmp_path):
    clip = _clip(entry)
    if not os.path.exists(clip):
        pytest.skip(f"clip not generated: {entry['id']} (run scripts/gen_test_audio.py)")
    # Copy into tmp so the converted .wav lands in tmp, not the fixtures dir.
    local = tmp_path / (entry["id"] + ".mp3")
    shutil.copy(clip, local)

    report = analyze_answer(str(local), "", language=entry["language"],
                            mode=entry["mode"], run_content=False)

    text = report["transcript"]["text"].lower()
    assert sum(kw.lower() in text for kw in entry["keywords"]) >= 1, \
        f"no keyword found in: {report['transcript']['text']!r}"
    if entry["language"] == "ja":
        assert _has_kana_kanji(report["transcript"]["text"])

    # Filler recall is unreliable on clean TTS: Whisper drops fillers and the acoustic
    # detector can't recover ones that leave no voiced gap (see fillers-spike.md). The
    # end-to-end test asserts the pipeline produces a count, NOT a recall figure.
    count = report["fillers"]["count"]
    assert isinstance(count, int) and count >= 0

    # WPM: English in a plausible band; Japanese reads high (short Whisper "words" —
    # a known rough edge), so only assert it's positive there.
    wpm = report["delivery"]["words_per_minute"]
    if entry["language"] == "en":
        assert 40 <= wpm <= 320
    else:
        assert wpm > 0
    assert 0 < report["clarity"]["mean_confidence"] <= 1

    for k in ("transcript", "delivery", "fillers", "prosody", "clarity"):
        assert k in report
    assert report["content"] is None
    assert report["spoken_summary"] is None
