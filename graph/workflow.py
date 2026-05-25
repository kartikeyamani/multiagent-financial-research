"""
graph/workflow.py
-----------------
LangGraph orchestration for the 3-agent pipeline:
  Researcher → Analyst → [Human-in-the-Loop interrupt] → Report Writer → Evaluator

State is persisted via MemorySaver (in-memory checkpointing), which enables
the graph to pause at the human approval node and resume after a user decision.
"""

import logging
import time
from typing import Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


# ── Graph State ────────────────────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    """Shared state propagated through every node of the graph."""
    query: str                           # original research question
    job_id: str                          # unique identifier for this run
    current_agent: str                   # name of the active / last-completed agent
    retrieved_chunks: list[dict]         # output of Researcher
    analysis: Optional[dict]            # output of Analyst (structured JSON)
    approval_decision: Optional[str]    # "approve" | "edit" | "reject"
    edited_analysis: Optional[dict]     # user-supplied edited analysis (optional)
    report: Optional[str]               # output of Report Writer
    citations: Optional[list[dict]]     # citation metadata from Report Writer
    evaluation_scores: Optional[dict]   # RAGAS scores
    token_counts: dict                   # per-agent token usage
    latencies: dict                      # per-agent wall-clock time (seconds)
    error: Optional[str]                # error message if any node fails


# ── Node: Researcher ───────────────────────────────────────────────────────────
def researcher_node(state: AgentState) -> dict:
    """Run the Researcher agent to retrieve relevant SEC filing chunks."""
    from agents.researcher import ResearcherAgent
    from database.db import update_run

    job_id = state.get("job_id", "unknown")
    logger.info(f"[Graph:Researcher] Starting | job_id={job_id}")
    update_run(job_id, status="running", current_agent="researcher")

    t0 = time.time()
    try:
        agent = ResearcherAgent()
        result = agent.run(state["query"])
    except Exception as e:
        logger.error(f"[Graph:Researcher] Error: {e}")
        update_run(job_id, status="error", error=str(e))
        return {"error": str(e), "current_agent": "researcher"}

    latency = time.time() - t0
    update_run(
        job_id,
        current_agent="analyst",
        retrieved_chunks=result["chunks"],
        token_counts={**state.get("token_counts", {}), "researcher": result["token_count"]},
        latencies={**state.get("latencies", {}), "researcher": round(latency, 2)},
    )
    return {
        "retrieved_chunks": result["chunks"],
        "current_agent": "analyst",
        "token_counts": {**state.get("token_counts", {}), "researcher": result["token_count"]},
        "latencies": {**state.get("latencies", {}), "researcher": round(latency, 2)},
    }


# ── Node: Analyst ──────────────────────────────────────────────────────────────
def analyst_node(state: AgentState) -> dict:
    """Run the Analyst agent to produce structured financial insights."""
    from agents.analyst import AnalystAgent
    from database.db import update_run

    job_id = state.get("job_id", "unknown")
    logger.info(f"[Graph:Analyst] Starting | job_id={job_id}")
    update_run(job_id, current_agent="analyst")

    t0 = time.time()
    try:
        agent = AnalystAgent()
        result = agent.run(state["retrieved_chunks"], state["query"])
    except Exception as e:
        logger.error(f"[Graph:Analyst] Error: {e}")
        update_run(job_id, status="error", error=str(e))
        return {"error": str(e), "current_agent": "analyst"}

    latency = time.time() - t0
    update_run(
        job_id,
        current_agent="awaiting_approval",
        analysis=result["analysis"],
        token_counts={**state.get("token_counts", {}), "analyst": result["token_count"]},
        latencies={**state.get("latencies", {}), "analyst": round(latency, 2)},
    )
    return {
        "analysis": result["analysis"],
        "current_agent": "awaiting_approval",
        "token_counts": {**state.get("token_counts", {}), "analyst": result["token_count"]},
        "latencies": {**state.get("latencies", {}), "analyst": round(latency, 2)},
    }


