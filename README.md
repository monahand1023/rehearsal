# rehearsal

A local web app for practicing spoken answers and getting AI feedback — entirely on your
machine (audio never leaves it; only an optional short coach summary is sent to ElevenLabs
for the spoken voice).

Two modes, one app:

- **Interview Coach** (English) — record an answer to a behavioral/leadership question; get
  feedback on delivery (pace, pauses, fillers, monotone), clarity, and content (did you
  answer it, STAR structure, conciseness) plus a warm spoken coaching summary.
- **Japanese Practice** (free-response) — record an answer to a STAMP-style prompt; get the
  same delivery/clarity feedback plus an ACTFL-style **proficiency estimate** (level, task
  completion, grammar, vocabulary, coherence). A practice estimate, **not** an official score.

## Run it

Double-click **`rehearsal.command`** in Finder (or keep it in the Dock), or from a terminal:

```bash
./run.sh
```

Either way it fetches the optional ElevenLabs key, checks Ollama, and opens the app
(default `http://localhost:8742`, auto-bumping if that port is busy). Pick a **Mode**, pick a
**Question**, click the **record orb**, speak, click it again to **stop**, then **Get feedback**.

Overrides:

```bash
REHEARSAL_PORT=9000 ./run.sh
REHEARSAL_LLM_MODEL=qwen2.5:14b-instruct ./run.sh    # richer (slower)
ELEVENLABS_VOICE_JA=<voice-id> ./run.sh              # override the JP voice
```

## Requirements

- **Python venv** — already set up at `.venv` (`pip install -r requirements.txt` to recreate).
- **ffmpeg** — on PATH (audio conversion).
- **Ollama** — running, with the content model pulled: `ollama pull qwen2.5:7b`. Used for the
  interview/proficiency analysis and the coach summary. Without it, delivery + clarity still
  work but content/coach feedback errors.
- **Optional — ElevenLabs voice:** spoken feedback turns on when `ELEVENLABS_API_KEY` is set.
  `run.sh` pulls it from AWS SSM (`/your-project/elevenlabs-api-key`) if you have AWS
  creds; otherwise set it yourself. Without a key, the coach summary still shows as text.
  Voices default to a warm English voice and a native Japanese voice (per mode), overridable
  via `ELEVENLABS_VOICE_EN` / `ELEVENLABS_VOICE_JA`.

## Model choice

The content/proficiency/coach model defaults to **`qwen2.5:7b`** (`REHEARSAL_LLM_MODEL`).
Benchmarked on an M4 Pro against `llama3.1:8b` and `qwen2.5:14b-instruct`: 7B was ~2× faster
and, crucially, actually reads Japanese (llama3.1 hallucinated grammar errors on clean
Japanese). `qwen2.5:14b-instruct` gives marginally richer English coaching at ~2× the latency.

## Testing

```bash
.venv/bin/pytest -q                          # full suite (88 tests)
.venv/bin/pytest --cov --cov-report=term     # coverage (~98%)
.venv/bin/pytest -k "not ollama" -q          # skip the slow LLM end-to-end tests
```

Integration tests run the real engine on committed ElevenLabs fixtures
(`tests/fixtures/generated/`). Regenerate them with `scripts/gen_test_audio.py` (needs the
ElevenLabs key).

## Known limitations

- **Filler detection** — reliable filler counting is the weakest component. Recall on cleanly
  synthesized speech is low, and the acoustic detector is tuned to favor precision (avoid
  false positives) over recall. Real-world tuning needs natural human recordings. See
  `docs/superpowers/fillers-spike.md`.
- **Japanese pace** reads high — Whisper segments Japanese into short "words", so words/minute
  is inflated; the coach treats it as approximate.
- **Proficiency** is an LLM practice estimate, not an official STAMP score.

## Layout

```
engine/   # standalone analysis engine (no web deps): transcribe, delivery, fillers,
          # prosody, clarity, content, proficiency, coach, tts, report
web/      # FastAPI server + vanilla-JS frontend (static/)
questions/# question libraries per track (interview_en, language_jp)
tests/    # unit + integration tests, audio fixtures
docs/superpowers/  # specs and implementation plans
```

## Cloud providers (for hosting)

By default everything runs locally (faster-whisper + Ollama). To run without local
models — e.g. on a server — set:

| Env var | Values | Effect |
|---|---|---|
| `REHEARSAL_TRANSCRIBE_PROVIDER` | `local` (default) / `openai` | Whisper via faster-whisper vs the OpenAI Whisper API |
| `REHEARSAL_LLM_PROVIDER` | `ollama` (default) / `openai` | rubric/coach via Ollama vs OpenAI |
| `REHEARSAL_LLM_MODEL` | (optional) | overrides the provider's default model |
| `OPENAI_API_KEY` | — | required when either provider is `openai` |

With both set to `openai`, the engine needs neither `faster-whisper` nor `ollama`
installed (`requirements-cloud.txt`); parselmouth + ElevenLabs are unchanged.
Note: the OpenAI Whisper API returns word timestamps but no per-word confidence, so
the clarity proxy is less precise on the cloud provider.

## Access code (optional gate)

The app is open by default (local use). Set `REHEARSAL_ACCESS_CODE` to require a shared
code before anyone can use it — a gate page exchanges the code for a signed, HttpOnly cookie
(~30 days). Used for the hosted deployment so only people with the code can get in.

| Env var | Default | Meaning |
|---|---|---|
| `REHEARSAL_ACCESS_CODE` | (unset → gate off) | the shared secret code (use a long random one) |
| `REHEARSAL_SESSION_SECRET` | dev default | signs the cookie — set a real random value when hosting |
| `REHEARSAL_UNLOCK_DELAY` | `3.0` | seconds to wait after a wrong code (brute-force friction) |
| `REHEARSAL_COOKIE_SECURE` | `false` | set `true` when served over HTTPS |

Brute force is resisted primarily by a high-entropy code; the delay + a deploy-time Lambda
concurrency cap are defense-in-depth.
