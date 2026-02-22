from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str


class LLMProvider(Protocol):
    name: str

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        ...
