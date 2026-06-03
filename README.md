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

```bash
./run.sh
```

That fetches the optional ElevenLabs key, checks Ollama, and opens
`http://localhost:8000`. Pick a **Mode**, pick a **Question**, click **Record**, speak,
**Stop**, then **Analyze**.

Overrides:

```bash
REHEARSAL_PORT=8080 ./run.sh
REHEARSAL_LLM_MODEL=qwen2.5:14b-instruct ./run.sh    # richer (slower)
ELEVENLABS_VOICE_JA=<japanese-voice-id> ./run.sh     # natural JP voice
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
