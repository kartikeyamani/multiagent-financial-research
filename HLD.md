# High Level Design — Production Multi-Agent Financial Research Assistant

## 1. System Overview

A user asks a financial research question. The system retrieves relevant SEC
filing data, runs it through a 3-agent AI pipeline, pauses for human review,
generates a final report, and evaluates its quality. Every step is persisted,
observable, and recoverable from failures.

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                   │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    Streamlit Frontend                           │  │
│   │         (browser-based UI, polls status every 2s)              │  │
│   └────────────────────────────┬────────────────────────────────────┘  │
└────────────────────────────────│────────────────────────────────────────┘
                                 │ HTTPS (JWT in header)
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                           API LAYER                                     │
│                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │
│   │   FastAPI    │    │   FastAPI    │    │   FastAPI    │  (N replicas│
│   │  Instance 1  │    │  Instance 2  │    │  Instance 3  │  behind LB) │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘            │
│          │  Auth Middleware (JWT verify on every request)              │
│          │  Rate Limiter (per user token budget)                       │
└──────────│──────────────────────────────────────────────────────────────┘
           │
           │  enqueue task                    read/write run state
           ▼                                          │
┌──────────────────────┐              ┌───────────────▼──────────────────┐
│    TASK QUEUE        │              │           DATABASE LAYER          │
│                      │              │                                   │
│  ┌────────────────┐  │              │  ┌────────────────────────────┐  │
│  │     Redis      │  │              │  │       PostgreSQL            │  │
│  │  (job broker)  │  │              │  │                            │  │
│  └────────────────┘  │              │  │  • users                   │  │
│                      │              │  │  • run_history             │  │
│  ┌────────────────┐  │              │  │  • langgraph_checkpoints   │  │
│  │  Redis Pub/Sub │  │              │  │  • embeddings (pgvector)   │  │
│  │ (approval gate)│  │              │  │                            │  │
│  └────────────────┘  │              │  └────────────────────────────┘  │
└──────────┬───────────┘              └──────────────────────────────────┘
           │ dequeue
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         WORKER LAYER (Celery)                            │
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                    _run_graph() Celery Task                      │  │
│   │                                                                  │  │
│   │   ┌────────────────────────────────────────────────────────┐    │  │
│   │   │                  LangGraph Pipeline                    │    │  │
│   │   │                                                        │    │  │
│   │   │   ┌──────────┐   ┌──────────┐   ┌─────────────────┐  │    │  │
│   │   │   │Researcher│──►│ Analyst  │──►│ human_approval  │  │    │  │
│   │   │   │  (RAG)   │   │(GPT-4.1) │   │  interrupt()    │  │    │  │
│   │   │   └──────────┘   └──────────┘   └────────┬────────┘  │    │  │
│   │   │                                           │           │    │  │
│   │   │                          waits on Redis pub/sub       │    │  │
│   │   │                                           │           │    │  │
│   │   │                                  ┌────────▼────────┐  │    │  │
│   │   │                                  │  Report Writer  │  │    │  │
│   │   │                                  │   (GPT-4.1)     │  │    │  │
│   │   │                                  └────────┬────────┘  │    │  │
│   │   │                                           │           │    │  │
│   │   │                                  ┌────────▼────────┐  │    │  │
│   │   │                                  │   Evaluator     │  │    │  │
│   │   │                                  │    (RAGAS)      │  │    │  │
│   │   │                                  └─────────────────┘  │    │  │
│   │   └────────────────────────────────────────────────────────┘    │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│   (Multiple worker instances can run in parallel — each picks one job)  │
└──────────────────────────────────────────────────────────────────────────┘
           │
           │  embedding search + BM25
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          RAG LAYER                                       │
│                                                                          │
│   ┌─────────────────────────┐    ┌─────────────────────────────────┐   │
│   │   pgvector (Postgres)   │    │   BM25 Index (in-memory/Redis)  │   │
│   │   semantic search       │    │   keyword search                │   │
│   │   text-embedding-3-small│    │   rank-bm25                     │   │
│   └─────────────────────────┘    └─────────────────────────────────┘   │
│                    \                          /                          │
│                     \── Reciprocal Rank Fusion ──/                      │
│                              top-5 chunks                               │
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │              Ingestion Pipeline (offline / scheduled)            │  │
│   │   SEC EDGAR API → chunking → embeddings → pgvector upsert       │  │
│   └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
           │
           │  chat completions + embeddings
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL AI LAYER                                │
│                                                                          │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │                        OpenAI API                              │   │
│   │   • text-embedding-3-small  (RAG embeddings)                   │   │
│   │   • gpt-4.1                 (Analyst + Report Writer)          │   │
│   │   • gpt-4                   (RAGAS evaluation judge)           │   │
│   └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   Retry policy: tenacity (3 attempts, exponential backoff)              │
│   Rate limiting: per-user token budget enforced at API layer            │
└──────────────────────────────────────────────────────────────────────────┘
           │
           │  traces + metrics + logs
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      OBSERVABILITY LAYER                                 │
│                                                                          │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│   │  OpenTelemetry   │  │   Prometheus     │  │  JSON Logs       │    │
│   │  (traces)        │  │   (metrics)      │  │  (structured)    │    │
│   │  → Jaeger/Tempo  │  │   → Grafana      │  │  → Loki/Datadog  │    │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘    │
│                                                                          │
│   Key metrics tracked:                                                  │
│   • run_duration_seconds per agent                                      │
│   • token_usage_total per agent                                         │
│   • run_status_total (completed / error / rejected)                     │
│   • retrieval_latency_seconds                                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        CI/CD LAYER                                       │
│                                                                          │
│   GitHub Push → GitHub Actions → pytest → Docker build → push to ECR   │
│                                        → deploy to AWS ECS (Fargate)    │
│                                                                          │
│   Environments:  local → staging → production                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Streamlit Frontend
- Sends all requests with a JWT in the `Authorization` header
- Polls `GET /status/{job_id}` every 2 seconds during active runs
- Displays approval panel when status = `awaiting_approval`
- No business logic — purely a display and input layer

