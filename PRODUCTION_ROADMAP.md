# Production Upgrade Roadmap

This document tracks the step-by-step plan to evolve this project from a
local demo into a production-grade system. Each phase builds on the previous
one — complete them in order.

---

## How to Use This File

- Each phase has a **Why** (the problem it solves) and **What You'll Learn**
- Steps within a phase are ordered — do them top to bottom
- Check off items as you complete them: `[ ]` → `[x]`
- Understanding > speed — read the "Why" before writing any code

---

## Phase 1 — Harden the Database

**Why:** SQLite is single-writer and file-based. Under concurrent requests it
locks up. It also disappears if the container restarts. PostgreSQL is what
every serious backend uses.

**What you'll learn:** PostgreSQL basics, SQLAlchemy ORM, Alembic migrations,
connection pooling, environment-based config.

### Steps
- [ ] Install PostgreSQL locally (or spin up via Docker)
- [ ] Replace `sqlite3` calls in `database/db.py` with SQLAlchemy Core
- [ ] Write an Alembic migration for the `run_history` table
- [ ] Replace `MemorySaver` (in-memory) with LangGraph's Postgres checkpointer
- [ ] Test pause/resume still works with Postgres-backed state
- [ ] Update `.env.example` with `DATABASE_URL`

---

## Phase 2 — Authentication & Multi-Tenancy

**Why:** Right now anyone who knows a `job_id` can approve or read any run.
There is no concept of users. Real APIs gate every endpoint behind identity.

**What you'll learn:** JWT tokens, OAuth2 flow, FastAPI dependency injection,
middleware, password hashing, user-scoped queries.

### Steps
- [ ] Add a `users` table (id, email, hashed_password, created_at)
- [ ] Add `user_id` foreign key to `run_history`
- [ ] Implement `POST /auth/register` and `POST /auth/login` (returns JWT)
- [ ] Add FastAPI `Depends(get_current_user)` guard on all existing endpoints
- [ ] Enforce that a user can only read/approve their own jobs
- [ ] Update Streamlit frontend to store token and send in headers

---

## Phase 3 — Replace BackgroundTasks with a Task Queue

**Why:** `BackgroundTasks` runs inside the FastAPI process. If the server
restarts mid-run, the job silently disappears. A task queue (Celery + Redis)
runs workers in a separate process and retries failed jobs automatically.

**What you'll learn:** Celery, Redis, worker processes, task retries,
distributed systems basics.

### Steps
- [ ] Run Redis locally (Docker: `docker run -p 6379:6379 redis`)
- [ ] Install Celery and configure it to use Redis as the broker
- [ ] Move `_run_graph()` into a Celery task
- [ ] Update `POST /run` to enqueue the Celery task instead of `BackgroundTasks`
- [ ] Verify job survives a FastAPI server restart mid-run
- [ ] Add retry logic (max 3 retries, exponential backoff) on Celery task

---

## Phase 4 — Fix the Approval Signal (Redis Pub/Sub)

**Why:** The current `threading.Event` only works on a single server process.
If two FastAPI instances run behind a load balancer, `/approve` might hit a
different server than the one holding the event in memory. Redis pub/sub
replaces the in-process signal with a network-accessible one.

**What you'll learn:** Redis pub/sub, distributed signaling, race conditions,
horizontal scaling concepts.

### Steps
- [ ] Replace `_approval_events` dict with Redis pub/sub channels
- [ ] Replace `_approval_payloads` dict with Redis key-value storage (with TTL)
- [ ] Update `_wait_for_approval()` to subscribe to `approval:{job_id}` channel
- [ ] Update `POST /approve` to publish to that channel
- [ ] Test that approve works even if called from a different process
- [ ] Set a TTL on approval keys so stale data cleans itself up

---

## Phase 5 — Error Handling & Retries on LLM Calls

**Why:** GPT-4.1 returns rate limit errors (429) and occasional 500s. Right
now one bad response kills the whole run. Production systems retry transient
failures automatically and surface permanent ones clearly.

**What you'll learn:** Exponential backoff, tenacity library, error
classification (transient vs permanent), dead letter queues.

### Steps
- [ ] Wrap every OpenAI call with `tenacity` retry decorator
  - Retry on 429 and 500 with exponential backoff (max 3 attempts)
  - Do not retry on 400 (bad request) — that's a code bug, not transient
