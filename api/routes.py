"""
api/routes.py
-------------
FastAPI routes for the Multi-Agent Financial Research Assistant.

Endpoints:
  POST /run               – Submit a new research query; returns job_id
  GET  /status/{job_id}  – Poll for current agent status and results
  POST /approve/{job_id} – Human approval gate (approve / edit / reject)
  GET  /runs             – List recent run history
"""

import logging
import math
import threading
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from langgraph.types import Command
from pydantic import BaseModel

from database.db import create_run, get_run, list_runs, update_run
from graph.workflow import compiled_graph

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    query: str


class ApprovalRequest(BaseModel):
    decision: str                           # "approve" | "edit" | "reject"
    edited_analysis: Optional[dict] = None  # only for "edit"


# ── In-process approval signals ───────────────────────────────────────────────
# job_id → threading.Event  (set by /approve to unblock the background thread)
# job_id → payload dict     (the user's decision)

_approval_events:   dict[str, threading.Event] = {}
_approval_payloads: dict[str, dict]            = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_interrupt_chunk(chunk: dict) -> bool:
    """
    Detect the LangGraph interrupt chunk regardless of minor version differences.
    LangGraph emits interrupts as {"__interrupt__": ...} in stream updates.
    """
    return "__interrupt__" in chunk


def _wait_for_approval(job_id: str, timeout: int = 3600) -> dict:
    """
    Block the calling thread until /approve signals the event.
    Returns the approval payload (defaulting to reject on timeout).
    """
    event = _approval_events.get(job_id)
    if event is None:
        event = threading.Event()
        _approval_events[job_id] = event

    logger.info(f"[Runner] Waiting for human approval | job_id={job_id}")
    fired = event.wait(timeout=timeout)
    if not fired:
        logger.warning(f"[Runner] Approval timed out after {timeout}s | job_id={job_id}")

    return _approval_payloads.pop(job_id, {"decision": "reject"})


# ── Background graph runner ───────────────────────────────────────────────────

def _run_graph(job_id: str, query: str) -> None:
    """
    Run the full LangGraph pipeline in a background thread.

    Phase 1: stream until interrupt() fires in human_approval_node
    Phase 2: resume with user decision, stream to completion
    """
    thread_config = {"configurable": {"thread_id": job_id}}
    initial_state = {
        "query": query,
        "job_id": job_id,
        "current_agent": "researcher",
        "token_counts": {},
        "latencies": {},
    }

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    logger.info(f"[Runner] Phase 1 starting | job_id={job_id}")
    interrupted = False
    payload: dict = {"decision": "reject"}   # safe default

    try:
        for chunk in compiled_graph.stream(
            initial_state,
            config=thread_config,
            stream_mode="updates",
        ):
            # ── Log node completions ───────────────────────────────────────────
            for node_name, node_output in chunk.items():
                if node_name == "__interrupt__":
                    continue
                if isinstance(node_output, dict) and "current_agent" in node_output:
                    logger.info(
                        f"[Runner] ✓ {node_name} → next={node_output['current_agent']}"
                        f" | job_id={job_id}"
                    )

            # ── Detect interrupt ───────────────────────────────────────────────
            if _is_interrupt_chunk(chunk):
                logger.info(f"[Runner] ⏸  Interrupt detected | job_id={job_id}")
                # Ensure DB reflects awaiting state (node may have already set it)
                update_run(job_id, status="awaiting_approval", current_agent="human_approval")
                interrupted = True
                payload = _wait_for_approval(job_id)
                logger.info(f"[Runner] ▶  Resuming | decision={payload.get('decision')} | job_id={job_id}")
                break

    except Exception as e:
        logger.error(f"[Runner] Phase 1 error: {e} | job_id={job_id}", exc_info=True)
        update_run(job_id, status="error", error=str(e))
        _approval_events.pop(job_id, None)
        return

    # ── If interrupt never fired, check if graph finished or errored ───────────
    if not interrupted:
        logger.warning(f"[Runner] Phase 1 ended without interrupt | job_id={job_id}")
        run = get_run(job_id)
        current_status = run.get("status") if run else "unknown"
        logger.warning(f"[Runner] Final DB status={current_status} | job_id={job_id}")
        # Nothing more to do — graph ran to completion or errored
        _approval_events.pop(job_id, None)
        return

    # ── Handle reject ──────────────────────────────────────────────────────────
    if payload.get("decision") == "reject":
        logger.info(f"[Runner] ✗ Run rejected | job_id={job_id}")
        update_run(job_id, status="rejected", current_agent="rejected")
        _approval_events.pop(job_id, None)
        return

    # ── Phase 2 ───────────────────────────────────────────────────────────────
    logger.info(f"[Runner] Phase 2 starting | job_id={job_id}")
    update_run(job_id, status="running", current_agent="report_writer")

    try:
        for chunk in compiled_graph.stream(
            Command(resume=payload),
            config=thread_config,
            stream_mode="updates",
        ):
            for node_name, node_output in chunk.items():
                if isinstance(node_output, dict) and "current_agent" in node_output:
                    logger.info(
                        f"[Runner] ✓ {node_name} → next={node_output['current_agent']}"
                        f" | job_id={job_id}"
                    )
    except Exception as e:
        logger.error(f"[Runner] Phase 2 error: {e} | job_id={job_id}", exc_info=True)
        update_run(job_id, status="error", error=str(e))

    _approval_events.pop(job_id, None)
    logger.info(f"[Runner] ✅ Pipeline complete | job_id={job_id}")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/run")
