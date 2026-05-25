"""
frontend/app.py
---------------
Streamlit UI for the Multi-Agent Financial Research Assistant.

Features:
  - Research query input
  - Real-time agent progress display (polling /status every 2 s)
  - Human-in-the-loop approval panel (Approve / Edit / Reject buttons)
  - Final report with source citations
  - RAGAS evaluation score display
  - Run history sidebar
"""

import json
import time

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"
POLL_INTERVAL = 2  # seconds between status polls

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Financial Research Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Dark gradient background */
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        min-height: 100vh;
    }

    /* Glassmorphism card */
    .glass-card {
        background: rgba(255, 255, 255, 0.07);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        margin-bottom: 16px;
    }

    /* Agent progress step */
    .agent-step {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        border-radius: 10px;
        margin-bottom: 8px;
        font-size: 14px;
        font-weight: 500;
    }
    .agent-step.active {
        background: linear-gradient(90deg, rgba(99,102,241,0.3), rgba(139,92,246,0.2));
        border: 1px solid rgba(99,102,241,0.5);
        animation: pulse 2s infinite;
    }
    .agent-step.done {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .agent-step.pending {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        opacity: 0.5;
    }
    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(99,102,241,0.4); }
        50%       { box-shadow: 0 0 0 6px rgba(99,102,241,0); }
    }

    /* Metric cards */
    .metric-row {
        display: flex;
        gap: 12px;
        margin-top: 12px;
    }
    .metric-card {
        flex: 1;
        background: linear-gradient(135deg, rgba(99,102,241,0.25), rgba(139,92,246,0.15));
        border: 1px solid rgba(139,92,246,0.3);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .metric-label {
        font-size: 11px;
        color: rgba(255,255,255,0.55);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        background: linear-gradient(90deg, #a78bfa, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Source badge */
    .source-badge {
        display: inline-block;
        background: rgba(99,102,241,0.2);
        border: 1px solid rgba(99,102,241,0.35);
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 12px;
        color: #a5b4fc;
        margin: 3px 3px 3px 0;
    }

    /* Report text box */
    .report-box {
        background: rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 20px 24px;
        line-height: 1.75;
        font-size: 15px;
        color: rgba(255,255,255,0.87);
        white-space: pre-wrap;
    }

    /* Approval buttons area */
    .approval-banner {
        background: linear-gradient(90deg, rgba(245,158,11,0.2), rgba(239,68,68,0.1));
        border: 1px solid rgba(245,158,11,0.4);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }

    /* Sidebar run history */
    .run-item {
        background: rgba(255,255,255,0.05);
        border-radius: 8px;
        padding: 8px 12px;
        margin-bottom: 6px;
        font-size: 12px;
        border-left: 3px solid #6366f1;
    }

    h1, h2, h3 { color: #fff !important; }
    p, li { color: rgba(255,255,255,0.8); }
    label { color: rgba(255,255,255,0.75) !important; }

    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        font-size: 14px;
        padding: 10px 22px;
        transition: all 0.2s ease;
    }
    .stButton > button:hover { transform: translateY(-1px); }

    textarea, .stTextArea textarea {
        background: rgba(255,255,255,0.07) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 10px !important;
        color: #fff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Session state defaults ─────────────────────────────────────────────────────
defaults = {
    "job_id": None,
    "status": None,
    "run_data": None,
    "polling": False,
    "show_edit": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helper functions ───────────────────────────────────────────────────────────

def api_get(path: str) -> dict | None:
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, payload: dict) -> dict | None:
    try:
        r = httpx.post(f"{API_BASE}{path}", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def _agent_step_html(label: str, icon: str, state: str) -> str:
    return (
        f'<div class="agent-step {state}">'
        f'  <span style="font-size:18px">{icon}</span>'
        f'  <span style="color:rgba(255,255,255,0.9)">{label}</span>'
        f"</div>"
    )


def render_agent_progress(current_agent: str):
    """Render coloured progress steps for the 3 agents."""
    agents = [
        ("researcher", "🔍", "Researcher — Retrieving SEC filing chunks"),
        ("analyst", "🧠", "Analyst — Identifying insights & risks"),
        ("human_approval", "👤", "Human Review — Awaiting your approval"),
        ("report_writer", "✍️", "Report Writer — Drafting final report"),
        ("evaluator", "📐", "Evaluator — Computing RAGAS scores"),
    ]

    done_states = {
        "researcher": [],
        "analyst": ["researcher"],
        "awaiting_approval": ["researcher", "analyst"],
        "human_approval": ["researcher", "analyst"],
        "report_writer": ["researcher", "analyst", "human_approval"],
        "evaluator": ["researcher", "analyst", "human_approval", "report_writer"],
        "completed": ["researcher", "analyst", "human_approval", "report_writer", "evaluator"],
    }

    completed = set(done_states.get(current_agent, []))
    html = ""
    for key, icon, label in agents:
        if key in completed:
            html += _agent_step_html(label, "✅", "done")
        elif key == current_agent or (current_agent == "awaiting_approval" and key == "human_approval"):
            html += _agent_step_html(label + " …", icon, "active")
        else:
            html += _agent_step_html(label, icon, "pending")

    st.markdown(f'<div class="glass-card">{html}</div>', unsafe_allow_html=True)


def render_analysis(analysis: dict):
    """Pretty-print the analyst's structured JSON output."""
    if not analysis:
        return
    st.markdown("### 🧠 Analyst Output")
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📌 Summary**")
            st.info(analysis.get("summary", "—"))
            st.markdown("**💡 Key Insights**")
            for ins in analysis.get("key_insights", []):
                st.markdown(f"- {ins}")
        with col2:
            st.markdown("**⚠️ Risks**")
            for r in analysis.get("risks", []):
                severity_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(r.get("severity", ""), "⚪")
                st.markdown(
                    f"{severity_color} **{r.get('risk')}** ({r.get('severity')})  \n"
                    f"{r.get('description', '')}"
                )
            st.markdown("**🚀 Opportunities**")
            for o in analysis.get("opportunities", []):
                impact_color = {"High": "🟣", "Medium": "🔵", "Low": "⚫"}.get(o.get("potential_impact", ""), "⚪")
                st.markdown(
                    f"{impact_color} **{o.get('opportunity')}** ({o.get('potential_impact')})  \n"
                    f"{o.get('description', '')}"
                )

        # Financial metrics
        metrics = analysis.get("financial_metrics", {})
        if metrics:
            st.markdown("**📊 Key Financial Metrics**")
            cols = st.columns(min(len(metrics), 4))
            for i, (name, value) in enumerate(metrics.items()):
                with cols[i % len(cols)]:
                    st.metric(name, value)


def render_report(report: str, citations: list | None):
    """Render the final report and source citations."""
    st.markdown("### 📄 Financial Research Report")
    st.markdown(f'<div class="report-box">{report}</div>', unsafe_allow_html=True)

    if citations:
        st.markdown("**📚 Sources**")
        badges = ""
        for c in citations:
            badges += (
                f'<span class="source-badge">'
                f'[{c["source_n"]}] {c["company"]} ({c["ticker"]}) — {c["filing"]}'
                f"</span>"
            )
        st.markdown(badges, unsafe_allow_html=True)


def render_evaluation_scores(scores: dict):
    """Render RAGAS evaluation scores as metric cards."""
    if not scores:
        return

    st.markdown("### 📐 RAGAS Evaluation")
    if scores.get("error"):
        st.warning(f"Evaluation error: {scores['error']}")
        return

    faithfulness = scores.get("faithfulness")
    context_recall = scores.get("context_recall")
    latency = scores.get("latency_s")

    def fmt(v):
        return f"{v:.2f}" if v is not None else "N/A"

    def color(v):
        if v is None:
            return "#94a3b8"
        if v >= 0.8:
            return "#10b981"
        if v >= 0.5:
            return "#f59e0b"
        return "#ef4444"

    st.markdown(
        f"""
        <div class="metric-row">
          <div class="metric-card">
            <div class="metric-label">Faithfulness</div>
            <div class="metric-value" style="color:{color(faithfulness)}">{fmt(faithfulness)}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Context Recall</div>
            <div class="metric-value" style="color:{color(context_recall)}">{fmt(context_recall)}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Eval Latency</div>
            <div class="metric-value" style="font-size:20px;color:#60a5fa">{f'{latency:.1f}s' if latency else 'N/A'}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Sidebar: run history ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗂️ Run History")
    history = api_get("/runs") or []
    if not history:
        st.caption("No runs yet.")
    for run in history[:10]:
        status_icon = {
            "completed": "✅",
            "running": "⏳",
            "awaiting_approval": "👤",
            "error": "❌",
            "rejected": "🚫",
        }.get(run.get("status", ""), "❓")
        st.markdown(
            f'<div class="run-item">'
            f'<b>{status_icon} {run.get("status", "?").upper()}</b><br>'
            f'<small style="color:#a5b4fc">{run.get("query", "")[:50]}</small>'
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("**API:** `http://localhost:8000`")
    st.markdown("**Docs:** [/docs](http://localhost:8000/docs)")


# ── Main content ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <h1 style="
        background: linear-gradient(90deg, #a78bfa, #60a5fa, #34d399);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.4rem;
        font-weight: 700;
        margin-bottom: 4px;
    ">📊 Financial Research Assistant</h1>
    <p style="color:rgba(255,255,255,0.55);font-size:15px;margin-top:0">
        Multi-agent LangGraph pipeline · RAG over SEC 10-K filings · Human-in-the-loop
    </p>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ── Query input ────────────────────────────────────────────────────────────────
if st.session_state.job_id is None:
    with st.form("query_form", clear_on_submit=False):
        query = st.text_area(
            "🔎 Enter your financial research question",
            placeholder=(
                "e.g. Compare the revenue growth and AI strategies of Apple, Microsoft, "
                "and Google based on their most recent 10-K filings."
            ),
            height=110,
            key="query_input",
        )
        submitted = st.form_submit_button(
            "🚀 Run Research Pipeline", use_container_width=True
        )

    if submitted and query.strip():
        with st.spinner("Submitting query …"):
            resp = api_post("/run", {"query": query.strip()})
        if resp and "job_id" in resp:
            st.session_state.job_id = resp["job_id"]
            st.session_state.status = "running"
            st.session_state.polling = True
            st.rerun()
        else:
            st.error("Failed to start pipeline. Is the FastAPI server running on port 8000?")

# ── Active pipeline view ───────────────────────────────────────────────────────
else:
    job_id = st.session_state.job_id

    # ── Poll status ────────────────────────────────────────────────────────────
    run_data = api_get(f"/status/{job_id}")
    if run_data:
        st.session_state.run_data = run_data
        st.session_state.status = run_data.get("status")

    data = st.session_state.run_data or {}
    current_status = data.get("status", "running")
    current_agent = data.get("current_agent", "researcher")

    # ── Header row ─────────────────────────────────────────────────────────────
    col_h1, col_h2 = st.columns([5, 1])
    with col_h1:
        st.markdown(f"**Query:** {data.get('query', '')}")
        st.caption(f"Job ID: `{job_id}`")
    with col_h2:
        if st.button("🔄 New Query", use_container_width=True):
            for k in ["job_id", "status", "run_data", "polling", "show_edit"]:
                st.session_state[k] = None if k not in ("polling", "show_edit") else False
            st.rerun()

    st.divider()

    # ── Agent progress ─────────────────────────────────────────────────────────
    st.markdown("### ⚡ Pipeline Progress")
    render_agent_progress(current_agent)

    # ── Error state ────────────────────────────────────────────────────────────
    if current_status == "error":
        st.error(f"❌ Pipeline error: {data.get('error', 'Unknown error')}")

    # ── Rejected state ─────────────────────────────────────────────────────────
    elif current_status == "rejected":
        st.warning("🚫 Run was rejected by the user.")

    # ── Awaiting approval ──────────────────────────────────────────────────────
    elif current_status == "awaiting_approval":
        st.markdown(
            '<div class="approval-banner">'
            "<b>👤 Human Review Required</b> — The Analyst has completed its analysis. "
            "Please review the findings below and choose an action."
            "</div>",
            unsafe_allow_html=True,
        )

        analysis = data.get("analysis") or {}
        render_analysis(analysis)

        st.divider()
        st.markdown("### 🗳️ Your Decision")

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            if st.button("✅ Approve & Generate Report", use_container_width=True, type="primary"):
                resp = api_post(f"/approve/{job_id}", {"decision": "approve"})
                if resp:
                    st.success("Approved! Generating report …")
                    st.session_state.status = "running"
                    time.sleep(1)
                    st.rerun()

        with col_b:
            if st.button("✏️ Edit Analysis", use_container_width=True):
                st.session_state.show_edit = True
                st.rerun()

        with col_c:
            if st.button("❌ Reject", use_container_width=True):
                resp = api_post(f"/approve/{job_id}", {"decision": "reject"})
                if resp:
                    st.warning("Run rejected.")
                    time.sleep(1)
                    st.rerun()

        # ── Edit panel ─────────────────────────────────────────────────────────
        if st.session_state.show_edit:
            st.markdown("**✏️ Edit Analysis JSON**")
            edited_str = st.text_area(
                "Modify the JSON below, then click Submit Edit",
                value=json.dumps(analysis, indent=2),
                height=300,
                key="edit_area",
            )
            if st.button("📤 Submit Edited Analysis", type="primary"):
                try:
                    edited_analysis = json.loads(edited_str)
                    resp = api_post(
                        f"/approve/{job_id}",
                        {"decision": "edit", "edited_analysis": edited_analysis},
                    )
                    if resp:
                        st.success("Edited analysis submitted! Generating report …")
                        st.session_state.show_edit = False
                        time.sleep(1)
                        st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")

    # ── Running ────────────────────────────────────────────────────────────────
    elif current_status == "running":
        st.info("⏳ Pipeline is running … page auto-refreshes every 2 seconds.")
        time.sleep(POLL_INTERVAL)
        st.rerun()

    # ── Completed ──────────────────────────────────────────────────────────────
    elif current_status == "completed":
        # Show analysis (collapsed)
        with st.expander("🧠 Analyst Output", expanded=False):
            render_analysis(data.get("analysis") or {})

        st.divider()

        # Final report
        render_report(
            data.get("report", "Report not available."),
            data.get("analysis", {}).get("citations") if isinstance(data.get("analysis"), dict) else None,
        )

        st.divider()

        # RAGAS scores
        render_evaluation_scores(data.get("evaluation_scores") or {})

        # Token & latency stats
        with st.expander("📊 Run Statistics", expanded=False):
            token_counts = data.get("token_counts") or {}
            latencies = data.get("latencies") or {}
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Token Usage**")
                for agent, count in token_counts.items():
                    st.metric(agent.replace("_", " ").title(), f"{count:,} tokens")
            with col2:
                st.markdown("**Latency**")
                for agent, secs in latencies.items():
                    st.metric(agent.replace("_", " ").title(), f"{secs:.1f}s")

    # ── Unknown/transitioning state — keep polling ─────────────────────────────
    else:
        st.info(f"Status: {current_status} … refreshing")
        time.sleep(POLL_INTERVAL)
        st.rerun()
