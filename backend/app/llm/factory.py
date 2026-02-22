from __future__ import annotations

import os

from .heuristic import HeuristicProvider
from .openai_provider import OpenAIProvider
from .provider import LLMProvider


def get_provider() -> LLMProvider:
    provider = (os.getenv("PANELAI_LLM_PROVIDER") or "heuristic").strip().lower()
    if provider == "heuristic":
        return HeuristicProvider()
    if provider == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown PANELAI_LLM_PROVIDER: {provider}")
