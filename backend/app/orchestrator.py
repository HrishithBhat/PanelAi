from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Literal

from .agents.base import AgentResult, PanelContext
from .agents.contradictions import ContradictionHunterAgent
from .agents.gap_analysis import GapAnalysisAgent
from .agents.judges import CodingJudgeAgent, HiringManagerAgent, SystemsDesignJudgeAgent
from .agents.resume_claims import ResumeClaimsAgent
from .agents.transcript_evidence import TranscriptEvidenceAgent, _best_evidence
from .models import AgentMessage, DimensionScore, Discrepancy, EvaluationResult


Verdict = Literal["hire", "no-hire", "lean-hire", "lean-no-hire"]


@dataclass(frozen=True)
class PanelConfig:
    cross_exam_rounds: int = 1


def _vote_to_int(v: Verdict) -> int:
    return {"no-hire": -2, "lean-no-hire": -1, "lean-hire": 1, "hire": 2}[v]


def _int_to_verdict(score: int) -> Verdict:
    if score >= 2:
        return "hire"
    if score == 1:
        return "lean-hire"
    if score == -1:
        return "lean-no-hire"
    return "no-hire"


def _weighted_consensus(votes: list[tuple[Verdict, float, str, int]]) -> tuple[Verdict, str]:
    # votes: (verdict, confidence, reasoning, weight)
    total = 0.0
    reasons: list[str] = []
    for verdict, conf, reasoning, weight in votes:
        total += _vote_to_int(verdict) * conf * weight
        reasons.append(f"{verdict} (c={conf:.2f}): {reasoning}")

    # normalize to an int bucket
    if total >= 1.6:
        return "hire", " | ".join(reasons)
    if total >= 0.4:
        return "lean-hire", " | ".join(reasons)
    if total <= -1.6:
        return "no-hire", " | ".join(reasons)
    if total <= -0.4:
        return "lean-no-hire", " | ".join(reasons)
    return "lean-no-hire", " | ".join(reasons)


