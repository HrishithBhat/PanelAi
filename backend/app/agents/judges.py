from __future__ import annotations

import re
from dataclasses import dataclass

from ..llm.factory import get_provider
from .base import AgentResult, Dimension, PanelContext, Vote


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def _depth_markers(transcript: str) -> int:
    markers = [
        "tradeoff",
        "throughput",
        "latency",
        "consistency",
        "availability",
        "partition",
        "idempotent",
        "backpressure",
        "retry",
        "rate limit",
        "cache",
        "index",
        "observability",
        "slo",
        "sli",
        "incident",
        "rca",
    ]
    t = transcript.lower()
    return sum(1 for m in markers if m in t)


def _uncertainty_markers(transcript: str) -> int:
    t = transcript.lower()
    flags = [
        "i don't know",
        "i dont know",
        "not sure",
        "haven't used",
        "have not used",
        "never used",
        "didn't think",
        "didnt think",
        "wasn't the lead",
        "wasnt the lead",
    ]
    return sum(1 for f in flags if f in t)


def _score_bucket(value: int, *, low: int, high: int) -> int:
    if value <= low:
        return 1
    if value >= high:
        return 4
    # map middle range to 2-3
    return 2 if value < (low + high) / 2 else 3


def _get_signals(ctx: PanelContext) -> dict:
    signals = ctx.config.get("panelai_signals") if isinstance(ctx.config, dict) else None
    return signals if isinstance(signals, dict) else {}


@dataclass
class SystemsDesignJudgeAgent:
    name: str = "judge-systems"

    async def run(self, ctx: PanelContext) -> AgentResult:
        depth = _depth_markers(ctx.transcript)
        uncertainty = _uncertainty_markers(ctx.transcript)
        adjusted = max(0, depth - 2 * uncertainty)
        score = _score_bucket(adjusted, low=2, high=10)

        signals = _get_signals(ctx)
        gaps_count = int(signals.get("gaps_count", 0) or 0)
        coverage_ratio = float(signals.get("coverage_ratio", 0.0) or 0.0)

        llm = get_provider()
        if getattr(llm, "name", "") == "heuristic":
            rationale_text = (
                f"Signals: depth={depth}, uncertainty={uncertainty}. "
                f"Score reflects demonstrated tradeoffs/failure-mode reasoning. "
                f"Role coverage: {coverage_ratio:.0%} ({gaps_count} gaps)."
            )
        else:
            rationale = await llm.complete(
                system="You are a systems design interviewer scoring demonstrated reasoning depth.",
                user=(
                    f"Given this transcript, score systems design depth 0-4. "
                    f"depth_markers={depth}, uncertainty_markers={uncertainty}, adjusted={adjusted}. "
                    "Do NOT reward keyword mentions if the candidate expresses uncertainty or lack of ownership. "
                    "Provide a short rationale citing evidence.\n\nTranscript:\n"
                    + ctx.transcript
                ),
            )
            rationale_text = rationale.text

        # Vote: design depth is primary, but large requirement gaps increases risk.
        verdict: Vote
        if score >= 3 and gaps_count <= 2:
            confidence = _clamp(0.58 + 0.06 * score + 0.02 * depth - 0.06 * uncertainty, 0.52, 0.85)
            verdict = Vote(
                verdict="lean-hire",
                confidence_0_to_1=confidence,
                reasoning=(
                    f"Design depth markers={depth}, uncertainty={uncertainty}; "
                    f"role coverage={coverage_ratio:.0%}, gaps={gaps_count}."
                ),
            )
        elif score >= 3:
            confidence = _clamp(0.54 + 0.05 * score + 0.02 * depth - 0.06 * uncertainty - 0.03 * min(6, gaps_count) / 6, 0.5, 0.82)
            verdict = Vote(
                verdict="lean-hire",
                confidence_0_to_1=confidence,
                reasoning=(
                    f"Design depth markers={depth}, uncertainty={uncertainty}; "
                    f"role coverage={coverage_ratio:.0%}, gaps={gaps_count} (gaps increase risk)."
                ),
            )
        else:
            confidence = _clamp(0.58 + 0.02 * max(0, 3 - score) + 0.03 * uncertainty, 0.55, 0.83)
            verdict = Vote(
                verdict="lean-no-hire",
                confidence_0_to_1=confidence,
                reasoning=(
                    f"Low design depth markers={depth} with uncertainty={uncertainty}; "
                    f"role coverage={coverage_ratio:.0%}, gaps={gaps_count}."
                ),
            )

        return AgentResult(
            scores=[Dimension(name="systems_design", score_0_to_4=score, rationale=rationale_text)],
            vote=verdict,
        )


    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        llm = get_provider()
        resp = await llm.complete(
            system="You defend a systems design score by citing transcript evidence and tradeoff reasoning.",
            user=f"Challenge: {challenge}\n\nTranscript:\n{ctx.transcript}",
        )
        return resp.text


