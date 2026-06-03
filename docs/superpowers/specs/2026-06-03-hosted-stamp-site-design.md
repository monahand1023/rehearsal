# Hosted STAMP Site — Design

**Date:** 2026-06-03
**Status:** Approved (design); building in sub-projects
**Scope:** Put the **Japanese / STAMP practice mode only** online for a small trusted group,
architected to grow. The interview/English mode stays local-only and is not exposed.

## Goals

- Let a few selected people (Dan's son + classmates) use the Japanese STAMP practice tool
  from their own browsers, without installing Python/Ollama/ffmpeg.
- Keep it cheap, simple, and low-maintenance. No always-on servers, no database.
- Protect against cost abuse and casual access, given there are no per-user accounts.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Audience / scale | Start small (a handful of users), built to grow. Phase 2 (public signup) is later. |
| Processing | **Cloud APIs** — transcription via a Whisper API, the proficiency rubric via an LLM API; parselmouth (prosody) runs in-process; ElevenLabs for voice. No GPU to manage. |
| Hosting | **AWS, serverless** — one container Lambda behind a **Lambda Function URL** (AWS-assigned HTTPS). No App Runner, no RDS, no Route 53, no custom domain. |
| Access control | **Shared access-code gate** (not Google OAuth). One secret code, entered on a gate page, exchanged for a signed cookie. |
| Persistence | **Stateless v1 — store nothing.** No history, no recordings retained. (DynamoDB-backed progress history is a clean later add-on.) |
| Providers | Recommend **OpenAI for both** transcription (Whisper API, word timestamps) and the rubric LLM (GPT-4o) to minimize accounts; Claude is a swappable alternative for the rubric. ElevenLabs unchanged. |

## Architecture

```
Browser  (gate page → access code → JP/STAMP app)
  │  HTTPS (cookie required for app + /api/*)
  ▼
Lambda Function URL ──► ONE container Lambda (existing FastAPI app via an ASGI adapter;
                          bundles ffmpeg + parselmouth)
                          ├─ GET /            → gate page if no valid cookie, else the app
                          ├─ POST /api/unlock → constant-time check vs. code in SSM → signed cookie
                          └─ POST /api/analyze (cookie-gated):
                               audio → Whisper API (transcript + word timestamps)
                                     → parselmouth (prosody, in-process)
                                     → LLM API (FACT proficiency rubric)
                                     → ElevenLabs (coach voice, via /api/speak)
   No database · no S3-for-data · no domain · scale-to-zero · pay-per-request
```

The **same FastAPI app runs locally (uvicorn) and in Lambda** (via an ASGI→Lambda adapter),
so local development is unchanged; deployment only wraps it.

## Access-code gate

- A gate page with a single "access code" field is served to anyone without a valid cookie.
- `POST /api/unlock {code}` compares the submission against the secret code in SSM using a
  **constant-time** comparison (`hmac.compare_digest`). On success it sets a **signed,
  HttpOnly, Secure, SameSite=Lax cookie** (~30-day expiry) — stateless, no DB, unforgeable.
- The app page and every `/api/*` route (except `/api/unlock` and static gate assets)
  require a valid cookie; otherwise they return to the gate / 401.
- The code lives in SSM and is rotatable to revoke access. The cookie-signing secret is also
  in SSM.

**Brute-force defense (no DB):**
1. **High-entropy code (primary defense)** — a 16+ char random code / passphrase makes online
   guessing infeasible regardless of rate limiting.
2. **Constant-time comparison** — no timing side-channel.
3. **~3-second delay on every failed unlock** (configurable) — makes automation glacial.
4. **Lambda reserved concurrency cap** — globally bounds guess rate and total cost.
5. *(Optional later)* CloudFront + AWS WAF rate-based rule for true per-IP throttling, no app
   state needed.

## Abuse guardrails

**Already shipped (server-side, in the API):**
- Reject oversize audio uploads (default 12 MB; read-capped so a huge file is never ingested).
- Reject audio longer than 6 min (ffprobe before any paid Whisper/LLM work).
- Cap `/api/speak` text length (per-character TTS cost).
- Validate the questions `track` param (path-traversal fix); sanitize temp-file suffix; stop
  leaking raw TTS error text. All limits overridable via env.

**Infra (in the deploy sub-project):**
- Lambda reserved concurrency (e.g. 5), 60s timeout, and an AWS Budget alarm emailing Dan if
  monthly spend crosses a threshold.

## Privacy posture

Stateless: recordings are processed and discarded; nothing about a session is stored; no
profiles. A short consent/notice line on the gate page covers that audio is sent to the
processing providers (OpenAI/ElevenLabs) and not retained. This minimal footprint sidesteps
most of the minors/COPPA weight that storing data would incur.

## Decomposition (each its own spec → plan → build)

1. **Cloud processing providers** *(build first — this spec's plan)* — make the engine call
   cloud APIs behind a config switch, keeping local mode the default.
2. **Access-code gate** — gate page, `/api/unlock`, signed cookie, cookie-required middleware.
3. **Deploy** — container Lambda + Function URL, code/keys/secret in SSM, infra guardrails.

## Sub-project #1 — Cloud processing providers (first build)

Make transcription and the LLM pluggable between **local** (today's faster-whisper + Ollama,
the default) and **cloud** (a Whisper API + an LLM API), selected by env config. Local stays
the default so local dev and the whole existing test suite are unchanged; cloud is opt-in.

- **LLM provider** (`engine/llm.py`): returns a chat client implementing the existing
  `.chat(model=, messages=, format=)` shape that `content.py`/`proficiency.py`/`coach.py`
  already accept via their `client=` param. `REHEARSAL_LLM_PROVIDER=ollama|openai|anthropic`.
  Cloud clients call the respective API; tested with a mocked HTTP layer (no real calls).
- **Transcription provider** (`engine/transcribe.py`): local faster-whisper OR a cloud Whisper
  API, returning the same `Transcript` (words with start/end, probability when available).
  `REHEARSAL_TRANSCRIBE_PROVIDER=local|openai`. Note: cloud Whisper may not return per-word
  confidence; when absent, `word.probability` defaults to a neutral value and the clarity
  proxy is correspondingly less precise (documented limitation).
- **Orchestrator** (`engine/report.py`): selects providers from config and passes them through.
- **Keys**: read from env (SSM at deploy), like ElevenLabs today.

**Out of scope for #1:** the gate, the Lambda packaging, any deploy. Those are #2 and #3.

## Non-goals (v1)

- ❌ Google/OAuth accounts (access-code gate instead)
- ❌ Database / stored history / retained recordings
- ❌ Custom domain / Route 53 / App Runner / RDS
- ❌ Exposing the interview/English mode publicly

## Testing

- Provider-selection logic: pure unit tests.
- Cloud LLM + transcription providers: unit-tested against mocked HTTP clients — no real API
  calls, no network in CI.
- Local providers and the existing suite: unchanged and still green (local is the default).
- The gate (#2): unlock success/failure, constant-time compare, cookie set/verify, delay on
  failure, cookie-required routes — all unit-testable locally.