### 3.2 FastAPI (API Layer)
- Multiple instances run behind a load balancer (Nginx or AWS ALB)
- Auth middleware validates JWT on every request before it reaches a route
- `/run` enqueues a Celery task (does not run it inline)
- `/approve` publishes to a Redis pub/sub channel (does not signal a thread)
- `/status` reads from PostgreSQL (pure read, no side effects)
- Stateless — any instance can serve any request

### 3.3 Redis
Two separate uses:
- **Celery broker:** holds the job queue; workers pull from it
- **Pub/Sub approval gate:** replaces `threading.Event`
  - Channel name: `approval:{job_id}`
  - Worker subscribes; `/approve` publishes; worker resumes

### 3.4 Celery Workers
- Separate processes (not inside FastAPI)
- Each worker picks one job at a time from the Redis queue
- Runs the full LangGraph pipeline
- If the worker crashes mid-run, Celery requeues the job (with retry limits)
- Multiple workers = multiple parallel research runs

### 3.5 LangGraph Pipeline
- Unchanged in logic, but backed by a **Postgres checkpointer** instead of MemorySaver
- State is saved to DB after every node — survives worker restarts
- `interrupt()` now waits on Redis pub/sub instead of `threading.Event`
- `thread_id` = `job_id` (same as today)

### 3.6 PostgreSQL
Single database, four concerns:
| Table / Extension | Purpose |
|-------------------|---------|
| `users` | Auth — email, hashed password, created_at |
| `run_history` | All run data — same as today but with `user_id` FK |
| `langgraph_checkpoints` | LangGraph Postgres checkpointer tables (auto-created) |
| `pgvector` extension | Stores document embeddings for RAG |

