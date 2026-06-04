#!/usr/bin/env bash
# Build + deploy rehearsal to AWS (Lambda + Function URL). Reads secrets from SSM — set them
# once with scripts/put_secrets.sh — and passes them as NoEcho stack parameters.
#   bash scripts/deploy.sh
# Env overrides: AWS_REGION (default us-west-2), REHEARSAL_STACK (default rehearsal).
set -euo pipefail
cd "$(dirname "$0")/.."
REGION="${AWS_REGION:-us-west-2}"
STACK="${REHEARSAL_STACK:-rehearsal}"

# --- prerequisites ---
command -v aws >/dev/null || { echo "✗ aws CLI not found — install it first."; exit 1; }
command -v sam >/dev/null || { echo "✗ AWS SAM CLI not found — install: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"; exit 1; }
aws sts get-caller-identity >/dev/null 2>&1 || { echo "✗ AWS credentials not configured — run 'aws configure' or set AWS_PROFILE."; exit 1; }

# --- secrets (set once with scripts/put_secrets.sh) ---
get() { aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text --region "$REGION" 2>/dev/null; }
OPENAI="$(get /rehearsal/openai-api-key)" || true
ACCESS="$(get /rehearsal/access-code)" || true
SESSION="$(get /rehearsal/session-secret)" || true
if [ -z "${OPENAI:-}" ] || [ -z "${ACCESS:-}" ] || [ -z "${SESSION:-}" ]; then
  echo "✗ required secrets missing in SSM (region $REGION). Set them once with:"
  echo "    OPENAI_API_KEY='sk-...' ACCESS_CODE='<long random code>' bash scripts/put_secrets.sh"
  exit 1
fi
ELEVEN="$(get /rehearsal/elevenlabs-api-key)" || true   # optional — cloud falls back to the browser voice

echo "Deploying stack '$STACK' to $REGION …"
sam build
sam deploy --stack-name "$STACK" --region "$REGION" --resolve-s3 \
  --capabilities CAPABILITY_IAM --no-confirm-changeset \
  --parameter-overrides \
    "OpenAIApiKey=$OPENAI" \
    "ElevenLabsApiKey=${ELEVEN:-}" \
    "AccessCode=$ACCESS" \
    "SessionSecret=$SESSION"
echo ""
echo "App URL:"
aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionUrl'].OutputValue" --output text
