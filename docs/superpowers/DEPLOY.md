# rehearsal — Deploy Runbook

Live (gated JP/STAMP practice): a pure-Python **zip** Lambda behind a Function URL.
Region `us-west-2`. **No Docker** — `sam build` uses a Makefile that installs linux/arm64
wheels directly. Cloud runs in "lite" mode (no ffmpeg/parselmouth): audio goes straight to
the OpenAI Whisper API; prosody (Expression) + acoustic fillers are skipped.

## Architecture
- `template.yaml` — SAM zip Lambda (`Runtime python3.12`, `arm64`), Function URL (public),
  reserved concurrency 5, 60s timeout. Env: `REHEARSAL_AUDIO_NATIVE=false`, providers=openai,
  `REHEARSAL_COOKIE_SECURE=true`, secrets via NoEcho params.
- `Makefile` — the `build-RehearsalFn` target (platform-pip + copy engine/web/questions).
- `web/lambda_handler.py` — Mangum adapter.

## Secrets (SSM SecureString, `/rehearsal/`)
`openai-api-key`, `elevenlabs-api-key`, `access-code`, `session-secret`. Set/rotate with:
```
OPENAI_API_KEY='sk-...' ACCESS_CODE='<code>' bash scripts/put_secrets.sh
```

## Deploy / update
```
bash scripts/deploy.sh        # sam build + sam deploy, sources secrets from SSM, prints the URL
```

## Rotate the access code
```
ACCESS_CODE='new-code' OPENAI_API_KEY="$(aws ssm get-parameter --name /rehearsal/openai-api-key --with-decryption --query Parameter.Value --output text --region us-west-2)" bash scripts/put_secrets.sh
bash scripts/deploy.sh        # re-passes the new code into the Lambda env
```

## Teardown
```
sam delete --stack-name rehearsal --region us-west-2
```

## Cost guards
- **Reserved concurrency 5** (in the stack) bounds the spend *rate* — at most 5 Lambdas at once.
- **AWS Budget `rehearsal-monthly`** — $50/mo, emails you@example.com at 80% actual and
  100% forecasted. Managed *outside* the stack (so deploys don't need budgets perms): the IAM
  user got `budgets:*` via the `RehearsalOps` group + `RehearsalBudgetsManage` managed policy
  (the user's own inline/managed-policy slots were full). Adjust the limit with
  `aws budgets update-budget --account-id YOUR_AWS_ACCOUNT_ID --new-budget '{...}'`.

## Notes
- `samconfig.toml` + `.aws-sam/` are gitignored (samconfig can hold NoEcho param values).
