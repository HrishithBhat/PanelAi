from __future__ import annotations

import os
from pathlib import Path

import json
import os
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agents.base import PanelContext
from .models import AssistRequest, AssistResult, EvaluateRequest, EvaluationResult
from .assist import run_assist
from .orchestrator import run_panel


APP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = APP_ROOT.parents[0]
DATA_ROOT = WORKSPACE_ROOT / "data"

# Load .env from workspace root for local development.
# Safe in production: if no .env exists, this is a no-op.
# Use override=True so local .env reliably wins over any pre-set OS/terminal env vars.
load_dotenv(WORKSPACE_ROOT / ".env", override=True)

app = FastAPI(title="PanelAI", version="0.1.0")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    debug = (os.getenv("PANELAI_DEBUG") or "1").strip().lower() in {"1", "true", "yes"}
    payload: dict[str, object] = {
        "detail": "Internal Server Error",
        "path": str(request.url.path),
    }
    if debug:
        payload["error"] = repr(exc)
        payload["trace"] = traceback.format_exc(limit=30)
    return JSONResponse(status_code=500, content=payload)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("PANELAI_CORS_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/samples")
def samples() -> list[dict[str, str]]:
    if not DATA_ROOT.exists():
        return []

    out: list[dict[str, str]] = []
    for d in sorted(DATA_ROOT.iterdir()):
        if not d.is_dir():
            continue
        jd = d / "job_description.md"
        resume = d / "resume.md"
        transcript = d / "transcript.md"
        if jd.exists() and resume.exists() and transcript.exists():
            out.append({"id": d.name, "job_description": jd.read_text(encoding="utf-8"), "resume": resume.read_text(encoding="utf-8"), "transcript": transcript.read_text(encoding="utf-8")})
    return out


@app.post("/evaluate", response_model=EvaluationResult)
async def evaluate(req: EvaluateRequest) -> EvaluationResult:
    if not req.job_description.strip() or not req.resume.strip() or not req.transcript.strip():
        raise HTTPException(status_code=400, detail="job_description, resume, and transcript are required")

    ctx = PanelContext(
        job_description=req.job_description,
        resume=req.resume,
        transcript=req.transcript,
        config=req.config or {},
    )

    return await run_panel(ctx=ctx)


@app.post("/assist", response_model=AssistResult)
async def assist(req: AssistRequest) -> AssistResult:
    if not req.job_description.strip() or not req.resume.strip():
        raise HTTPException(status_code=400, detail="job_description and resume are required")

    ctx = PanelContext(
        job_description=req.job_description,
        resume=req.resume,
        transcript=req.transcript or "",
        config=req.config or {},
    )

    return await run_assist(ctx=ctx)


@app.post("/evaluate-files", response_model=EvaluationResult)
async def evaluate_files(
    job_description: UploadFile = File(...),
    resume: UploadFile = File(...),
    transcript: UploadFile = File(...),
    config_json: str = Form(default="{}"),
) -> EvaluationResult:
    try:
        config = json.loads(config_json or "{}")
        if not isinstance(config, dict):
            raise ValueError("config_json must be a JSON object")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config_json: {e}")

    jd_text = (await job_description.read()).decode("utf-8", errors="replace").strip()
    resume_text = (await resume.read()).decode("utf-8", errors="replace").strip()
    transcript_text = (await transcript.read()).decode("utf-8", errors="replace").strip()

    if not jd_text or not resume_text or not transcript_text:
        raise HTTPException(status_code=400, detail="Uploaded files must not be empty")

    ctx = PanelContext(
        job_description=jd_text,
        resume=resume_text,
        transcript=transcript_text,
        config=config,
    )

    return await run_panel(ctx=ctx)
