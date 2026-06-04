from engine.transcribe_openai import transcribe_openai


class FakeResp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


class FakeHTTP:
    def __init__(self, payload):
        self._payload = payload
        self.call = None
    def post(self, url, **kw):
        self.call = {"url": url, **kw}
        return FakeResp(self._payload)


def test_transcribe_openai_builds_transcript(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFxxxx")
    payload = {
        "text": "hello world",
        "language": "english",
        "duration": 1.5,
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
        ],
    }
    http = FakeHTTP(payload)
    tr = transcribe_openai(str(audio), language="en", client=http)
    assert tr.text == "hello world"
    assert len(tr.words) == 2
    assert tr.words[0].text == "hello"
    assert tr.words[0].probability == 1.0   # OpenAI gives no per-word confidence
    assert tr.duration == 1.5
    assert tr.language == "en"   # ISO code, not OpenAI's full-name "english"
    assert http.call["data"]["model"] == "whisper-1"


def test_transcribe_openai_returns_iso_language_not_full_name(tmp_path, monkeypatch):
    # OpenAI's verbose_json returns the full language NAME ("japanese"), but the rest of the
    # pipeline keys off ISO codes ("ja") — e.g. the Japanese filler detector. The transcript
    # must carry the requested ISO code so those branches actually run.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFxxxx")
    payload = {"text": "あの、はい", "language": "japanese", "duration": 1.0,
               "words": [{"word": "あの", "start": 0.0, "end": 0.4}]}
    tr = transcribe_openai(str(audio), language="ja", client=FakeHTTP(payload))
    assert tr.language == "ja"


def test_transcribe_openai_drops_prompt_echo(tmp_path, monkeypatch):
    # On near-silent/short audio Whisper can parrot the priming prompt back; that must not
    # turn into phantom fillers — blank the transcript.
    from engine.transcribe_openai import FILLER_PROMPTS
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFxxxx")
    payload = {"text": FILLER_PROMPTS["ja"], "language": "japanese", "duration": 1.0,
               "words": [{"word": "えーと", "start": 0.0, "end": 0.4}]}
    tr = transcribe_openai(str(audio), language="ja", client=FakeHTTP(payload))
    assert tr.text == "" and tr.words == []


def test_transcribe_openai_keeps_real_speech_with_fillers(tmp_path, monkeypatch):
    # A real answer that merely CONTAINS a filler must NOT be mistaken for an echo.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFxxxx")
    payload = {"text": "あの、週末は楽しかったです。", "language": "japanese", "duration": 2.0,
               "words": [{"word": "あの", "start": 0.0, "end": 0.4}]}
    tr = transcribe_openai(str(audio), language="ja", client=FakeHTTP(payload))
    assert tr.text.startswith("あの、週末")


def test_transcribe_openai_empty_words(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFxxxx")
    tr = transcribe_openai(str(audio), language="ja",
                           client=FakeHTTP({"text": "", "duration": 0.0, "words": []}))
    assert tr.words == []
    assert tr.duration == 0.0
