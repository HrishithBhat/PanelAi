from __future__ import annotations

import re
from dataclasses import dataclass

from ..llm.factory import get_provider
from .base import AgentResult, Finding, PanelContext


def _heuristic_transcript_summary(transcript: str) -> str:
    lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
    if not lines:
        return "Heuristic summary: (empty transcript)"

    t = transcript.lower()
    bullets: list[str] = []

    # Pull a few strong-signal lines
    for ln in lines:
        low = ln.lower()
        if any(w in low for w in ("built", "designed", "implemented", "scaled", "migrated", "owned", "led")):
            bullets.append(ln)
        if len(bullets) >= 4:
            break

    # Add uncertainty markers if present
    if any(p in t for p in ("i don't know", "i dont know", "not sure", "haven't used", "never used")):
        bullets.append("Uncertainty detected (e.g., 'not sure' / 'haven't used').")

    if not bullets:
        bullets = lines[:3]

    bullets = bullets[:6]
    return "Heuristic summary (evidence-oriented):\n" + "\n".join(f"- {b}" for b in bullets)


def _chunk_transcript(transcript: str) -> list[str]:
    # Split into short chunks for evidence retrieval.
    lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    for ln in lines:
        buf.append(ln)
        if len(" ".join(buf)) > 360:
            chunks.append(" ".join(buf))
            buf = []
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_+.#-]{0,}", text.lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "have",
        "from",
        "were",
        "what",
        "when",
        "then",
        "they",
        "them",
        "into",
        "about",
        "just",
        "like",
        "kind",
        "sort",
    }
    short_ok = {"go", "c", "js", "ts", "ai", "ml", "db", "ci", "cd"}
    return {w for w in words if w not in stop and (len(w) >= 3 or w in short_ok)}


def _best_evidence(claim: str, chunks: list[str]) -> tuple[str, float]:
    c = _tokenize(claim)
    best = ("", 0.0)
    for ch in chunks:
        t = _tokenize(ch)
        if not c or not t:
            continue
        overlap = len(c & t)
        # For short claims (e.g., a single technology), an exact mention is strong evidence.
        score = overlap / max(1, len(c))
        if overlap > 0 and len(c) <= 2:
            score = max(score, 0.95)
        if claim.strip() and claim.strip().lower() in ch.lower():
            score = max(score, 0.85)
        if score > best[1]:
            best = (ch, score)
    return best


@dataclass
class TranscriptEvidenceAgent:
    name: str = "transcript-evidence"

    async def run(self, ctx: PanelContext) -> AgentResult:
        llm = get_provider()
        chunks = _chunk_transcript(ctx.transcript)

        if getattr(llm, "name", "") == "heuristic":
            summary_text = _heuristic_transcript_summary(ctx.transcript)
        else:
            summary = await llm.complete(
                system="You summarize interview transcripts for a technical interview panel.",
                user=(
                    "Summarize the transcript focusing on what the candidate *demonstrated* (not claims). "
                    "Include concrete evidence snippets.\n\nTranscript:\n" + ctx.transcript
                ),
            )
            summary_text = summary.text

        return AgentResult(
            findings=[
                Finding(
                    category="transcript_summary",
                    summary="Transcript condensed into evidence-oriented summary.",
                    severity="low",
                    evidence=summary_text,
                )
            ],
            artifacts={"chunks": chunks, "summary": summary_text},
        )

    async def respond_to_challenge(self, ctx: PanelContext, challenge: str) -> str:
        llm = get_provider()
        resp = await llm.complete(
            system="You cite transcript evidence precisely and avoid overclaiming.",
            user=f"Challenge: {challenge}\n\nTranscript:\n{ctx.transcript}\n",
        )
        return resp.text


# Export helpers for orchestrator
__all__ = ["_chunk_transcript", "_best_evidence", "TranscriptEvidenceAgent"]
