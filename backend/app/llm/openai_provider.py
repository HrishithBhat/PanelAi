from __future__ import annotations

import os

import httpx

from .provider import LLMProvider, LLMResponse


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._model = os.getenv("OPENAI_MODEL", "") or "gpt-4o-mini"
        self._base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self._base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        return LLMResponse(text=content)
