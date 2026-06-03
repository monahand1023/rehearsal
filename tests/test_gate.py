from fastapi.testclient import TestClient

import web.app as appmod

CODE = "open-sesame-1234"


def _client(monkeypatch):
    monkeypatch.setenv("REHEARSAL_ACCESS_CODE", CODE)
    monkeypatch.setenv("REHEARSAL_UNLOCK_DELAY", "0")  # no real sleep in tests
    monkeypatch.setenv("REHEARSAL_SESSION_SECRET", "test-secret")
    return TestClient(appmod.app)


def test_api_locked_without_cookie(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/tracks").status_code == 401


def test_page_shows_gate_without_cookie(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "access code" in resp.text.lower()


def test_unlock_wrong_code_401(monkeypatch):
    client = _client(monkeypatch)
    assert client.post("/api/unlock", data={"code": "nope"}).status_code == 401


def test_unlock_correct_code_then_api_open(monkeypatch):
    client = _client(monkeypatch)
    resp = client.post("/api/unlock", data={"code": CODE})
    assert resp.status_code == 200
    # TestClient keeps the cookie; the gated API now passes
    assert client.get("/api/tracks").status_code == 200


def test_unlock_endpoint_open_without_cookie(monkeypatch):
    # /api/unlock must be reachable while locked, else you could never get in
    client = _client(monkeypatch)
    assert client.post("/api/unlock", data={"code": "nope"}).status_code == 401  # not 404


def test_gate_off_leaves_everything_open(monkeypatch):
    monkeypatch.delenv("REHEARSAL_ACCESS_CODE", raising=False)
    client = TestClient(appmod.app)
    assert client.get("/api/tracks").status_code == 200  # today's behavior
