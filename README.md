# PanelAI — Autonomous Technical Interview Panel

PanelAI is a full‑stack web app that helps HR/engineering teams evaluate a candidate against a job description using the candidate’s resume and interview transcript.

It runs a **multi-agent interview panel** (custom orchestration; no pre-built “agent framework”) to flag discrepancies, generate follow-up questions, and produce an auditable evaluation trace.

## What you get
- Web UI to upload the 3 inputs (JD / resume / transcript), paste text, or load provided samples
- Outputs: assessment, discrepancy log, strengths/risks, follow-up questions, verdict + reasoning, and agent trace
- Live Interview Assist mode (optional): append transcript as you go and get near-real-time discrepancies + follow-ups (final verdict only on demand)

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
