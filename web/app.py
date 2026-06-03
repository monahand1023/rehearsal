import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from engine.report import analyze_answer

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
    run_content: bool = Form(True),
):
    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        report = analyze_answer(tmp_path, question, run_content=run_content)
    finally:
        os.unlink(tmp_path)
    return JSONResponse(report)


# Serve the frontend (index.html etc.). Mounted last so /api routes win.
app.mount("/", StaticFiles(directory=str(BASE / "static"), html=True), name="static")
