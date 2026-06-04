import json
import os

DEFAULT_MODELS = {"ollama": "qwen2.5:7b", "openai": "gpt-4o"}


def salvage_json(raw: str):
    """LLMs (esp. local Ollama) sometimes wrap JSON in prose or truncate it. Try a strict
    parse, then a brace-substring salvage. Returns the dict, or None if unrecoverable."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def provider() -> str:
    return os.environ.get("REHEARSAL_LLM_PROVIDER", "ollama")


def default_model() -> str:
    return os.environ.get("REHEARSAL_LLM_MODEL") or DEFAULT_MODELS.get(provider(), "qwen2.5:7b")


class OllamaChatClient:
    """Uniform chat(model=, messages=, format=, temperature=) over the ollama module,
    translating temperature into ollama's options dict. Ollama is imported lazily."""

    def __init__(self, client=None):
        self._client = client

    def chat(self, model, messages, format=None, temperature=None):
        client = self._client
        if client is None:
            import ollama
            client = ollama
        kwargs = {"model": model, "messages": messages}
        if format:
            kwargs["format"] = format
        if temperature is not None:
            kwargs["options"] = {"temperature": temperature}
        return client.chat(**kwargs)


def get_client():
    """The chat client for the configured provider. Ollama is imported lazily so a
    cloud-only deploy needn't install it."""
    if provider() == "openai":
        from engine.llm_openai import OpenAIChatClient
        return OpenAIChatClient()
    return OllamaChatClient()
