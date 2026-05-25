"""
main.py
-------
FastAPI application entry-point.
Run with:  uvicorn main:app --reload --port 8000
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()                   # load .env before any other imports

# ── Logging configuration ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── FastAPI setup ─────────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from database.db import init_db

app = FastAPI(
    title="Multi-Agent Financial Research Assistant",
    description=(
        "3-agent LangGraph pipeline (Researcher → Analyst → Report Writer) "
        "backed by RAG over SEC 10-K filings with human-in-the-loop approval."
    ),
    version="1.0.0",
)

# Allow Streamlit (running on a different port) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="")


@app.on_event("startup")
async def startup_event():
    """Run startup tasks: init DB, warm up the RAG index."""
    logger.info("=" * 60)
    logger.info("  Multi-Agent Financial Research Assistant — starting up")
    logger.info("=" * 60)

    # ── Initialize database ────────────────────────────────────────────────────
    init_db()

    # ── Warm-up: ingest sample filings if index doesn't exist ─────────────────
    faiss_path = os.getenv("FAISS_INDEX_PATH", "./faiss_index")
    if not os.path.exists(faiss_path):
        logger.info("[Startup] No FAISS index found — ingesting sample filings …")
        from rag.ingest import ingest_sample_data
        ingest_sample_data()
    else:
        logger.info(f"[Startup] FAISS index found at {faiss_path} — loading …")
        from rag.pipeline import load_retriever
        load_retriever()

    logger.info("[Startup] Ready ✅")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "financial-research-assistant"}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