- [ ] Add a `failed_reason` field to `run_history` (timeout / rate_limit / etc.)
- [ ] Create a "dead letter" state — runs that exhausted all retries land here
- [ ] Surface retry count and failure reason in the Streamlit UI

---

## Phase 6 — Observability (Logs, Traces, Metrics)

**Why:** stdout logs tell you what happened on one machine. In production you
need to search across all machines, trace a single request end-to-end, and
get alerted when things go wrong — without reading logs manually.

**What you'll learn:** OpenTelemetry, structured logging (JSON), distributed
tracing, metrics (counters, histograms), Grafana + Prometheus basics.

### Steps
- [ ] Switch all `logging` calls to structured JSON (use `python-json-logger`)
- [ ] Add OpenTelemetry SDK — instrument FastAPI and each agent node
- [ ] Export traces to Jaeger (local Docker) — visualize one run end-to-end
- [ ] Add Prometheus metrics:
  - `run_duration_seconds` histogram per agent
  - `run_total` counter by status (completed / error / rejected)
  - `token_usage_total` counter per agent
- [ ] Run Prometheus + Grafana locally and build a dashboard

---

## Phase 7 — RAG at Scale

**Why:** 15 hardcoded excerpts in a Python file is a demo. Real systems
ingest thousands of documents, update the index as new filings arrive,
and store vectors in a managed database — not a local FAISS file.

**What you'll learn:** Managed vector databases (pgvector or Pinecone),
document ingestion pipelines, incremental indexing, retrieval evaluation.

### Steps
- [ ] Replace local FAISS with pgvector (Postgres extension) or Pinecone
- [ ] Build an ingestion script that reads real SEC filings from EDGAR API
- [ ] Add deduplication — don't re-embed a chunk that's already indexed
- [ ] Add metadata filtering to retrieval (filter by company, year, section)
- [ ] Build a retrieval evaluation dataset (10 questions + expected chunks)
- [ ] Measure retrieval precision@5 before and after each RAG change

---

## Phase 8 — Tests & CI/CD

**Why:** Without tests, every change is a gamble. Without CI, "works on my
machine" is all you have. Real teams ship with confidence because the pipeline
catches regressions automatically.

**What you'll learn:** pytest, mocking external APIs, GitHub Actions, Docker,
integration vs unit tests.

### Steps
- [ ] Write unit tests for each agent (mock OpenAI calls with `pytest-mock`)
- [ ] Write an integration test for the full pipeline (researcher → evaluator)
- [ ] Write API tests for all 4 endpoints using `httpx.AsyncClient`
- [ ] Set up GitHub Actions workflow:
  - Triggers on every PR
  - Runs `pytest` and fails the PR if any test fails
- [ ] Write a `Dockerfile` for the FastAPI backend
- [ ] Write a `docker-compose.yml` that starts FastAPI + Postgres + Redis together

---

## Phase 9 — Deployment

**Why:** The final step — making the system accessible beyond your laptop.

**What you'll learn:** Cloud basics (AWS or GCP), container orchestration,
environment management, secrets management, domain + SSL.

### Steps
- [ ] Push Docker image to a container registry (ECR or Docker Hub)
- [ ] Deploy FastAPI on AWS ECS (Fargate) or Render.com
- [ ] Deploy Streamlit on Streamlit Cloud or as a second ECS service
- [ ] Use AWS Secrets Manager (or similar) instead of `.env` files
- [ ] Set up a domain + SSL certificate
- [ ] Configure health checks and auto-restart on crash

---

## Progress Tracker

| Phase | Topic | Status |
|-------|-------|--------|
| 1 | Harden the Database | Not started |
| 2 | Auth & Multi-Tenancy | Not started |
| 3 | Task Queue (Celery) | Not started |
| 4 | Redis Approval Signal | Not started |
| 5 | LLM Error Handling | Not started |
| 6 | Observability | Not started |
| 7 | RAG at Scale | Not started |
| 8 | Tests & CI/CD | Not started |
| 9 | Deployment | Not started |

---

## Ground Rules

1. **Understand before implementing.** Each phase starts with reading and
   discussion — don't write code until the concept is clear.
2. **One phase at a time.** Don't jump to Phase 3 while Phase 1 is incomplete.
3. **Keep the app working.** Every phase should end with a running system,
   not a half-migrated one.
4. **Commit after every phase.** Each phase = one clean git commit.
