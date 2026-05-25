"""
rag/pipeline.py
---------------
RAG pipeline: FAISS vector store + BM25 hybrid retrieval.
- Embeddings: OpenAI text-embedding-3-small
- Chunk size: 512 tokens with 20% overlap (~102 tokens)
- Retrieval: top-5 chunks via hybrid (BM25 + semantic) Reciprocal Rank Fusion
  NOTE: EnsembleRetriever was removed from LangChain 0.3+, so we implement
        RRF (Reciprocal Rank Fusion) directly — no extra dependency needed.
"""

import os
import json
import time
import logging
from typing import Any, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever

# Document moved to langchain_core in LangChain 0.3+
try:
    from langchain_core.documents import Document
except ImportError:
    from langchain.schema import Document  # type: ignore

# TokenTextSplitter lives in the standalone langchain-text-splitters package
try:
    from langchain_text_splitters import TokenTextSplitter
except ImportError:
    from langchain.text_splitter import TokenTextSplitter  # type: ignore

logger = logging.getLogger(__name__)

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./faiss_index")
DOCS_CACHE_PATH  = FAISS_INDEX_PATH + "_docs.json"   # persisted document cache for BM25
TOP_K = 5
CHUNK_SIZE = 512      # tokens
CHUNK_OVERLAP = 102   # ≈ 20% of 512

# Hybrid weights for Reciprocal Rank Fusion
FAISS_WEIGHT = 0.6
BM25_WEIGHT  = 0.4

# ── Module-level singletons (loaded once per process) ─────────────────────────
_embeddings: Optional[OpenAIEmbeddings] = None
_faiss_store: Optional[FAISS] = None
_bm25_retriever: Optional[BM25Retriever] = None
_retriever_ready: bool = False
_all_documents: list[Document] = []   # kept in memory for BM25


def _get_embeddings() -> OpenAIEmbeddings:
    """Lazily instantiate the OpenAI embeddings model."""
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        logger.info("[RAG] Embeddings model loaded: text-embedding-3-small")
    return _embeddings