@dataclass
class CodingJudgeAgent:
    name: str = "judge-coding"

    async def run(self, ctx: PanelContext) -> AgentResult:
        t = ctx.transcript.lower()
        # crude: detect whether they discuss complexity, testing, edge cases
        signals = 0
        present: list[str] = []
        if "big o" in t or "complexity" in t:
            signals += 1
            present.append("complexity")
        if "edge case" in t or "corner case" in t:
            signals += 1
            present.append("edge_cases")
        if "test" in t or "unit" in t:
            signals += 1
            present.append("testing")
        if "refactor" in t:
            signals += 1
            present.append("refactor")
        score = min(4, max(0, signals + 1))

        meta = _get_signals(ctx)
        contradiction_count = int(meta.get("contradiction_count", 0) or 0)
        weak_claims_count = int(meta.get("weak_claims_count", 0) or 0)

        llm = get_provider()
        if getattr(llm, "name", "") == "heuristic":
            rationale_text = (
                f"Signals: {signals} (complexity/edge-cases/tests/refactor mentions). "
                f"Risk signals: contradictions={contradiction_count}, weak_claims={weak_claims_count}."
            )
        else:
            rationale = await llm.complete(
                system="You are a coding interviewer scoring practical coding reasoning.",
                user=(
                    f"Score coding signal 0-4 based on evidence in transcript. signals={signals}. "
                    "Provide a short rationale.\n\nTranscript:\n" + ctx.transcript
                ),
            )
            rationale_text = rationale.text

        risk_penalty = 0.04 * min(3, contradiction_count) + 0.03 * min(6, weak_claims_count) / 6
        base_conf = 0.52 + 0.07 * signals
        confidence = _clamp(base_conf - risk_penalty, 0.5, 0.86)

        if contradiction_count >= 2 or weak_claims_count >= 6:
            verdict = Vote(
                verdict="lean-no-hire",
                confidence_0_to_1=_clamp(confidence + 0.04, 0.55, 0.9),
                reasoning=(
                    f"Coding signals={present or ['none']}; contradictions={contradiction_count}, "
                    f"weak_claims={weak_claims_count} (risk dominates)."
                ),
            )
        else:
            verdict_value = "lean-hire" if score >= 3 else "lean-no-hire"
            verdict = Vote(
                verdict=verdict_value,
                confidence_0_to_1=confidence,
                reasoning=(
                    f"Coding signals={present or ['none']} (score={score}/4); "
                    f"contradictions={contradiction_count}, weak_claims={weak_claims_count}."
                ),
            )

        return AgentResult(scores=[Dimension(name="coding", score_0_to_4=score, rationale=rationale_text)], vote=verdict)

    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        return f"Coding judge response: {challenge}"