# ── Node: Human Approval (interrupt) ──────────────────────────────────────────
def human_approval_node(state: AgentState) -> dict:
    """
    Pause the graph and surface the analysis to the human for review.
    The graph will stay suspended here until the caller resumes it via:
        graph.invoke(Command(resume={"decision": "approve"|"edit"|"reject",
                                    "edited_analysis": {...} | None}), config=config)
    """
    from database.db import update_run

    job_id = state.get("job_id", "unknown")
    logger.info(f"[Graph:HumanApproval] Pausing for human review | job_id={job_id}")
    update_run(job_id, status="awaiting_approval", current_agent="human_approval")

    # ── This call pauses the graph; value is sent back to the caller ───────────
    decision_payload: dict = interrupt(
        {
            "analysis": state.get("analysis"),
            "message": "Please review the analyst's findings.",
            "job_id": job_id,
        }
    )

    decision = decision_payload.get("decision", "reject")
    edited_analysis = decision_payload.get("edited_analysis")

    logger.info(f"[Graph:HumanApproval] Decision received: {decision} | job_id={job_id}")
    update_run(
        job_id,
        approval_decision=decision,
        current_agent="report_writer" if decision == "approve" else "rejected",
    )
    return {
        "approval_decision": decision,
        "edited_analysis": edited_analysis,
        "current_agent": "report_writer" if decision == "approve" else "rejected",
    }


# ── Node: Report Writer ────────────────────────────────────────────────────────
def report_writer_node(state: AgentState) -> dict:
    """Write the final ~300-word research report with citations."""
    from agents.report_writer import ReportWriterAgent
    from database.db import update_run

    job_id = state.get("job_id", "unknown")
    logger.info(f"[Graph:ReportWriter] Starting | job_id={job_id}")
    update_run(job_id, current_agent="report_writer")

    # Use edited analysis if the user provided one, else fall back to original
    analysis = state.get("edited_analysis") or state.get("analysis", {})

    t0 = time.time()
    try:
        agent = ReportWriterAgent()
        result = agent.run(analysis, state["retrieved_chunks"], state["query"])
    except Exception as e:
        logger.error(f"[Graph:ReportWriter] Error: {e}")
        update_run(job_id, status="error", error=str(e))
        return {"error": str(e), "current_agent": "report_writer"}

    latency = time.time() - t0
    update_run(
        job_id,
        current_agent="evaluator",
        report=result["report"],
        token_counts={**state.get("token_counts", {}), "report_writer": result["token_count"]},
        latencies={**state.get("latencies", {}), "report_writer": round(latency, 2)},
    )
    return {
        "report": result["report"],
        "citations": result["citations"],
        "current_agent": "evaluator",
        "token_counts": {**state.get("token_counts", {}), "report_writer": result["token_count"]},
        "latencies": {**state.get("latencies", {}), "report_writer": round(latency, 2)},
    }


# ── Node: Evaluator ────────────────────────────────────────────────────────────
def evaluator_node(state: AgentState) -> dict:
    """Run RAGAS evaluation and persist scores."""
    from evaluation.ragas_eval import evaluate_run
    from database.db import update_run

    job_id = state.get("job_id", "unknown")
    logger.info(f"[Graph:Evaluator] Computing RAGAS scores | job_id={job_id}")

    scores = evaluate_run(
        query=state["query"],
        report=state.get("report", ""),
        chunks=state.get("retrieved_chunks", []),
    )

    update_run(
        job_id,
        status="completed",
        current_agent="completed",
        evaluation_scores=scores,
    )
    logger.info(
        f"[Graph:Evaluator] Done | faithfulness={scores.get('faithfulness')} "
        f"context_recall={scores.get('context_recall')} | job_id={job_id}"
    )
    return {"evaluation_scores": scores, "current_agent": "completed"}


# ── Routing ────────────────────────────────────────────────────────────────────
def route_after_approval(state: AgentState) -> str:
    """Route to report_writer if approved, else end the graph."""
    decision = state.get("approval_decision", "reject")
    if decision == "approve":
        return "report_writer"
    return END


# ── Graph Assembly ─────────────────────────────────────────────────────────────
def _build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("report_writer", report_writer_node)
    workflow.add_node("evaluator", evaluator_node)

    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "human_approval")
    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {"report_writer": "report_writer", END: END},
    )
    workflow.add_edge("report_writer", "evaluator")
    workflow.add_edge("evaluator", END)

    return workflow


# ── Singleton compiled graph with MemorySaver checkpointing ───────────────────
_memory = MemorySaver()
compiled_graph = _build_graph().compile(checkpointer=_memory)

logger.info("[Graph] LangGraph workflow compiled with MemorySaver checkpointing")
