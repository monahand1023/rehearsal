import asyncio
import json
import logging
import os
import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from web import auth

from engine.audio import probe_duration
from engine.report import analyze_answer
from engine.constants import LANG_EN, MODE_INTERVIEW
from engine.tts import config as tts_config
from engine.tts.base import TTSError
from web.storage import save_attempt

BASE = Path(__file__).resolve().parent
QUESTIONS_DIR = BASE.parent / "questions"
log = logging.getLogger("rehearsal")

# Abuse guardrails (overridable via env). The app has no per-request auth, so these
# server-side caps are the real protection against cost abuse — the client-side limits
# only protect honest users, not someone POSTing straight at the API.
TRACK_RE = re.compile(r"^[a-z0-9_]+$")
AUDIO_SUFFIXES = {".webm", ".wav", ".mp3", ".mp4", ".m4a", ".ogg", ".oga", ".aiff", ".flac"}


def _max_upload_bytes() -> int:
    return int(os.environ.get("REHEARSAL_MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))


def _max_audio_seconds() -> float:
    return float(os.environ.get("REHEARSAL_MAX_AUDIO_SECONDS", "360"))  # 6 min


def _audio_native() -> bool:
    return os.environ.get("REHEARSAL_AUDIO_NATIVE", "true").lower() == "true"


def _allowed_tracks():
    """Set of track names to expose, or None for all. Lets the cloud deploy show only
    Japanese (REHEARSAL_TRACKS=language_jp) while local keeps every track."""
    raw = os.environ.get("REHEARSAL_TRACKS", "").strip()
    if not raw:
        return None
    return {t.strip() for t in raw.split(",") if t.strip()}


def _max_tts_chars() -> int:
    return int(os.environ.get("REHEARSAL_MAX_TTS_CHARS", "2000"))


app = FastAPI(title="rehearsal")


class NoCacheStaticFiles(StaticFiles):
    """Serve the frontend with revalidate-always caching. Without this, browsers
    apply heuristic freshness to last-modified-only responses and can serve a stale
    recorder.js/results.js for minutes — confusing while the UI is iterated on."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response



@app.get("/api/questions")
def get_questions(track: str = "interview_en"):
    if not TRACK_RE.match(track):  # reject path traversal / arbitrary file reads
        raise HTTPException(status_code=404, detail="unknown track")
    allowed = _allowed_tracks()
    if allowed is not None and track not in allowed:
        raise HTTPException(status_code=404, detail="unknown track")
    path = QUESTIONS_DIR / f"{track}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"unknown track: {track}")
    return json.loads(path.read_text())


@app.post("/api/analyze")
async def analyze(
    question: str = Form(...),
    audio: UploadFile = File(...),
    language: str = Form(LANG_EN),
    mode: str = Form(MODE_INTERVIEW),
    run_content: bool = Form(True),
    category: str = Form(""),
):
    # Size cap first (reads at most max+1 bytes — never ingests a giant file).
    max_bytes = _max_upload_bytes()
    data = await audio.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="Recording is too large.")

    ext = os.path.splitext(audio.filename or "")[1].lower()
    suffix = ext if ext in AUDIO_SUFFIXES else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        # Duration cap uses ffprobe (native only). In cloud "lite" mode the size cap above
        # is the bound (and stays well under the Whisper API's own 25 MB limit).
        if _audio_native() and probe_duration(tmp_path) > _max_audio_seconds():
            raise HTTPException(status_code=413, detail="Recording is too long.")
        report = analyze_answer(tmp_path, question, language=language, mode=mode,
                                run_content=run_content, category=category)
    finally:
        os.unlink(tmp_path)
    try:
        save_attempt(data, suffix, report, mode=mode, language=language)
    except Exception:
        # best-effort archival; never fail the user's feedback — but don't lose the training
        # corpus silently: a persistent IAM/bucket misconfig should be visible in the logs.
        log.warning("recording archival to S3 failed", exc_info=True)
    return JSONResponse(report)


@app.get("/api/config")
def get_config():
    # tts_mode tells the frontend whether to POST /api/speak (server: ElevenLabs/Piper) or
    # speak locally via the browser's Web Speech API (the zero-config, fully-local default).
    p = tts_config.provider()
    return {"tts_enabled": tts_config.is_available(),
            "tts_mode": "browser" if p == "browser" else "server"}


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


@app.post("/api/speak")
async def speak(text: str = Form(...), language: str = Form(LANG_EN)):
    if len(text) > _max_tts_chars():  # cap before hitting the per-character TTS bill
        raise HTTPException(status_code=413, detail="Text is too long.")
    synth = tts_config.server_synthesizer()
    if synth is None:  # browser-TTS mode — the client speaks locally, nothing to do here
        raise HTTPException(status_code=503, detail="TTS handled by the browser")
    try:
        audio = synth.synthesize(text, language)
    except TTSError:
        raise HTTPException(status_code=502, detail="Voice generation failed.")
    return Response(content=audio, media_type=synth.media_type)


@app.get("/api/tracks")
def get_tracks():
    allowed = _allowed_tracks()
    tracks = []
    for path in sorted(QUESTIONS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        if allowed is not None and data["track"] not in allowed:
            continue
        tracks.append({"track": data["track"], "language": data["language"],
                       "mode": data.get("mode", MODE_INTERVIEW),
                       "count": len(data.get("questions", []))})
    return {"tracks": tracks}


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


# Serve the frontend (index.html etc.). Mounted last so /api routes win.
app.mount("/", NoCacheStaticFiles(directory=str(BASE / "static"), html=True), name="static")
