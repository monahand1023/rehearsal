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
    if entry["keywords"]:   # deliberately-thin clips (e.g. ja_thin) carry no content keywords
        assert sum(kw.lower() in text for kw in entry["keywords"]) >= 1, \
            f"no keyword found in: {report['transcript']['text']!r}"
    if entry["language"] == "ja":
        assert _has_kana_kanji(report["transcript"]["text"])

    # Filler recall is unreliable on clean TTS: Whisper drops fillers and the acoustic
    # detector can't recover ones that leave no voiced gap (see fillers-spike.md). The
    # end-to-end test asserts the pipeline produces a count, NOT a recall figure.
    count = report["fillers"]["count"]
    assert isinstance(count, int) and count >= 0

    # English uses words/min in a plausible band. Japanese reports characters/min instead
    # (per-character tokenization makes wpm meaningless, so it's zeroed there).
    if entry["language"] == "en":
        assert 40 <= report["delivery"]["words_per_minute"] <= 320
    else:
        assert report["delivery"]["words_per_minute"] == 0.0
        assert report["delivery"]["chars_per_minute"] > 0
    assert 0 < report["clarity"]["mean_confidence"] <= 1

    for k in ("transcript", "delivery", "fillers", "prosody", "clarity"):
        assert k in report
    assert report["content"] is None
    assert report["spoken_summary"] is None


def _ollama_model(prefix="llama3.1"):
    """Return an installed Ollama model usable as the content model, or None.

    The engine defaults to the bare tag ``llama3.1``; many machines instead have a
    specific variant like ``llama3.1:8b``. Resolve to whatever is actually pulled so
    the full-pipeline test runs (rather than skipping) when a usable model exists.
    """
    try:
        import ollama
        models = [m.get("model") or m.get("name")
                  for m in ollama.list().get("models", [])]
        if prefix in models:
            return prefix
        for m in models:
            if m and m.startswith(prefix + ":"):
                return m
        return None
    except Exception:
        return None


_OLLAMA_MODEL = _ollama_model()


def _find(entry_id):
    for e in _ENTRIES:
        if e["id"] == entry_id:
            return e
    return None


def _run_full(entry, question, mode, language, tmp_path):
    clip = _clip(entry)
    if not os.path.exists(clip):
        pytest.skip(f"clip not generated: {entry['id']}")
    local = tmp_path / (entry["id"] + ".mp3")
    shutil.copy(clip, local)
    return analyze_answer(str(local), question, language=language, mode=mode,
                          run_content=True, content_model=_OLLAMA_MODEL)


@pytest.mark.skipif(_OLLAMA_MODEL is None, reason="no llama3.1 model in Ollama")
def test_full_analyze_interview_with_ollama(tmp_path):
    entry = _find("en_story") or (_ENTRIES[0] if _ENTRIES else None)
    if not entry:
        pytest.skip("no manifest entries")
    report = _run_full(entry, "Tell me about a challenge you faced.",
                       "interview", "en", tmp_path)
    assert report["content"] is not None
    assert report["content"]["kind"] == "interview"
    assert report["spoken_summary"]


@pytest.mark.skipif(_OLLAMA_MODEL is None, reason="no llama3.1 model in Ollama")
def test_full_analyze_japanese_with_ollama(tmp_path):
    entry = _find("ja_clean") or _find("ja_fillers")
    if not entry:
        pytest.skip("no JP manifest entries")
    report = _run_full(entry, "あなたの趣味について話してください。",
                       "japanese", "ja", tmp_path)
    assert report["content"] is not None
    assert report["content"]["kind"] == "proficiency"
    assert report["spoken_summary"]