@dataclass
class HiringManagerAgent:
    name: str = "hiring-manager"

    async def run(self, ctx: PanelContext) -> AgentResult:
        llm = get_provider()
        signals = _get_signals(ctx)
        coverage_ratio = float(signals.get("coverage_ratio", 0.0) or 0.0)
        gaps_count = int(signals.get("gaps_count", 0) or 0)
        discrepancy_count = int(signals.get("discrepancy_count", 0) or 0)
        high_discrepancy_count = int(signals.get("high_discrepancy_count", 0) or 0)
        top_gaps = signals.get("top_gaps", [])
        if getattr(llm, "name", "") == "heuristic":
            gaps_preview = ", ".join(str(g) for g in (top_gaps[:3] if isinstance(top_gaps, list) else []) if str(g).strip())
            hm_text = (
                "Heuristic summary: HM vote based on role coverage + ownership + risk signals. "
                f"Coverage={coverage_ratio:.0%} (gaps={gaps_count}). "
                f"Discrepancies={discrepancy_count} (high={high_discrepancy_count})."
                + (f" Top gaps: {gaps_preview}." if gaps_preview else "")
            )
        else:
            rationale = await llm.complete(
                system=(
                    "You are a hiring manager on an interview panel. You care about role fit, scope, ownership, "
                    "communication clarity, and risk."
                ),
                user=(
                    "Based on the resume and transcript, provide a concise hire recommendation (hire/no-hire/lean). "
                    "List top strengths and top risks.\n\nJD:\n"
                    + ctx.job_description
                    + "\n\nResume:\n"
                    + ctx.resume
                    + "\n\nTranscript:\n"
                    + ctx.transcript
                ),
            )
            hm_text = rationale.text

        # Heuristic vote: combine role coverage + ownership + depth, penalize high discrepancies.
        t = ctx.transcript.lower()
        ownership = 1 if re.search(r"\b(i\s+owned|i\s+led|i\s+was\s+responsible|i\s+drove|i\s+designed)\b", t) else (1 if re.search(r"\bowned\b|\bled\b|\bdrove\b", t) else 0)
        depth = 1 if _depth_markers(ctx.transcript) >= 4 else 0
        risk = 1 if high_discrepancy_count >= 2 else 0

        score = 0.0
        score += 1.0 if coverage_ratio >= 0.6 else (0.3 if coverage_ratio >= 0.35 else -0.6)
        score += 0.6 * ownership
        score += 0.4 * depth
        score -= 0.9 * risk

        coverage_pct = f"{coverage_ratio:.0%}"
        ownership_text = "ownership" if ownership else "limited_ownership"
        depth_text = "design_depth" if depth else "limited_depth"
        risk_text = "high_risk" if risk else "lower_risk"

        confidence = _clamp(0.55 + 0.12 * min(1.5, abs(score)) - (0.06 if risk else 0.0), 0.5, 0.88)
        reasoning = (
            f"Coverage={coverage_pct}, gaps={gaps_count}; signals={ownership_text}+{depth_text}; "
            f"discrepancies(high)={high_discrepancy_count}; risk={risk_text}."
        )

        if score >= 1.1:
            vote = Vote(verdict="lean-hire", confidence_0_to_1=confidence, reasoning=reasoning)
        elif score <= -0.6:
            vote = Vote(verdict="lean-no-hire", confidence_0_to_1=_clamp(confidence + 0.03, 0.55, 0.9), reasoning=reasoning)
        else:
            vote = Vote(verdict="lean-no-hire", confidence_0_to_1=confidence, reasoning=reasoning)

        return AgentResult(
            vote=vote,
            artifacts={"hm_summary": hm_text},
        )

    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        llm = get_provider()
        resp = await llm.complete(
            system="You defend your hiring recommendation using concrete evidence.",
            user=f"Challenge: {challenge}\n\nContext:\nJD:\n{ctx.job_description}\n\nResume:\n{ctx.resume}\n\nTranscript:\n{ctx.transcript}",
        )
        return resp.text
