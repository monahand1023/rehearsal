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
