import json
import os

MANIFEST = os.path.join(os.path.dirname(__file__), "fixtures", "generated", "manifest.json")
REQUIRED = {"id", "language", "mode", "text", "expected_fillers", "keywords"}


def test_manifest_valid():
    entries = json.load(open(MANIFEST))
    assert len(entries) >= 3
    ids = set()
    for e in entries:
        assert REQUIRED <= set(e), f"missing keys in {e.get('id')}"
        assert e["language"] in ("en", "ja")
        assert isinstance(e["keywords"], list)  # may be empty for deliberately-thin clips
        ids.add(e["id"])
    assert len(ids) == len(entries)  # ids unique
