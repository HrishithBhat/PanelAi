# PanelAI — Autonomous Technical Interview Panel

PanelAI is a full‑stack web app that helps HR/engineering teams evaluate a candidate against a job description using the candidate’s resume and interview transcript.

It runs a **multi-agent interview panel** (custom orchestration; no pre-built “agent framework”) to flag discrepancies, generate follow-up questions, and produce an auditable evaluation trace.


Why PanelAI
Hiring feedback often becomes subjective, inconsistent, and hard to audit. PanelAI makes the evaluation:

Evidence-driven (ties claims to resume/transcript snippets)
Repeatable (same inputs → consistent structure of output)
Actionable (concrete follow-ups and gap signals)
Auditable (multi-agent trace instead of a single opaque blob)
PanelAI returns:

Verdict / recommendation (hire / no-hire style outcome, with justification)
Strengths aligned to role needs
Risks / concerns with supporting evidence
Discrepancy log (conflicting or weakly supported statements)
Follow-up questions prioritized for the next interview round
Agent trace to understand how each reviewer reached its view
2) Live Interview Assist (No Auto-Verdict)
During a live interview, you can keep appending transcript text (typed/paste, or mic via browser speech recognition) while the system periodically analyzes the latest transcript and highlights:

New contradictions / discrepancies
Gaps vs job requirements
High-value follow-up questions
Evidence snippets to support each prompt.
How It Works (High-Level)
PanelAI uses a small set of specialized “reviewers” (agents) that each focus on one lens:

Resume Claims: extracts key candidate claims and experience signals from the resume
Transcript Evidence: finds supporting evidence in the transcript
Gap Analysis: compares role requirements to candidate evidence (missing/weak areas)
Contradiction Hunter: flags inconsistent statements or mismatches across sources
Judges / Synthesizer: aggregates findings into a structured decision narrative and trace
The backend orchestrates these components concurrently and then synthesizes a final response model.

## What you get
- Web UI to upload the 3 inputs (JD / resume / transcript), paste text, or load provided samples
- Outputs: assessment, discrepancy log, strengths/risks, follow-up questions, verdict + reasoning, and agent trace
- Live Interview Assist mode (optional): append transcript as you go and get near-real-time discrepancies + follow-ups (final verdict only on demand)

## More about PanelAI

### Core goals
- **Consistency**: standardizes how interview feedback is structured across candidates.
- **Evidence-first**: ties strengths/risks/discrepancies to specific resume/transcript signals.
- **Actionability**: produces concrete follow-up questions for the next round.
- **Auditability**: includes an agent trace so decisions are explainable.

### Two modes

**1) Panel Evaluation (full verdict)**
- Generates a structured verdict/recommendation with supporting reasoning
- Produces a discrepancy log (claims vs evidence) and prioritized follow-up questions
- Returns agent artifacts so you can understand how the outcome was formed

**2) Live Interview Assist (no auto-verdict)**
- Designed for real-time interviewing: append transcript as the interview happens
- Highlights contradictions/discrepancies and gaps vs job requirements
- Suggests follow-up questions with evidence pointers
- Final verdict is only generated when you explicitly run the full evaluation

### High-level architecture
PanelAI orchestrates specialized reviewer agents in parallel and then synthesizes results:
- Resume claims extraction
- Transcript evidence mining
- Gap analysis vs role requirements
- Contradiction detection
- Synthesis/judging into a structured result + trace

### Notes / limitations
- Live mic transcription uses the browser Web Speech API (best in Chrome/Edge).
- If you enable an external LLM provider, you may hit rate limits (HTTP 429). Heuristic mode avoids external calls.

## Quickstart

### Backend (FastAPI)

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend runs at http://127.0.0.1:8000.

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173.

## Using uploads
- Supported formats in the UI: `.txt` and `.md` (you can paste anything into the text boxes too).
- Backend also exposes a multipart endpoint at `POST /evaluate-files`.

## Sample inputs
Sample data is in `data/sample1/`.

## Configuration (optional LLM)
By default, PanelAI runs in **heuristic mode** (no API keys needed).

To enable an LLM, set backend env vars (recommended via a local `.env` file):
- `PANELAI_LLM_PROVIDER=openai` (or `heuristic`)
- `OPENAI_API_KEY=...`
- `OPENAI_MODEL=...` (optional)

## Docs
- Diagrams: `docs/diagrams.md`
