from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    job_description: str = Field(..., description="Job description text")
    resume: str = Field(..., description="Candidate resume text")
    transcript: str = Field(..., description="Interview transcript text")
    config: dict[str, Any] = Field(default_factory=dict)


class AssistRequest(BaseModel):
    job_description: str = Field(..., description="Job description text")
    resume: str = Field(..., description="Candidate resume text")
    transcript: str = Field(default="", description="Interview transcript text (can be empty for live sessions)")
    config: dict[str, Any] = Field(default_factory=dict)


class Discrepancy(BaseModel):
    severity: Literal["low", "medium", "high"]
    category: str
    claim: str
    evidence: str
    explanation: str


class DimensionScore(BaseModel):
    dimension: str
    score_0_to_4: int = Field(..., ge=0, le=4)
    rationale: str


class AgentMessage(BaseModel):
    agent: str
    stage: str
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    verdict: Literal["hire", "no-hire", "lean-hire", "lean-no-hire"]
    overall_reasoning: str
    scores: list[DimensionScore]
    discrepancies: list[Discrepancy]
    strengths: list[str]
    risks: list[str]
    next_interview_questions: list[str]
    trace: list[AgentMessage]
    artifacts: dict[str, Any] = Field(default_factory=dict)


class FollowUp(BaseModel):
    question: str
    reason: str = ""
    evidence: str = ""
    evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class AssistResult(BaseModel):
    discrepancies: list[Discrepancy]
    followups: list[FollowUp]
    risks: list[str] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