# ── Reciprocal Rank Fusion ─────────────────────────────────────────────────────
def _rrf_fuse(
    faiss_docs: list[Document],
    bm25_docs: list[Document],
    k: int = TOP_K,
) -> list[Document]:
    """
    Combine two ranked lists via Reciprocal Rank Fusion.
    score(doc) = FAISS_WEIGHT / (rank_faiss + 60) + BM25_WEIGHT / (rank_bm25 + 60)
    The constant 60 dampens the effect of high ranks (standard RRF constant).
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for rank, doc in enumerate(faiss_docs, start=1):
        key = doc.page_content[:120]
        scores[key] = scores.get(key, 0.0) + FAISS_WEIGHT / (rank + 60)
        doc_map[key] = doc

    for rank, doc in enumerate(bm25_docs, start=1):
        key = doc.page_content[:120]
        scores[key] = scores.get(key, 0.0) + BM25_WEIGHT / (rank + 60)
        doc_map.setdefault(key, doc)

    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [doc_map[key] for key in sorted_keys[:k]]


# ── Build / Load ───────────────────────────────────────────────────────────────
def build_retriever(documents: list[Document]) -> bool:
    """
    Build FAISS index + BM25 retriever from a list of Documents.
    Returns True on success.
    """
    global _faiss_store, _bm25_retriever, _retriever_ready, _all_documents

    embeddings = _get_embeddings()

    logger.info(f"[RAG] Building FAISS index over {len(documents)} chunks …")
    t0 = time.time()
    _faiss_store = FAISS.from_documents(documents, embeddings)
    _faiss_store.save_local(FAISS_INDEX_PATH)
    logger.info(f"[RAG] FAISS index built in {time.time() - t0:.1f}s → {FAISS_INDEX_PATH}")

    _bm25_retriever = BM25Retriever.from_documents(documents, k=TOP_K * 2)
    _all_documents = documents
    _retriever_ready = True

    # ── Persist docs so BM25 can be rebuilt after a restart ───────────────────
    try:
        serialised = [
            {"page_content": d.page_content, "metadata": d.metadata}
            for d in documents
        ]
        with open(DOCS_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(serialised, f)
        logger.info(f"[RAG] Document cache saved → {DOCS_CACHE_PATH}")
    except Exception as e:
        logger.warning(f"[RAG] Could not save document cache: {e}")

    logger.info("[RAG] Hybrid retriever ready (60% FAISS / 40% BM25 via RRF)")
    return True


def load_retriever() -> bool:
    """
    Load FAISS index from disk (BM25 is rebuilt from _all_documents in memory).
    Triggers ingest if the index doesn't exist yet.
    Returns True once ready.
    """
    global _faiss_store, _bm25_retriever, _retriever_ready

    if _retriever_ready:
        return True

    embeddings = _get_embeddings()

    if os.path.exists(FAISS_INDEX_PATH):
        logger.info(f"[RAG] Loading FAISS index from {FAISS_INDEX_PATH} …")
        _faiss_store = FAISS.load_local(
            FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True
        )
        # ── Try to reload docs from disk cache for BM25 ──────────────────────
        if not _all_documents and os.path.exists(DOCS_CACHE_PATH):
            try:
                with open(DOCS_CACHE_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                _all_documents.extend(
                    [Document(page_content=d["page_content"], metadata=d["metadata"]) for d in raw]
                )
                logger.info(f"[RAG] Loaded {len(_all_documents)} docs from cache → BM25 rebuilding …")
            except Exception as e:
                logger.warning(f"[RAG] Could not load doc cache: {e}")

        if _all_documents:
            _bm25_retriever = BM25Retriever.from_documents(_all_documents, k=TOP_K * 2)
            logger.info("[RAG] BM25 retriever rebuilt ✅")
        else:
            logger.warning("[RAG] No docs available for BM25 — FAISS-only mode")

        _retriever_ready = True
        logger.info("[RAG] Retriever loaded from disk ✅")
        return True
    else:
        logger.warning("[RAG] No FAISS index found — triggering sample data ingest …")
        from rag.ingest import ingest_sample_data
        ingest_sample_data()
        return True


# ── Public retrieval API ───────────────────────────────────────────────────────
def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    """
    Run hybrid BM25 + FAISS retrieval and return top-k chunks with metadata.

    Returns
    -------
    list of dicts with keys:
        text, company, ticker, filing, section, score_rank
    """
    load_retriever()

    t0 = time.time()

    # ── FAISS semantic search ──────────────────────────────────────────────────
    faiss_docs: list[Document] = []
    if _faiss_store is not None:
        faiss_retriever = _faiss_store.as_retriever(search_kwargs={"k": k * 2})
        faiss_docs = faiss_retriever.invoke(query)

    # ── BM25 lexical search ────────────────────────────────────────────────────
    bm25_docs: list[Document] = []
    if _bm25_retriever is not None:
        bm25_docs = _bm25_retriever.invoke(query)

    # ── Fuse results ───────────────────────────────────────────────────────────
    if faiss_docs and bm25_docs:
        fused = _rrf_fuse(faiss_docs, bm25_docs, k=k)
        mode = "hybrid RRF"
    elif faiss_docs:
        fused = faiss_docs[:k]
        mode = "FAISS-only"
    else:
        fused = bm25_docs[:k]
        mode = "BM25-only"

    latency = time.time() - t0

    # ── Convert to output dicts ────────────────────────────────────────────────
    chunks: list[dict] = []
    for rank, doc in enumerate(fused, start=1):
        chunks.append(
            {
                "text": doc.page_content,
                "company": doc.metadata.get("company", "Unknown"),
                "ticker": doc.metadata.get("ticker", "N/A"),
                "filing": doc.metadata.get("filing", "N/A"),
                "section": doc.metadata.get("section", "N/A"),
                "score_rank": rank,
            }
        )

    logger.info(
        f"[RAG] {mode} → {len(chunks)} chunks in {latency:.2f}s | "
        f"query='{query[:60]}'"
    )
    for i, c in enumerate(chunks, 1):
        logger.info(f"[RAG]   [{i}] {c['company']} | {c['filing']} | {c['section']}")

    return chunks


def chunk_documents(raw_docs: list[dict]) -> list[Document]:
    """
    Split raw filing dicts into overlapping 512-token chunks.
    Preserves company/ticker/filing/section metadata on each chunk.
    """
    splitter = TokenTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    documents: list[Document] = []

    for doc in raw_docs:
        chunks = splitter.split_text(doc["text"])
        for chunk in chunks:
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "company": doc["company"],
                        "ticker": doc["ticker"],
                        "filing": doc["filing"],
                        "section": doc["section"],
                    },
                )
            )

    logger.info(f"[RAG] Split {len(raw_docs)} documents → {len(documents)} chunks")
    return documents
