import json

from engine import llm
from engine.llm_openai import OpenAIChatClient


def test_default_provider_is_ollama(monkeypatch):
    monkeypatch.delenv("REHEARSAL_LLM_PROVIDER", raising=False)
    assert llm.provider() == "ollama"


def test_default_model_is_provider_aware(monkeypatch):
    monkeypatch.delenv("REHEARSAL_LLM_MODEL", raising=False)
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "ollama")
    assert llm.default_model() == "qwen2.5:7b"
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "openai")
    assert llm.default_model() == "gpt-4o"


def test_default_model_env_override(monkeypatch):
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "openai")
    monkeypatch.setenv("REHEARSAL_LLM_MODEL", "gpt-4o-mini")
    assert llm.default_model() == "gpt-4o-mini"


def test_get_client_openai(monkeypatch):
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "openai")
    assert isinstance(llm.get_client(), OpenAIChatClient)


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


def test_openai_chat_shape_and_json_mode(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    payload = {"choices": [{"message": {"content": "{\"level\": \"Novice-High\"}"}}]}
    http = FakeHTTP(payload)
    client = OpenAIChatClient(client=http)
    out = client.chat(model="gpt-4o",
                      messages=[{"role": "user", "content": "hi"}],
                      format="json")
    assert out == {"message": {"content": "{\"level\": \"Novice-High\"}"}}
    assert http.call["json"]["model"] == "gpt-4o"
    assert http.call["json"]["response_format"] == {"type": "json_object"}
    assert http.call["headers"]["Authorization"] == "Bearer sk-test"