async def run_pipeline(req: RunRequest, background_tasks: BackgroundTasks):
    """Submit a new research query. Returns a job_id for polling."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    job_id = str(uuid.uuid4())
    create_run(job_id, req.query)
    update_run(job_id, status="running", current_agent="researcher")

    # Pre-register event BEFORE starting the thread to avoid a tiny race window
    _approval_events[job_id] = threading.Event()

    background_tasks.add_task(_run_graph, job_id, req.query)

    logger.info(f"[API] New run | job_id={job_id} | query='{req.query[:60]}'")
    return {"job_id": job_id, "status": "running", "message": "Pipeline started."}


def _json_safe(obj: Any) -> Any:
    """Recursively replace NaN/Inf floats with None for JSON safety."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Return the full run record for a job (poll every 2 s from the UI)."""
    run = get_run(job_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return _json_safe(run)


@router.post("/approve/{job_id}")
async def approve_run(job_id: str, req: ApprovalRequest):
    """
    Human approval gate.
      approve → proceed to Report Writer
      edit    → proceed with user-modified analysis
      reject  → abort
    
    Accepts both "awaiting_approval" AND "running" statuses to tolerate
    the small window between the node setting the interrupt and the DB update.
    """
    if req.decision not in ("approve", "edit", "reject"):
        raise HTTPException(
            status_code=400,
            detail="decision must be one of: approve, edit, reject",
        )

    run = get_run(job_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    # Accept "awaiting_approval" OR "running" — the interrupt may have fired
    # before the DB write completed, causing a brief "running" window.
    allowed_statuses = ("awaiting_approval", "running")
    if run.get("status") not in allowed_statuses:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot approve job in status '{run.get('status')}'. "
                f"Expected one of: {allowed_statuses}"
            ),
        )

    # Build resume payload
    payload: dict = {"decision": req.decision}
    if req.decision == "edit" and req.edited_analysis:
        payload["edited_analysis"] = req.edited_analysis
        payload["decision"] = "approve"

    # Store payload and signal the background thread
    _approval_payloads[job_id] = payload
    event = _approval_events.get(job_id)
    if event:
        event.set()
    else:
        # Thread not waiting yet — it will pick up the payload when it reaches wait
        logger.warning(
            f"[API] No event found for job_id={job_id} — payload stored for pickup"
        )

    logger.info(f"[API] Approval: decision={req.decision} | job_id={job_id}")
    return {"job_id": job_id, "decision": req.decision, "message": "Decision recorded."}


@router.get("/runs")
async def list_recent_runs(limit: int = 20):
    """List the most recent pipeline runs."""
    return list_runs(limit=limit)
