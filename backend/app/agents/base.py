from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class PanelContext:
    job_description: str
    resume: str
    transcript: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Finding:
    category: str
    summary: str
    severity: Literal["low", "medium", "high"] = "medium"
    claim: str | None = None
    evidence: str | None = None
    explanation: str | None = None


@dataclass(frozen=True)
class Dimension:
    name: str
    score_0_to_4: int
    rationale: str


@dataclass(frozen=True)
class Vote:
    verdict: Literal["hire", "no-hire", "lean-hire", "lean-no-hire"]
    confidence_0_to_1: float
    reasoning: str


@dataclass
class AgentResult:
    findings: list[Finding] = field(default_factory=list)
    scores: list[Dimension] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_questions: list[str] = field(default_factory=list)
    vote: Vote | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)


class PanelAgent(Protocol):
    name: str

    async def run(self, ctx: PanelContext) -> AgentResult:
        ...

    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        ...
