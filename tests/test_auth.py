from web import auth


def test_gate_disabled_by_default(monkeypatch):
    monkeypatch.delenv("REHEARSAL_ACCESS_CODE", raising=False)
    assert auth.gate_enabled() is False


def test_gate_enabled_when_code_set(monkeypatch):
    monkeypatch.setenv("REHEARSAL_ACCESS_CODE", "swordfish")
    assert auth.gate_enabled() is True


def test_check_code(monkeypatch):
    monkeypatch.setenv("REHEARSAL_ACCESS_CODE", "swordfish")
    assert auth.check_code("swordfish") is True
    assert auth.check_code("wrong") is False
    assert auth.check_code("") is False


def test_check_code_false_when_gate_off(monkeypatch):
    monkeypatch.delenv("REHEARSAL_ACCESS_CODE", raising=False)
    assert auth.check_code("anything") is False  # nothing to match → reject


def test_token_round_trip(monkeypatch):
    monkeypatch.setenv("REHEARSAL_SESSION_SECRET", "s3cret")
    token = auth.make_token()
    assert auth.valid_token(token) is True


def test_token_rejects_tampering(monkeypatch):
    monkeypatch.setenv("REHEARSAL_SESSION_SECRET", "s3cret")
    token = auth.make_token()
    assert auth.valid_token(token + "x") is False
    assert auth.valid_token("garbage") is False
    assert auth.valid_token(None) is False


def test_token_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("REHEARSAL_SESSION_SECRET", "secretA")
    token = auth.make_token()
    monkeypatch.setenv("REHEARSAL_SESSION_SECRET", "secretB")
    assert auth.valid_token(token) is False


def test_unlock_delay_default(monkeypatch):
    monkeypatch.delenv("REHEARSAL_UNLOCK_DELAY", raising=False)
    assert auth.unlock_delay() == 3.0
