from __future__ import annotations

import re
from dataclasses import dataclass

from ..llm.factory import get_provider
from .base import AgentResult, Finding, PanelAgent, PanelContext


def _extract_resume_claims(resume: str) -> list[str]:
    lines = [ln.strip() for ln in resume.splitlines() if ln.strip()]
    claims: list[str] = []
    for ln in lines:
        if ln.startswith(("-", "•", "*")):
            claims.append(ln.lstrip("-*• ").strip())
            continue
        if re.search(r"\b(built|designed|led|owned|implemented|scaled|migrated|optimized|architected)\b", ln, re.I):
            claims.append(ln)
            continue
        if re.search(r"\b\d+\+?\s*(years|yrs)\b", ln, re.I):
            claims.append(ln)
            continue
    # de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for c in claims:
        c2 = re.sub(r"\s+", " ", c).strip()
        if c2 and c2 not in seen:
            out.append(c2)
            seen.add(c2)
    return out[:40]


@dataclass
class ResumeClaimsAgent:
    name: str = "resume-claims"

    async def run(self, ctx: PanelContext) -> AgentResult:
        claims = _extract_resume_claims(ctx.resume)

        llm = get_provider()
        if getattr(llm, "name", "") == "heuristic":
            synthesis_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
        else:
            synthesis = await llm.complete(
                system="You extract and normalize resume claims for an interview panel.",
                user=(
                    "Normalize the following resume claims into a compact numbered list. "
                    "Keep each item atomic and testable.\n\n"
                    + "\n".join(f"- {c}" for c in claims)
                ),
            )
            synthesis_text = synthesis.text

        findings = [
            Finding(
                category="resume_claims",
                summary=f"Extracted {len(claims)} testable resume claims.",
                severity="low",
                evidence=synthesis_text,
            )
        ]

        return AgentResult(findings=findings, artifacts={"claims": claims, "claims_normalized": synthesis_text})

    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        llm = get_provider()
        resp = await llm.complete(
            system="You defend/clarify what counts as a resume claim and how it should be tested.",
            user=f"Challenge: {challenge}\n\nResume:\n{ctx.resume}\n",
        )
        return resp.text
