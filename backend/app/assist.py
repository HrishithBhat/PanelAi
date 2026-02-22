from __future__ import annotations

import asyncio
import re
from typing import Any

from .agents.base import PanelContext
from .agents.contradictions import ContradictionHunterAgent
from .agents.gap_analysis import GapAnalysisAgent
from .agents.transcript_evidence import TranscriptEvidenceAgent, _best_evidence
from .models import AssistResult, Discrepancy, FollowUp


def _severity_rank(sev: str) -> int:
    return 0 if sev == "high" else 1 if sev == "medium" else 2


def _extract_gap_from_question(q: str) -> str:
    m = re.search(r"experience with:\s*(.+?)\?\s*$", q, re.I)
    if m:
        return m.group(1).strip()
    return q.strip()


async def run_assist(*, ctx: PanelContext) -> AssistResult:
    """Assist-mode analysis for live interviews.

    Runs lightweight agents only:
    - TranscriptEvidenceAgent: chunks + evidence summary
    - GapAnalysisAgent: requirements coverage + follow-up questions
    - ContradictionHunterAgent: uncertainty / contradictions

    Returns live discrepancies + follow-ups with evidence snippets.
    """

    te = TranscriptEvidenceAgent()
    ga = GapAnalysisAgent()
    ch = ContradictionHunterAgent()

    te_res, ga_res, ch_res = await asyncio.gather(te.run(ctx), ga.run(ctx), ch.run(ctx))

    chunks = te_res.artifacts.get("chunks", [])
    if not isinstance(chunks, list):
        chunks = []
    chunks = [str(x) for x in chunks]

    discrepancies: list[Discrepancy] = []

    # 1) Contradiction/uncertainty findings become discrepancies directly.
    for f in ch_res.findings:
        discrepancies.append(
            Discrepancy(
                severity=f.severity,
                category=f.category,
                claim=f.claim or "(unspecified)",
                evidence=f.evidence or "",
                explanation=f.explanation or f.summary,
            )
        )

    # 2) Missing requirements become “gap” discrepancies.
    gaps = ga_res.artifacts.get("gaps", [])
    if isinstance(gaps, list):
        for g in [str(x) for x in gaps[:10]]:
            ev, score = _best_evidence(g, chunks) if chunks else ("", 0.0)
            evidence = ev if score >= 0.20 and ev else "(no supporting transcript snippet yet)"
            discrepancies.append(
                Discrepancy(
                    severity="medium",
                    category="missing_requirement_signal",
                    claim=g,
                    evidence=evidence,
                    explanation=(
                        "Job requirement has weak or missing evidence so far in the live transcript. "
                        "This is a prompt for targeted follow-up questions."
                    ),
                )
            )

    # Follow-ups: prefer gap questions; fill remaining with contradiction clarifications.
    followups: list[FollowUp] = []

    for q in ga_res.next_questions[:8]:
        q2 = str(q)
        gap = _extract_gap_from_question(q2)
        ev, score = _best_evidence(gap, chunks) if chunks else ("", 0.0)
        followups.append(
            FollowUp(
                question=q2,
                reason="Weak or missing coverage of a job requirement so far.",
                evidence=(ev if score >= 0.25 else ""),
                evidence_score=float(score),
            )
        )
        if len(followups) >= 5:
            break

    if len(followups) < 5:
        for f in ch_res.findings[:8]:
            if len(followups) >= 5:
                break
            claim = (f.claim or "").strip()
            if claim:
                question = f"You mentioned uncertainty around '{claim}'. Can you clarify what you actually did hands-on?"
            else:
                question = "You expressed uncertainty in that area—can you clarify what you personally implemented and why?"
            followups.append(
                FollowUp(
                    question=question,
                    reason="Clarifies a potential contradiction or uncertainty signal.",
                    evidence=str(f.evidence or ""),
                    evidence_score=1.0,
                )
            )

    risks: list[str] = []
    if any(d.severity == "high" for d in discrepancies):
        risks.append("High-severity uncertainty/contradiction signals detected in the live transcript.")
    if isinstance(gaps, list) and len(gaps) >= 5:
        risks.append("Many job requirements are not yet covered by evidence in the transcript.")

    artifacts: dict[str, Any] = {
        "chunks_count": len(chunks),
        "gap_count": len(gaps) if isinstance(gaps, list) else 0,
        "contradiction_findings": len(ch_res.findings),
    }

    # Sort discrepancies for UI (high -> medium -> low)
    discrepancies = sorted(discrepancies, key=lambda d: _severity_rank(d.severity))[:20]

    return AssistResult(
        discrepancies=discrepancies,
        followups=followups[:5],
        risks=risks[:6],
        artifacts=artifacts,
    )
