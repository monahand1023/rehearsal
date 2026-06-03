# Access-Code Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate the app behind a single shared access code: a gate page exchanges the code for a signed cookie; the app and all `/api/*` routes require that cookie. Opt-in via env, so local dev and the existing suite are unchanged.

**Architecture:** A small `web/auth.py` holds the gate logic — is-the-gate-on, constant-time code check, and signed-token mint/verify (itsdangerous). One FastAPI HTTP middleware enforces it: when `REHEARSAL_ACCESS_CODE` is unset it is a pass-through (today's behavior); when set, unauthed `/api/*` returns 401 and unauthed page loads return a self-contained gate page. `POST /api/unlock` checks the code (constant-time), sleeps ~3s on failure, and sets the cookie on success.

**Tech Stack:** Python 3.11+, FastAPI/Starlette, itsdangerous (signed cookie; already a Starlette transitive dep — pinned explicitly), pytest with TestClient (cookies persist across calls).

---

## File structure

```
web/auth.py            # NEW: gate_enabled, check_code, make_token, valid_token, unlock_delay, cookie_secure, COOKIE_NAME
web/app.py             # MODIFY: gate middleware + POST /api/unlock
web/static/gate.html   # NEW: self-contained access-code page (warm aesthetic)
requirements.txt       # MODIFY: + itsdangerous
requirements-cloud.txt # MODIFY: + itsdangerous
README.md              # MODIFY: document the gate env vars
tests/test_auth.py     # NEW: helper unit tests
tests/test_gate.py     # NEW: end-to-end gate behavior via TestClient
```

**Env vars (all optional; gate is OFF unless `REHEARSAL_ACCESS_CODE` is set):**

| Env var | Default | Meaning |
|---|---|---|
| `REHEARSAL_ACCESS_CODE` | (unset → gate off) | the shared secret code |
| `REHEARSAL_SESSION_SECRET` | `"dev-insecure-secret"` | signs the session cookie (set a real one in cloud) |
| `REHEARSAL_UNLOCK_DELAY` | `3.0` | seconds to sleep on a failed unlock |
| `REHEARSAL_COOKIE_SECURE` | `false` | set `true` in cloud (HTTPS) so the cookie is Secure |

**Pre-req:** the app is at 106 passing tests; no gate exists yet.

---

## Task 1: Gate helpers (`web/auth.py`)

**Files:** Create `web/auth.py`, `tests/test_auth.py`.

- [ ] **Step 1: Write failing tests** in `tests/test_auth.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_auth.py -v`
Expected: FAIL — `No module named 'web.auth'`.

- [ ] **Step 3: Create `web/auth.py`**:

```python
import hmac
import os

from itsdangerous import URLSafeTimedSerializer

COOKIE_NAME = "rehearsal_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_SALT = "rehearsal-gate"


def gate_enabled() -> bool:
    return bool(os.environ.get("REHEARSAL_ACCESS_CODE"))


def check_code(submitted: str) -> bool:
    secret = os.environ.get("REHEARSAL_ACCESS_CODE")
    if not secret:
        return False
    return hmac.compare_digest(submitted or "", secret)


def _serializer() -> URLSafeTimedSerializer:
    key = os.environ.get("REHEARSAL_SESSION_SECRET", "dev-insecure-secret")
    return URLSafeTimedSerializer(key, salt=_SALT)


def make_token() -> str:
    return _serializer().dumps("ok")


def valid_token(token) -> bool:
    if not token:
        return False
    try:
        _serializer().loads(token, max_age=COOKIE_MAX_AGE)
        return True
    except Exception:  # bad signature, expired, or malformed → not valid
        return False


def unlock_delay() -> float:
    return float(os.environ.get("REHEARSAL_UNLOCK_DELAY", "3.0"))


def cookie_secure() -> bool:
    return os.environ.get("REHEARSAL_COOKIE_SECURE", "false").lower() == "true"
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_auth.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Add `itsdangerous` to both requirements files**

Append `itsdangerous` as a line to `requirements.txt` AND to `requirements-cloud.txt`.
Then: `.venv/bin/pip install itsdangerous` (it's already present transitively, but make it explicit).

- [ ] **Step 6: Commit**

```bash
git add web/auth.py tests/test_auth.py requirements.txt requirements-cloud.txt
git commit -m "feat: access-code gate helpers (constant-time check, signed token)"
```

---

## Task 2: Gate middleware + `/api/unlock` + gate page

**Files:** Modify `web/app.py`; create `web/static/gate.html`, `tests/test_gate.py`.

- [ ] **Step 1: Write failing tests** in `tests/test_gate.py`:

```python
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
    assert client.post("/api/unlock", data={"code": "nope"}).status_code == 401  # not 404/redirect


def test_gate_off_leaves_everything_open(monkeypatch):
    monkeypatch.delenv("REHEARSAL_ACCESS_CODE", raising=False)
    client = TestClient(appmod.app)
    assert client.get("/api/tracks").status_code == 200  # today's behavior
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_gate.py -v`
Expected: FAIL — `/api/tracks` returns 200 (no gate) and `/api/unlock` 404 (route missing).

- [ ] **Step 3: Create `web/static/gate.html`** (self-contained — renders even though everything else is gated):

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>rehearsal — access</title>
  <style>
    body { font-family: "Hanken Grotesk", system-ui, sans-serif; background: #f5eede;
      color: #33302a; min-height: 100vh; margin: 0; display: grid; place-items: center; }
    .box { background: #fffbf3; border: 1px solid #e8ddc9; border-radius: 24px;
      padding: 2.4rem 2.2rem; box-shadow: 0 18px 48px rgba(120,90,60,.12); width: 320px; text-align: center; }
    h1 { font-family: Georgia, serif; font-weight: 600; font-size: 1.5rem; margin: 0 0 .3rem; }
    p { color: #6c6256; font-size: .92rem; margin: 0 0 1.4rem; }
    input { width: 100%; box-sizing: border-box; font-size: 1rem; padding: .7rem .8rem;
      border: 1px solid #e8ddc9; border-radius: 12px; background: #f7efe1; text-align: center; }
    button { margin-top: .9rem; width: 100%; font-weight: 700; font-size: 1rem; color: #fff;
      background: #c5694a; border: 0; border-radius: 999px; padding: .8rem; cursor: pointer; }
    .err { color: #b91c1c; font-size: .85rem; min-height: 1.1rem; margin-top: .7rem; }
  </style>
</head>
<body>
  <div class="box">
    <h1>rehearsal</h1>
    <p>Enter your access code to continue.</p>
    <form id="f">
      <input id="code" type="password" autocomplete="off" placeholder="access code" autofocus />
      <button type="submit">Unlock</button>
      <div class="err" id="err"></div>
    </form>
  </div>
  <script>
    document.getElementById("f").addEventListener("submit", async (e) => {
      e.preventDefault();
      const err = document.getElementById("err");
      err.textContent = "";
      const body = new FormData();
      body.append("code", document.getElementById("code").value);
      const resp = await fetch("/api/unlock", { method: "POST", body });
      if (resp.ok) { window.location.reload(); }
      else { err.textContent = "That code didn't work — try again."; }
    });
  </script>
</body>
</html>
```

- [ ] **Step 4: Edit `web/app.py`** — add the imports, the unlock route, and the gate middleware.

Add to the imports near the top:
```python
import asyncio

from fastapi.responses import FileResponse
from web import auth
```
Add the unlock route (place it with the other routes, e.g. right after `get_config`):
```python
@app.post("/api/unlock")
async def unlock(code: str = Form(...)):
    if auth.check_code(code):
        resp = JSONResponse({"ok": True})
        resp.set_cookie(auth.COOKIE_NAME, auth.make_token(), httponly=True,
                        samesite="lax", secure=auth.cookie_secure(),
                        max_age=auth.COOKIE_MAX_AGE)
        return resp
    await asyncio.sleep(auth.unlock_delay())
    raise HTTPException(status_code=401, detail="Invalid code.")
```
Add the gate middleware. It must be defined AFTER `app = FastAPI(...)` and the open-path set; placing it just before the final `app.mount(...)` is fine:
```python
GATE_OPEN_PATHS = {"/api/unlock", "/gate.html", "/favicon.ico"}


@app.middleware("http")
async def access_gate(request, call_next):
    if not auth.gate_enabled():
        return await call_next(request)
    path = request.url.path
    if path in GATE_OPEN_PATHS:
        return await call_next(request)
    if auth.valid_token(request.cookies.get(auth.COOKIE_NAME)):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "locked"}, status_code=401)
    return FileResponse(BASE / "static" / "gate.html")
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/pytest tests/test_gate.py -v`
Expected: PASS (6 tests). The `REHEARSAL_UNLOCK_DELAY=0` env keeps the failure tests instant.

- [ ] **Step 6: Full suite (gate stays OFF for the existing tests)**

Run: `.venv/bin/pytest -q -k "not ollama"`
Expected: all green. The existing tests never set `REHEARSAL_ACCESS_CODE`, so the middleware is a pass-through for them.

- [ ] **Step 7: Commit**

```bash
git add web/app.py web/static/gate.html tests/test_gate.py
git commit -m "feat: access-code gate middleware + /api/unlock + gate page"
```

---

## Task 3: Document the gate + manual smoke test

**Files:** Modify `README.md`.

- [ ] **Step 1: Add a "Access code (optional gate)" section to `README.md`** (append at the end):

```markdown
## Access code (optional gate)

The app is open by default (local use). Set `REHEARSAL_ACCESS_CODE` to require a shared
code before anyone can use it — a gate page exchanges the code for a signed, HttpOnly cookie
(~30 days). Used for the hosted deployment so only people with the code can get in.

| Env var | Default | Meaning |
|---|---|---|
| `REHEARSAL_ACCESS_CODE` | (unset → gate off) | the shared secret code (use a long random one) |
| `REHEARSAL_SESSION_SECRET` | dev default | signs the cookie — set a real random value when hosting |
| `REHEARSAL_UNLOCK_DELAY` | `3.0` | seconds to wait after a wrong code (brute-force friction) |
| `REHEARSAL_COOKIE_SECURE` | `false` | set `true` when served over HTTPS |

Brute force is resisted primarily by a high-entropy code; the delay + a deploy-time Lambda
concurrency cap are defense-in-depth.
```

- [ ] **Step 2: Manual smoke test** (the gate UI needs a browser)

Run the app with the gate on:
```bash
REHEARSAL_ACCESS_CODE="test-code-123" REHEARSAL_PORT=8743 ./run.sh
```
In a browser at `http://localhost:8743`:
1. Confirm the **gate page** appears (not the app) — an "access code" field.
2. Enter a wrong code → after ~3s, "That code didn't work."
3. Enter `test-code-123` → the page reloads into the real app.
4. The app works normally; refreshing stays unlocked (cookie persists).
Record each result. Then stop the server (`pkill -f "uvicorn web.app:app"`).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: access-code gate env vars"
```

---

## Definition of done

- [ ] `.venv/bin/pytest -q` fully green; the existing suite is unchanged (gate is off without
  `REHEARSAL_ACCESS_CODE`).
- [ ] With `REHEARSAL_ACCESS_CODE` set: unauthed `/api/*` → 401, unauthed page loads → the gate
  page, `/api/unlock` with the right code sets a signed cookie and opens the app, wrong code →
  ~3s delay then 401. Constant-time code compare; tamper/wrong-secret tokens rejected.
- [ ] `engine/` untouched (this is web-layer only); the gate is fully opt-in via env.
- [ ] Real deployment wiring (the code + session secret in SSM, `REHEARSAL_COOKIE_SECURE=true`,
  the concurrency cap) is deferred to the deploy sub-project (#3).
```
