from datetime import datetime, timezone

from web import storage


class FakeS3:
    def __init__(self):
        self.calls = []

    def put_object(self, **kw):
        self.calls.append(kw)


def test_save_disabled_without_bucket(monkeypatch):
    monkeypatch.delenv("REHEARSAL_RECORDINGS_BUCKET", raising=False)
    assert storage.save_attempt(b"x", ".webm", {"ok": True}) is None


def test_save_writes_audio_and_report_encrypted(monkeypatch):
    monkeypatch.setenv("REHEARSAL_RECORDINGS_BUCKET", "my-bucket")
    s3 = FakeS3()
    now = datetime(2026, 6, 4, 3, 1, 2, tzinfo=timezone.utc)
    prefix = storage.save_attempt(b"AUDIO", ".webm", {"transcript": {"text": "hi"}},
                                  mode="japanese", language="ja", client=s3, now=now)
    assert prefix.startswith("recordings/2026-06-04/030102-")
    assert len(s3.calls) == 2
    audio_call, report_call = s3.calls
    assert audio_call["Bucket"] == "my-bucket"
    assert audio_call["Key"].endswith("/audio.webm")
    assert audio_call["Body"] == b"AUDIO"
    assert audio_call["ServerSideEncryption"] == "AES256"   # encrypted at rest
    assert report_call["Key"].endswith("/report.json")
    assert report_call["ServerSideEncryption"] == "AES256"
    import json
    meta = json.loads(report_call["Body"])
    assert meta["mode"] == "japanese" and meta["report"]["transcript"]["text"] == "hi"


def test_analyze_saves_when_bucket_set(monkeypatch):
    monkeypatch.setenv("REHEARSAL_RECORDINGS_BUCKET", "b")
    import web.app as appmod
    captured = {}
    monkeypatch.setattr(appmod, "analyze_answer",
                        lambda *a, **k: {"transcript": {"text": ""}})
    monkeypatch.setattr(appmod, "save_attempt",
                        lambda *a, **k: captured.setdefault("saved", True))
    from fastapi.testclient import TestClient
    client = TestClient(appmod.app)
    client.post("/api/analyze", data={"question": "Q", "mode": "japanese"},
                files={"audio": ("a.webm", b"x", "audio/webm")})
    assert captured.get("saved") is True
