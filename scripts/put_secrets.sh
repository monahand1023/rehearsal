#!/usr/bin/env bash
# Store rehearsal's secrets in SSM (SecureString). Run once (and to rotate).
#   OPENAI_API_KEY='sk-...' ACCESS_CODE='<long random code>' bash scripts/put_secrets.sh
set -euo pipefail
REGION=us-west-2
: "${OPENAI_API_KEY:?set OPENAI_API_KEY before running}"
: "${ACCESS_CODE:?set ACCESS_CODE before running}"
SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
ELEVEN="$(aws ssm get-parameter --name /your-project/elevenlabs-api-key \
          --with-decryption --query Parameter.Value --output text --region "$REGION")"
put() { aws ssm put-parameter --name "$1" --value "$2" --type SecureString \
        --overwrite --region "$REGION" >/dev/null; echo "  set $1"; }
put /rehearsal/openai-api-key     "$OPENAI_API_KEY"
put /rehearsal/elevenlabs-api-key "$ELEVEN"
put /rehearsal/access-code        "$ACCESS_CODE"
put /rehearsal/session-secret     "$SESSION_SECRET"
echo "done — secrets stored encrypted in SSM under /rehearsal/."
