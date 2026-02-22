from __future__ import annotations

import re
from dataclasses import dataclass

from ..llm.factory import get_provider
from .base import AgentResult, Dimension, PanelContext, Vote


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


@dataclass
class SystemsDesignJudgeAgent:
    name: str = "judge-systems"

    async def run(self, ctx: PanelContext) -> AgentResult:
        depth = _depth_markers(ctx.transcript)
        uncertainty = _uncertainty_markers(ctx.transcript)
        adjusted = max(0, depth - 2 * uncertainty)
        score = _score_bucket(adjusted, low=2, high=10)

        llm = get_provider()
        if getattr(llm, "name", "") == "heuristic":
            rationale_text = (
                f"Signals: depth={depth}, uncertainty={uncertainty}. "
                f"Score reflects demonstrated tradeoffs/failure-mode reasoning."
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

        verdict: Vote
        if score >= 3:
            verdict = Vote(verdict="lean-hire", confidence_0_to_1=0.62, reasoning="Solid design reasoning markers.")
        else:
            verdict = Vote(verdict="lean-no-hire", confidence_0_to_1=0.62, reasoning="Insufficient design depth markers.")

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
        signals += 1 if "big o" in t or "complexity" in t else 0
        signals += 1 if "edge case" in t or "corner case" in t else 0
        signals += 1 if "test" in t or "unit" in t else 0
        signals += 1 if "refactor" in t else 0
        score = min(4, max(0, signals + 1))

        llm = get_provider()
        if getattr(llm, "name", "") == "heuristic":
            rationale_text = f"Signals: {signals} (complexity/edge-cases/tests/refactor mentions)."
        else:
            rationale = await llm.complete(
                system="You are a coding interviewer scoring practical coding reasoning.",
                user=(
                    f"Score coding signal 0-4 based on evidence in transcript. signals={signals}. "
                    "Provide a short rationale.\n\nTranscript:\n" + ctx.transcript
                ),
            )
            rationale_text = rationale.text

        verdict = Vote(
            verdict="lean-hire" if score >= 3 else "lean-no-hire",
            confidence_0_to_1=0.58,
            reasoning="Based on coding reasoning signals in transcript.",
        )

        return AgentResult(scores=[Dimension(name="coding", score_0_to_4=score, rationale=rationale_text)], vote=verdict)

    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        return f"Coding judge response: {challenge}"


@dataclass
class HiringManagerAgent:
    name: str = "hiring-manager"

    async def run(self, ctx: PanelContext) -> AgentResult:
        llm = get_provider()
        if getattr(llm, "name", "") == "heuristic":
            hm_text = "Heuristic summary: HM vote based on ownership + design-depth signals."
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

        # heuristic vote: if they show ownership language + some depth markers
        ownership = 1 if re.search(r"\b(i owned|i led|i was responsible|i drove)\b", ctx.transcript.lower()) else 0
        depth = 1 if _depth_markers(ctx.transcript) >= 4 else 0
        if ownership + depth >= 1:
            vote = Vote(verdict="lean-hire", confidence_0_to_1=0.6, reasoning="Some ownership/depth evidence.")
        else:
            vote = Vote(verdict="lean-no-hire", confidence_0_to_1=0.6, reasoning="Weak ownership/depth evidence.")

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
