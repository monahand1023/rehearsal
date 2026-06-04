#!/usr/bin/env bash
# Store the OPTIONAL cloud-deploy secrets in SSM (SecureString). Only needed if you deploy to
# AWS (see docs/superpowers/DEPLOY.md) — local use needs none of this. Run once (and to rotate):
#   OPENAI_API_KEY='sk-...' ACCESS_CODE='<long random code>' [ELEVENLABS_API_KEY='...'] bash scripts/put_secrets.sh
set -euo pipefail
REGION="${AWS_REGION:-us-west-2}"
: "${OPENAI_API_KEY:?set OPENAI_API_KEY before running}"
: "${ACCESS_CODE:?set ACCESS_CODE before running}"
SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
put() { aws ssm put-parameter --name "$1" --value "$2" --type SecureString \
        --overwrite --region "$REGION" >/dev/null; echo "  set $1"; }
put /rehearsal/openai-api-key     "$OPENAI_API_KEY"
put /rehearsal/access-code        "$ACCESS_CODE"
put /rehearsal/session-secret     "$SESSION_SECRET"
# ElevenLabs is optional (cloud TTS); skip it to use the browser voice instead.
[ -n "${ELEVENLABS_API_KEY:-}" ] && put /rehearsal/elevenlabs-api-key "$ELEVENLABS_API_KEY"
echo "done — secrets stored encrypted in SSM under /rehearsal/."
