# CLAUDE.md — Multi-Agent Financial Research Assistant

## What This Project Is

A **production-grade multi-agent AI system** that answers financial research questions using SEC 10-K filings. It demonstrates collaborative LLM agents with a human-in-the-loop approval gate, built on LangGraph + FastAPI + Streamlit.

A user submits a research question → three sequential agents process it → the human reviews and approves the analysis → a final report is generated with source citations and quality evaluation scores.

---

## Architecture at a Glance

```
Streamlit UI (port 8501)
    ↕ HTTP (httpx)
FastAPI Backend (port 8000)
    ↕ LangGraph
3-Agent Workflow ──── SQLite (runs.db)
    ↕ OpenAI API
FAISS + BM25 RAG ──── SEC Filing Data (AAPL, MSFT, GOOGL)
```

---

## The Three Agents

| Agent | File | Model | Role |
|-------|------|-------|------|
| Researcher | `agents/researcher.py` | None (pure retrieval) | Hybrid RAG → top-5 chunks |
| Analyst | `agents/analyst.py` | `gpt-4.1` | Structured JSON analysis (summary, risks, opportunities, metrics) |
| Report Writer | `agents/report_writer.py` | `gpt-4.1` | ~300-word prose report with inline `[Source N]` citations |

---

## LangGraph Workflow

```
researcher_node
    ↓
analyst_node
    ↓
human_approval_node  ← ⏸ INTERRUPT — pauses here waiting for user
    ↓ (approve / edit / reject)
report_writer_node
    ↓
evaluator_node
    ↓
END
```

Human approval is implemented via LangGraph's `interrupt()`. The FastAPI layer runs the graph in a background thread (`threading.Event`) so the async API stays non-blocking while the graph is paused.

---

## RAG Pipeline

- **Data:** 15 SEC filing excerpts across AAPL, MSFT, GOOGL (`data/sample_filings.py`)
- **Chunking:** `TokenTextSplitter` — 512 tokens, 20% overlap
- **Embeddings:** OpenAI `text-embedding-3-small` → FAISS index
- **Retrieval:** Hybrid search — 60% FAISS (semantic) + 40% BM25 (keyword) fused via Reciprocal Rank Fusion (RRF)
- **Index storage:** `./faiss_index/` (FAISS), `./faiss_index_docs.json` (BM25 cache)

---

## API Endpoints (`api/routes.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/run` | POST | Submit query → returns `job_id` |
| `/status/{job_id}` | GET | Poll for current state + all results |
| `/approve/{job_id}` | POST | Send `approve` / `edit` / `reject` decision |
| `/runs` | GET | List recent run history (default 20) |
| `/health` | GET | Health check |

---

## Shared State (`graph/workflow.py`)

```python
class AgentState(TypedDict):
    query: str
    job_id: str
    current_agent: str
    retrieved_chunks: list[dict]
    analysis: Optional[dict]          # analyst output (structured JSON)
    approval_decision: Optional[str]  # "approve" | "edit" | "reject"
    edited_analysis: Optional[dict]   # user-modified analysis
    report: Optional[str]
    citations: Optional[list[dict]]
    evaluation_scores: Optional[dict]
    token_counts: dict
    latencies: dict
    error: Optional[str]
```

---

## Evaluation (`evaluation/ragas_eval.py`)

Uses **RAGAS** with GPT-4 as judge:
- **Faithfulness** — does the report only assert facts present in retrieved chunks?
- **Context Recall** — did retrieval surface the chunks needed to answer the question?

Note: currently uses query as ground truth placeholder; scores are approximate without a labeled dataset.

---

## Database (`database/db.py`)

SQLite (`runs.db`) with a single `run_history` table. WAL mode enabled for concurrent reads. All `dict`/`list` fields are JSON-serialized. Auto-created on startup.

---

## Entry Points

```bash
# Backend API (port 8000)
python main.py
# or
uvicorn main:app --reload --port 8000

# Frontend (port 8501)
streamlit run frontend/app.py

# Rebuild RAG index manually
python -m rag.ingest

# Check available OpenAI models
python check_models.py
```

---

## Environment

Copy `.env.example` → `.env` and set:
```
OPENAI_API_KEY=sk-...
```

---

## Key Dependencies

| Category | Libraries |
|----------|-----------|
| Web | fastapi, uvicorn, httpx |
| LLM Orchestration | langgraph, langchain, langchain-openai |
| Retrieval | faiss-cpu, rank-bm25, tiktoken |
| Frontend | streamlit |
| Evaluation | ragas, datasets |
| Storage | sqlite3 (stdlib), python-dotenv |

---

## Directory Structure

```
multiagent/
├── main.py                    # FastAPI app + startup (DB init, RAG warmup)
├── requirements.txt
├── .env / .env.example        # OPENAI_API_KEY
├── check_models.py            # Utility: list available GPT models
├── project_walkthrough.md     # Extended documentation
│
├── agents/
│   ├── researcher.py          # RAG retrieval node
│   ├── analyst.py             # GPT-4.1 → structured JSON
│   └── report_writer.py       # GPT-4.1 → prose report + citations
│
├── graph/
│   └── workflow.py            # LangGraph graph + AgentState definition
│
├── rag/
│   ├── pipeline.py            # Hybrid FAISS + BM25 retriever
│   └── ingest.py              # Index builder (chunking + embeddings)
│
├── data/
│   └── sample_filings.py      # 15 sample SEC filing excerpts
│
├── database/
│   └── db.py                  # SQLite schema + CRUD helpers
│
├── api/
│   └── routes.py              # FastAPI route handlers
│
├── evaluation/
│   └── ragas_eval.py          # RAGAS faithfulness + context recall
│
├── frontend/
│   └── app.py                 # Streamlit UI (glassmorphism dark theme)
│
├── faiss_index/               # Auto-created: FAISS vector store
└── faiss_index_docs.json      # Auto-created: BM25 document cache
```

---

## Full Request Lifecycle

1. User submits query in Streamlit
2. `POST /run` → FastAPI creates `job_id`, spawns background thread
3. **Phase 1:** Researcher retrieves chunks → Analyst generates JSON → `interrupt()` fires → thread blocks
4. Streamlit polls `/status` → shows analyst output + approval buttons
5. User approves (or edits JSON, then approves)
6. `POST /approve` → event unblocks background thread
7. **Phase 2:** Report Writer generates report → Evaluator runs RAGAS → status = `completed`
8. Streamlit renders final report, citations, token counts, latency, and RAGAS scores

Total wall-clock time: ~30–90 seconds depending on GPT-4.1 response times.
