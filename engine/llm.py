import os

DEFAULT_MODELS = {"ollama": "qwen2.5:7b", "openai": "gpt-4o"}


def provider() -> str:
    return os.environ.get("REHEARSAL_LLM_PROVIDER", "ollama")


def default_model() -> str:
    return os.environ.get("REHEARSAL_LLM_MODEL") or DEFAULT_MODELS.get(provider(), "qwen2.5:7b")


def get_client():
    """The chat client for the configured provider. Ollama is imported lazily so a
    cloud-only deploy needn't install it."""
    if provider() == "openai":
        from engine.llm_openai import OpenAIChatClient
        return OpenAIChatClient()
    import ollama
    return ollama
