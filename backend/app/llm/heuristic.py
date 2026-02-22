from __future__ import annotations

import re
from dataclasses import dataclass

from .provider import LLMProvider, LLMResponse


@dataclass
class HeuristicProvider:
    name: str = "heuristic"

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        # Deterministic fallback for no-key runs.
        # Important: do NOT echo the full prompt back (it pollutes the UI).
        compact: list[str] = []

        # Extract common numeric signals if present
        for key in ("depth_markers", "uncertainty_markers", "adjusted", "signals"):
            m = re.search(rf"\b{re.escape(key)}\s*=\s*(\d+)\b", user)
            if m:
                compact.append(f"{key}={m.group(1)}")

        if compact:
            return LLMResponse(text="Heuristic summary: " + ", ".join(compact) + ".")

        # Otherwise return a short statement of what the agent attempted.
        sys = re.sub(r"\s+", " ", system).strip()
        sys = sys[:160] + ("…" if len(sys) > 160 else "")
        return LLMResponse(text=f"Heuristic summary: {sys}")