async def run_panel(*, ctx: PanelContext) -> EvaluationResult:
    config = PanelConfig(cross_exam_rounds=int(ctx.config.get("cross_exam_rounds", 1)))

    analysis_agents = [
        ResumeClaimsAgent(),
        TranscriptEvidenceAgent(),
        GapAnalysisAgent(),
        ContradictionHunterAgent(),
    ]

    panel_agents = [
        SystemsDesignJudgeAgent(),
        CodingJudgeAgent(),
        HiringManagerAgent(),
    ]

    trace: list[AgentMessage] = []
    results: dict[str, AgentResult] = {}

    async def _run_agent(*, agent, run_ctx: PanelContext, stage: str) -> None:
        trace.append(AgentMessage(agent=agent.name, stage=stage, content="Running"))
        res = await agent.run(run_ctx)
        results[agent.name] = res
        trace.append(
            AgentMessage(agent=agent.name, stage=stage, content="Completed", meta={"artifacts_keys": list(res.artifacts.keys())})
        )

    # Phase 1: analysis (parallelizable)
    await asyncio.gather(*[_run_agent(agent=a, run_ctx=ctx, stage="analysis") for a in analysis_agents])

    claims = results["resume-claims"].artifacts.get("claims", [])
    chunks = results["transcript-evidence"].artifacts.get("chunks", [])

    weak_claims: list[tuple[str, str, float]] = []
    if isinstance(claims, list) and isinstance(chunks, list):
        for c in claims[:20]:
            ev, score = _best_evidence(str(c), [str(x) for x in chunks])
            if score < 0.22:
                weak_claims.append((str(c), ev, score))

    # Build discrepancy list: start from contradiction findings + claim evidence mismatches
    discrepancies: list[Discrepancy] = []

    # Add explicit contradiction/uncertainty findings
    for f in results["contradiction-hunter"].findings:
        discrepancies.append(
            Discrepancy(
                severity=f.severity,
                category=f.category,
                claim=f.claim or "(unspecified)",
                evidence=f.evidence or "",
                explanation=f.explanation or f.summary,
            )
        )

    for c, ev, score in weak_claims[:10]:
        discrepancies.append(
            Discrepancy(
                severity="medium" if score > 0.12 else "high",
                category="claim_not_demonstrated",
                claim=c,
                evidence=ev or "(no supporting transcript snippet found)",
                explanation=(
                    "Resume claim has weak supporting evidence in the interview transcript. "
                    "This may be acceptable if the interview did not cover it, but it increases risk."
                ),
            )
        )

    gap_art = results["gap-analysis"].artifacts
    requirements = gap_art.get("requirements", []) if isinstance(gap_art, dict) else []
    gaps = gap_art.get("gaps", []) if isinstance(gap_art, dict) else []
    covered = gap_art.get("covered", []) if isinstance(gap_art, dict) else []

    coverage_ratio = 0.0
    try:
        total = float(len(requirements))
        if total > 0:
            coverage_ratio = float(len(covered)) / total
    except Exception:
        coverage_ratio = 0.0

    contradiction_count = len(results["contradiction-hunter"].findings)
    high_discrepancy_count = sum(1 for d in discrepancies if d.severity == "high")

    derived_signals: dict[str, Any] = {
        "requirements_count": len(requirements) if isinstance(requirements, list) else 0,
        "gaps_count": len(gaps) if isinstance(gaps, list) else 0,
        "covered_count": len(covered) if isinstance(covered, list) else 0,
        "coverage_ratio": coverage_ratio,
        "top_gaps": gaps[:6] if isinstance(gaps, list) else [],
        "contradiction_count": contradiction_count,
        "weak_claims_count": len(weak_claims),
        "high_discrepancy_count": high_discrepancy_count,
        "discrepancy_count": len(discrepancies),
    }

    panel_ctx = PanelContext(
        job_description=ctx.job_description,
        resume=ctx.resume,
        transcript=ctx.transcript,
        config={**(ctx.config or {}), "panelai_signals": derived_signals},
    )

    # Phase 2: panel votes (parallelizable)
    await asyncio.gather(*[_run_agent(agent=a, run_ctx=panel_ctx, stage="panel") for a in panel_agents])

    # Cross-exam: have judges challenge top discrepancies
    if config.cross_exam_rounds > 0 and discrepancies:
        top = sorted(discrepancies, key=lambda d: {"high": 0, "medium": 1, "low": 2}[d.severity])[:5]
        for round_idx in range(config.cross_exam_rounds):
            for d in top:
                challenge = (
                    f"Discrepancy ({d.severity}) in {d.category}: claim='{d.claim}'. "
                    f"Evidence: {d.evidence[:240]}"
                )
                for agent in (SystemsDesignJudgeAgent(), CodingJudgeAgent(), HiringManagerAgent()):
                    trace.append(AgentMessage(agent=agent.name, stage=f"cross-exam-{round_idx+1}", content=challenge))
                    response = await agent.respond_to_challenge(panel_ctx, challenge)
                    trace.append(
                        AgentMessage(
                            agent=agent.name,
                            stage=f"cross-exam-{round_idx+1}",
                            content=response,
                            meta={"target_discrepancy": d.category},
                        )
                    )

    # Consolidate scores
    scores: list[DimensionScore] = []
    for agent_name in ("judge-systems", "judge-coding"):
        for s in results[agent_name].scores:
            scores.append(DimensionScore(dimension=s.name, score_0_to_4=s.score_0_to_4, rationale=s.rationale))

    # Strengths/risks/questions
    strengths: list[str] = []
    risks: list[str] = []
    questions: list[str] = []

    strengths += results["gap-analysis"].strengths
    risks += results["gap-analysis"].risks
    questions += results["gap-analysis"].next_questions

    # Basic derived risks from discrepancies
    if any(d.severity == "high" for d in discrepancies):
        risks.append("High-severity discrepancies between claims and demonstrated knowledge.")
    if len([d for d in discrepancies if d.category == "claim_not_demonstrated"]) >= 4:
        risks.append("Many resume claims were not evidenced in the transcript.")

    # Consensus
    votes: list[tuple[Verdict, float, str, int]] = []
    # Weighting reflects a real panel: HM and Systems heavier
    for agent, weight in (("hiring-manager", 2), ("judge-systems", 2), ("judge-coding", 1)):
        v = results[agent].vote
        if v is not None:
            votes.append((v.verdict, v.confidence_0_to_1, v.reasoning, weight))

    if votes:
        verdict, consensus_reason = _weighted_consensus(votes)
    else:
        verdict, consensus_reason = "lean-no-hire", "No agent votes available."

    # Risk adjustment: multiple high-severity discrepancies should prevent an outright hire.
    high_count = sum(1 for d in discrepancies if d.severity == "high")
    if high_count >= 4:
        verdict = "no-hire"
        consensus_reason += " | risk-adjustment: 4+ high discrepancies => no-hire"
    elif high_count >= 2 and verdict in ("hire", "lean-hire"):
        verdict = "lean-no-hire"
        consensus_reason += " | risk-adjustment: 2+ high discrepancies => cap to lean-no-hire"

    hm_summary = results["hiring-manager"].artifacts.get("hm_summary", "")
    overall_reasoning = (hm_summary + "\n\nConsensus: " + consensus_reason).strip()

    artifacts: dict[str, Any] = {
        "votes": [{"verdict": v, "confidence": c, "reason": r, "weight": w} for (v, c, r, w) in votes],
        "weak_claims": [{"claim": c, "score": s, "evidence": ev} for (c, ev, s) in weak_claims],
        "signals": derived_signals,
    }

    # Ensure minimal output lists
    if not strengths:
        strengths = ["Clear baseline communication (no blocking signals detected)."]
    if not questions:
        questions = [
            "Tell us about a time you handled a production incident end-to-end.",
            "Walk through a system you designed: tradeoffs, scaling, and failure modes.",
        ]

    return EvaluationResult(
        verdict=verdict,
        overall_reasoning=overall_reasoning,
        scores=scores,
        discrepancies=discrepancies,
        strengths=strengths[:8],
        risks=risks[:8],
        next_interview_questions=questions[:10],
        trace=trace,
        artifacts=artifacts,
    )