### 3.7 RAG Layer
- Embeddings stored in pgvector (same Postgres instance)
- BM25 index rebuilt from DB on worker startup (or cached in Redis)
- Ingestion pipeline runs separately (cron job or triggered manually)
  - Pulls filings from SEC EDGAR API
  - Chunks → embeds → upserts into pgvector
  - Deduplicates by document hash

### 3.8 Observability
- Every FastAPI request gets a trace ID (OpenTelemetry)
- That trace ID flows into Celery task and all agent calls
- One trace = one research run, end to end, across processes
- Grafana dashboard shows: active runs, p95 latency, token cost/hour, error rate

### 3.9 CI/CD
- Every PR runs `pytest` via GitHub Actions (unit + integration tests)
- On merge to `main`: build Docker image → push to ECR → deploy to ECS
- Staging environment mirrors production (same stack, smaller instance sizes)
- Secrets live in AWS Secrets Manager — never in `.env` files in production

---

## 4. Request Flow (End to End)

```
1.  User logs in → POST /auth/login → receives JWT token

2.  User submits query → POST /run (JWT in header)
    FastAPI validates JWT → creates job_id → writes to PostgreSQL
    → enqueues Celery task(job_id, query) to Redis queue
    → returns {job_id} immediately

3.  Celery worker picks up the task
    → starts LangGraph pipeline with Postgres checkpointer
    → researcher_node: hybrid RAG (pgvector + BM25) → top-5 chunks
    → analyst_node: GPT-4.1 → structured JSON analysis
    → human_approval_node: interrupt() fires
       → worker subscribes to Redis channel: approval:{job_id}
       → writes status="awaiting_approval" to PostgreSQL
       → worker blocks (waiting on Redis)

4.  Streamlit polls GET /status/{job_id} every 2s
    FastAPI reads PostgreSQL → returns current state
    UI sees status="awaiting_approval" → shows analyst JSON + buttons

5.  User clicks Approve → POST /approve/{job_id} (JWT in header)
    FastAPI validates ownership (user_id matches)
    → stores payload in Redis key: approval_payload:{job_id}
    → publishes to Redis channel: approval:{job_id}

6.  Worker receives Redis message → resumes LangGraph
    → report_writer_node: GPT-4.1 → ~300-word report + citations
    → evaluator_node: RAGAS → faithfulness + context_recall
    → writes status="completed" + full results to PostgreSQL

7.  Streamlit polls → sees status="completed" → renders report

Total time: ~30-90s (same as today, but now survives crashes and scales)
```

---

## 5. What Changes vs. Today

| Concern | Current (local) | Production |
|---------|----------------|------------|
| Database | SQLite (file) | PostgreSQL (server) |
| LangGraph state | MemorySaver (RAM) | Postgres checkpointer |
| Background work | FastAPI BackgroundTasks | Celery workers |
| Approval signal | threading.Event (in-process) | Redis pub/sub (cross-process) |
| Auth | None | JWT middleware |
| Embeddings | FAISS file | pgvector in Postgres |
| LLM errors | Crash the run | tenacity retry + dead letter |
| Observability | stdout logs | OTel traces + Prometheus + JSON logs |
| Tests | None | pytest + GitHub Actions |
| Deployment | `python main.py` | Docker + AWS ECS |

---

## 6. Implementation Order (Why This Sequence)

```
Phase 1: PostgreSQL first — everything else depends on a real DB
Phase 2: Auth second — needed before any multi-user feature makes sense
Phase 3: Celery — replaces BackgroundTasks, needs Redis
Phase 4: Redis pub/sub — replaces threading.Event, needs Redis (already there)
Phase 5: LLM retries — independent, can slot in anytime after Phase 1
Phase 6: Observability — easier to add once core is stable
Phase 7: RAG at scale — builds on pgvector (already in Phase 1)
Phase 8: Tests — write alongside each phase, formalize CI here
Phase 9: Deploy — packages everything built in Phases 1-8
```

Each phase is a working system. At no point is the app broken mid-migration.
```
