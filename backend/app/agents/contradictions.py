from __future__ import annotations

import re
from dataclasses import dataclass

from .base import AgentResult, Finding, PanelContext
from .transcript_evidence import _chunk_transcript


_RED_FLAGS = [
    "i don't know",
    "i dont know",
    "not sure",
    "haven't used",
    "have not used",
    "never used",
    "can't remember",
    "no idea",
]


def _find_red_flag_snippets(transcript: str) -> list[str]:
    chunks = _chunk_transcript(transcript)
    out: list[str] = []
    for ch in chunks:
        lower = ch.lower()
        if any(p in lower for p in _RED_FLAGS):
            out.append(ch)
    return out[:8]


def _extract_skill_terms(resume: str) -> set[str]:
    # lightweight: treat common tech tokens as skills
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9+.#-]{1,}\b", resume)
    keep: set[str] = set()
    for t in tokens:
        if t[0].isupper() or any(x in t for x in ["+", ".", "#"]):
            if len(t) <= 24:
                keep.add(t)
    return set(sorted(keep))


@dataclass
class ContradictionHunterAgent:
    name: str = "contradiction-hunter"

    async def run(self, ctx: PanelContext) -> AgentResult:
        skills = _extract_skill_terms(ctx.resume)
        red_flags = _find_red_flag_snippets(ctx.transcript)

        findings: list[Finding] = []
        for snippet in red_flags:
            mentioned = [s for s in list(skills)[:80] if s.lower() in snippet.lower()]
            findings.append(
                Finding(
                    category="contradiction_or_uncertainty",
                    summary="Candidate expressed uncertainty / lack of experience.",
                    severity="high" if mentioned else "medium",
                    claim=", ".join(mentioned) if mentioned else None,
                    evidence=snippet,
                    explanation=(
                        "Uncertainty is not automatically disqualifying, but becomes a discrepancy "
                        "when it conflicts with strong resume claims or role-critical requirements."
                    ),
                )
            )

        return AgentResult(findings=findings, artifacts={"skills_detected": sorted(list(skills))[:120]})

    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        return (
            "I treat contradictions as: (1) direct conflicts between stated experience and transcript admissions, "
            "or (2) repeated uncertainty on role-critical topics. "
            f"Challenge received: {challenge}"
        )
