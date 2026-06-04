#!/usr/bin/env bash
# One-command local setup for rehearsal: Python venv + deps, and an Ollama/model check.
# Everything runs on your machine — see the Privacy section of the README.
set -uo pipefail
cd "$(dirname "$0")"

echo "rehearsal setup —"

# 1. ffmpeg (audio decoding)
if command -v ffmpeg >/dev/null 2>&1; then
  echo "  ✓ ffmpeg"
else
  echo "  ⚠ ffmpeg not found — install it:  macOS: brew install ffmpeg   ·   Debian/Ubuntu: sudo apt install ffmpeg"
fi

# 2. Python venv + dependencies
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✗ python3 not found — install Python 3.11+ first"; exit 1
fi
if [ ! -d .venv ]; then
  echo "  • creating .venv"; python3 -m venv .venv
fi
echo "  • installing Python dependencies"
./.venv/bin/pip install -q --upgrade pip >/dev/null
if ./.venv/bin/pip install -q -r requirements.txt; then
  echo "  ✓ Python dependencies"
else
  echo "  ✗ pip install failed — see the error above"; exit 1
fi

# 3. Ollama + the content model
MODEL="${REHEARSAL_LLM_MODEL:-qwen2.5:7b}"
if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "${MODEL%%:*}"; then
    echo "  ✓ Ollama + model '$MODEL'"
  else
    echo "  • pulling '$MODEL' (one-time download)"
    ollama pull "$MODEL" && echo "  ✓ model ready"
  fi
else
  echo "  ⚠ Ollama not found — install from https://ollama.com, then:  ollama pull $MODEL"
fi

echo ""
echo "Done. Start the app with:  ./run.sh   (then open the printed http://localhost URL)"
echo "The coach voice works in your browser by default — no keys, nothing leaves your machine."
