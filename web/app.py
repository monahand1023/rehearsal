import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from engine.report import analyze_answer
from engine.tts import config as tts_config
from engine.tts.base import TTSError
from engine.tts.elevenlabs import ElevenLabsProvider

BASE = Path(__file__).resolve().parent
QUESTIONS_DIR = BASE.parent / "questions"

app = FastAPI(title="rehearsal")


@app.get("/api/questions")
def get_questions(track: str = "interview_en"):
    path = QUESTIONS_DIR / f"{track}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"unknown track: {track}")
    return json.loads(path.read_text())


@app.post("/api/analyze")
async def analyze(
    question: str = Form(...),
    audio: UploadFile = File(...),
    language: str = Form("en"),
    run_content: bool = Form(True),
):
    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        report = analyze_answer(tmp_path, question, language=language,
                                run_content=run_content)
    finally:
        os.unlink(tmp_path)
    return JSONResponse(report)


@app.get("/api/config")
def get_config():
    return {"tts_enabled": tts_config.is_available()}


@app.post("/api/speak")
async def speak(text: str = Form(...), language: str = Form("en")):
    if not tts_config.is_available():
        raise HTTPException(status_code=503, detail="TTS not configured")
    try:
        audio = ElevenLabsProvider().synthesize(text, language)
    except TTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return Response(content=audio, media_type="audio/mpeg")


# Serve the frontend (index.html etc.). Mounted last so /api routes win.
app.mount("/", StaticFiles(directory=str(BASE / "static"), html=True), name="static")
