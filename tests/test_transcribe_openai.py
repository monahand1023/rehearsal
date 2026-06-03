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
    assert http.call["data"]["model"] == "whisper-1"


def test_transcribe_openai_empty_words(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFxxxx")
    tr = transcribe_openai(str(audio), language="ja",
                           client=FakeHTTP({"text": "", "duration": 0.0, "words": []}))
    assert tr.words == []
    assert tr.duration == 0.0
