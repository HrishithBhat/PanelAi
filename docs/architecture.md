# Architecture — PanelAI (Autonomous Technical Interview Panel)

## Goal
Build an **autonomous technical interview panel** that behaves like a real hiring committee:
- Ingests **job description**, **resume**, and **interview transcript**
- Produces an **assessment + discrepancy log + hire/no-hire verdict**
- Provides a **debate trace** showing how agents challenged each other

This repo intentionally implements **custom orchestration logic** (not a pre-built “agent framework”).

## System Overview
PanelAI is split into:
- **Backend (FastAPI)**: orchestration engine + evaluation API
- **Frontend (React/Vite)**: usable UI to run evaluations and inspect results
- **Data**: reproducible sample inputs

### Key artifacts produced per evaluation
- `discrepancies[]`: structured list of claim-vs-evidence mismatches and contradictions
- `scores[]`: dimension scores (0–4) with rationale
- `verdict`: `hire | no-hire | lean-hire | lean-no-hire`
- `trace[]`: chronological log of agent actions + cross-exam responses

## Agents
Each agent is a small, role-specific component with two capabilities:
- `run(ctx)`: produce findings/scores/questions/vote
- `respond_to_challenge(ctx, challenge)`: participate in cross-examination

### Implemented roles
- **ResumeClaimsAgent**: extracts atomic, testable claims from the resume
- **TranscriptEvidenceAgent**: summarizes what the candidate demonstrated and chunks transcript for evidence retrieval
- **GapAnalysisAgent**: compares JD requirements vs resume/transcript evidence; proposes follow-up questions
- **ContradictionHunterAgent**: flags uncertainty/admissions that may contradict strong resume claims
- **SystemsDesignJudgeAgent**: scores demonstrated systems reasoning
- **CodingJudgeAgent**: scores coding reasoning signals
- **HiringManagerAgent**: weighs risk/fit/ownership and issues an overall vote

## Orchestration & Conflict Resolution
The orchestrator (`backend/app/orchestrator.py`) runs the panel in phases:

1) **Initial round (parallel)**
- All agents run from the same `PanelContext`

2) **Discrepancy synthesis**
- Seeds discrepancies from contradiction findings
- Adds additional discrepancies for resume claims that have weak transcript evidence using a lightweight similarity search

3) **Cross-exam rounds (challenge protocol)**
- The orchestrator selects the top discrepancies by severity
- Judges and hiring manager are asked to respond to each discrepancy
- Responses are appended to the `trace[]`

4) **Consensus voting**
- Weighted committee vote (HM and Systems are weighted higher)
- Final verdict is derived from weighted sum of vote strength × confidence

## LLM Strategy (Optional)
PanelAI runs in two modes:
- **Heuristic (default)**: deterministic analysis; no keys needed
- **OpenAI (optional)**: improves synthesis/rationales; still uses the same orchestration design

The LLM is used only as a **tool for synthesis**, not as the orchestrator.
The orchestrator remains responsible for:
- which agents run
- how conflicts are surfaced
- how evidence is collected
- how consensus is computed

## Tech stack
- Backend: FastAPI + Pydantic
- Frontend: React + Vite + TypeScript

## Design decisions
- **Transparency first**: outputs include a trace to support judge auditability
- **Evidence-driven discrepancies**: every discrepancy must include a claim and a transcript snippet
- **Reproducibility**: sample inputs shipped in-repo for consistent re-runs
