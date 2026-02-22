from __future__ import annotations

import re
from dataclasses import dataclass

from ..llm.factory import get_provider
from .base import AgentResult, Finding, PanelContext


def _extract_requirements(jd: str) -> list[str]:
    lines = [ln.strip() for ln in jd.splitlines() if ln.strip()]
    reqs: list[str] = []
    for ln in lines:
        if ln.startswith(("-", "•", "*")):
            reqs.append(ln.lstrip("-*• ").strip())
            continue
        if re.search(r"\b(must|required|requirements?)\b", ln, re.I):
            reqs.append(ln)
    seen: set[str] = set()
    out: list[str] = []
    for r in reqs:
        r2 = re.sub(r"\s+", " ", r).strip()
        if r2 and r2 not in seen:
            out.append(r2)
            seen.add(r2)
    return out[:40]


def _mentions(text: str, requirement: str) -> bool:
    # crude but effective: match main keywords
    req_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}", requirement.lower())
    stop = {
        "and",
        "with",
        "for",
        "the",
        "to",
        "a",
        "of",
        "must",
        "have",
        "required",
        "requirements",
        "requirement",
        "experience",
        "years",
        "year",
    }
    short_ok = {"go", "c", "js", "ts", "ai", "ml"}
    req_words = [w for w in req_words if w not in stop and (len(w) >= 3 or w in short_ok)]
    if not req_words:
        return False
    hits = sum(1 for w in set(req_words[:8]) if w in text.lower())
    return hits >= max(1, min(3, len(set(req_words)) // 4))


@dataclass
class GapAnalysisAgent:
    name: str = "gap-analysis"

    async def run(self, ctx: PanelContext) -> AgentResult:
        reqs = _extract_requirements(ctx.job_description)
        corpus = ctx.resume + "\n" + ctx.transcript

        covered: list[str] = []
        gaps: list[str] = []
        for r in reqs:
            if _mentions(corpus, r):
                covered.append(r)
            else:
                gaps.append(r)

        llm = get_provider()
        if getattr(llm, "name", "") == "heuristic":
            top_gaps = gaps[:6]
            narrative_text = (
                "Heuristic gap summary:\n"
                + ("Covered (signals in resume/transcript):\n" + "\n".join(f"- {c}" for c in covered[:6]) + "\n\n" if covered else "")
                + ("Missing/weak coverage:\n" + "\n".join(f"- {g}" for g in top_gaps) if top_gaps else "No major gaps detected.")
            )
        else:
            narrative = await llm.complete(
                system="You identify gaps between role requirements and demonstrated evidence.",
                user=(
                    "Job requirements:\n"
                    + "\n".join(f"- {r}" for r in reqs)
                    + "\n\nMissing/weak coverage requirements:\n"
                    + "\n".join(f"- {g}" for g in gaps)
                    + "\n\nExplain the most interview-relevant gaps and why they matter."
                ),
            )
            narrative_text = narrative.text

        findings = [
            Finding(
                category="role_alignment",
                summary=f"Identified {len(gaps)} requirement areas with weak evidence.",
                severity="medium" if gaps else "low",
                evidence=narrative_text,
            )
        ]
        next_questions = [f"Can you walk through your experience with: {g}?" for g in gaps[:6]]

        strengths = [f"Evidence suggests coverage of: {c}" for c in covered[:6]]
        risks = [f"Weak or missing evidence for: {g}" for g in gaps[:6]]

        return AgentResult(
            findings=findings,
            next_questions=next_questions,
            strengths=strengths,
            risks=risks,
            artifacts={"requirements": reqs, "gaps": gaps, "covered": covered},
        )

    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        llm = get_provider()
        resp = await llm.complete(
            system="You justify gap analysis with role requirements and avoid nitpicks.",
            user=f"Challenge: {challenge}\n\nJD:\n{ctx.job_description}\n\nResume:\n{ctx.resume}\n\nTranscript:\n{ctx.transcript}\n",
        )
        return resp.text
