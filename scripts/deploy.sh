#!/usr/bin/env bash
# Build + deploy rehearsal to AWS (sources secrets from SSM, passes as NoEcho params).
set -euo pipefail
REGION=us-west-2
get() { aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text --region "$REGION"; }
sam build
sam deploy --stack-name rehearsal --region "$REGION" --resolve-s3 \
  --capabilities CAPABILITY_IAM --no-confirm-changeset \
  --parameter-overrides \
    "OpenAIApiKey=$(get /rehearsal/openai-api-key)" \
    "ElevenLabsApiKey=$(get /rehearsal/elevenlabs-api-key)" \
    "AccessCode=$(get /rehearsal/access-code)" \
    "SessionSecret=$(get /rehearsal/session-secret)"
echo ""
aws cloudformation describe-stacks --stack-name rehearsal --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionUrl'].OutputValue" --output text
