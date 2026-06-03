from fastapi.testclient import TestClient

import web.app as appmod


def test_questions_endpoint():
    client = TestClient(appmod.app)
    resp = client.get("/api/questions?track=interview_en")
    assert resp.status_code == 200
    body = resp.json()
    assert body["track"] == "interview_en"
    assert len(body["questions"]) >= 1


def test_questions_unknown_track_404():
    client = TestClient(appmod.app)
    resp = client.get("/api/questions?track=nope")
    assert resp.status_code == 404


def test_analyze_endpoint_calls_engine(monkeypatch):
    captured = {}

    def fake_analyze(audio_path, question, **kwargs):
        captured["question"] = question
        return {"ok": True}

    monkeypatch.setattr(appmod, "analyze_answer", fake_analyze)
    client = TestClient(appmod.app)
    resp = client.post(
        "/api/analyze",
        data={"question": "Tell me about yourself"},
        files={"audio": ("a.webm", b"fakebytes", "audio/webm")},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert captured["question"] == "Tell me about yourself"


def test_config_endpoint_reports_disabled(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    client = TestClient(appmod.app)
    assert client.get("/api/config").json() == {"tts_enabled": False}


def test_speak_without_key_returns_503(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    client = TestClient(appmod.app)
    resp = client.post("/api/speak", data={"text": "hi", "language": "en"})
    assert resp.status_code == 503


def test_speak_with_key_returns_audio(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    import engine.tts.elevenlabs as el
    monkeypatch.setattr(el.ElevenLabsProvider, "synthesize",
                        lambda self, text, language="en": b"AUDIOBYTES")
    client = TestClient(appmod.app)
    resp = client.post("/api/speak", data={"text": "great", "language": "en"})
    assert resp.status_code == 200
    assert resp.content == b"AUDIOBYTES"
    assert resp.headers["content-type"] == "audio/mpeg"


def test_tracks_endpoint_lists_both():
    client = TestClient(appmod.app)
    body = client.get("/api/tracks").json()
    tracks = {t["track"]: t for t in body["tracks"]}
    assert "interview_en" in tracks
    assert "language_jp" in tracks
    assert tracks["language_jp"]["language"] == "ja"
