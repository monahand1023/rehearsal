#!/usr/bin/env bash
# rehearsal launcher — start the local app with sensible defaults.
#   ./run.sh                  # default port 8000, model qwen2.5:7b
#   REHEARSAL_PORT=8080 ./run.sh
#   REHEARSAL_LLM_MODEL=qwen2.5:14b-instruct ./run.sh
set -uo pipefail
cd "$(dirname "$0")"

VENV=".venv/bin"
# Dedicated port so rehearsal never shares a localhost origin (and its service
# workers / caches) with other projects. Auto-bumps if something's already there.
PORT="${REHEARSAL_PORT:-8742}"
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  for p in $(seq "$PORT" $((PORT + 25))); do
    if ! lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then PORT="$p"; break; fi
  done
fi
export REHEARSAL_LLM_MODEL="${REHEARSAL_LLM_MODEL:-qwen2.5:7b}"

echo "rehearsal —"

# --- Ollama + model (content / proficiency / coach feedback) ---
# (substring test, not `ollama list | grep -q`: pipefail + grep's early exit would
#  SIGPIPE `ollama list` and falsely report the model missing.)
if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  _models="$(ollama list 2>/dev/null)"
  if [[ "$_models" == *"$REHEARSAL_LLM_MODEL"* ]]; then
    echo "  ✓ Ollama up, model '$REHEARSAL_LLM_MODEL' ready"
  else
    echo "  ⚠ model '$REHEARSAL_LLM_MODEL' not installed — run:  ollama pull $REHEARSAL_LLM_MODEL"
    echo "    (delivery/clarity still work; content & coach feedback will error until pulled)"
  fi
else
  echo "  ⚠ Ollama not reachable at :11434 — start it first (content & coach feedback need it)"
fi

# --- ElevenLabs voice (optional; only the short coach summary text is ever sent) ---
if [ -z "${ELEVENLABS_API_KEY:-}" ]; then
  KEY="$(aws ssm get-parameter --name /your-project/elevenlabs-api-key \
        --with-decryption --query Parameter.Value --output text --region us-west-2 2>/dev/null || true)"
  if [ -n "$KEY" ]; then
    export ELEVENLABS_API_KEY="$KEY"
    echo "  ✓ ElevenLabs key loaded from SSM (spoken feedback enabled)"
  else
    echo "  ℹ no ElevenLabs key — spoken feedback disabled (on-screen text still shown)"
  fi
fi
# Chosen English + native Japanese coach voices, overridable via env.
export ELEVENLABS_VOICE_EN="${ELEVENLABS_VOICE_EN:-UgBBYS2sOqTuMpoF3BR0}"
export ELEVENLABS_VOICE_JA="${ELEVENLABS_VOICE_JA:-MXKtCrra8fvlDUbfKUT1}"

echo "  ▶ http://localhost:$PORT   (mode picker: Interview Coach / Japanese Practice)"
echo ""
( sleep 1.5; open "http://localhost:$PORT" >/dev/null 2>&1 || true ) &
exec "$VENV/uvicorn" web.app:app --port "$PORT"
