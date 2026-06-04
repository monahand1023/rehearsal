import os

import httpx

API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIChatClient:
    """Mimics the ollama `.chat()` interface so content/proficiency/coach can use it
    unchanged: chat(model=, messages=, format=, temperature=) -> {"message": {"content": str}}."""

    def __init__(self, client=None):
        self._client = client or httpx

    def chat(self, model, messages, format=None, temperature=None):
        key = os.environ["OPENAI_API_KEY"]
        body = {"model": model, "messages": messages}
        if format == "json":
            body["response_format"] = {"type": "json_object"}
        if temperature is not None:
            body["temperature"] = temperature
        resp = self._client.post(
            API_URL,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"message": {"content": data["choices"][0]["message"]["content"]}}
