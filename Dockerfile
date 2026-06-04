# rehearsal — local, private speaking practice. Runs the full native pipeline
# (faster-whisper + parselmouth + ffmpeg); pair with the Ollama service in docker-compose.yml.
# Coach voice is the browser's Web Speech API by default, so no TTS deps are needed here.
FROM python:3.12-slim

# ffmpeg = audio decoding; build-essential covers any wheel that needs compiling.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ engine/
COPY web/ web/
COPY questions/ questions/

# faster-whisper downloads its model on first use into the HF cache; persist it via a volume.
ENV HF_HOME=/cache/huggingface \
    REHEARSAL_PORT=8742
EXPOSE 8742

CMD ["sh", "-c", "uvicorn web.app:app --host 0.0.0.0 --port ${REHEARSAL_PORT}"]
