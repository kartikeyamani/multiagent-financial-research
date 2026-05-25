"""
agents/researcher.py
--------------------
Researcher Agent
Accepts a financial query, performs hybrid BM25 + semantic retrieval
over the SEC filings vector store, and returns the top-5 chunks
along with their source metadata.
"""

import logging
import time

import tiktoken

from rag.pipeline import retrieve

logger = logging.getLogger(__name__)

# Token counter for the embedding query (informational only)
_enc = tiktoken.get_encoding("cl100k_base")


class ResearcherAgent:
    """Retrieves the most relevant SEC filing chunks for a given query."""

    def run(self, query: str, top_k: int = 5) -> dict:
        """
        Parameters
        ----------
        query  : The natural-language financial research question.
        top_k  : Number of chunks to return (default 5).

        Returns
        -------
        dict with keys:
            chunks      : list of chunk dicts (text, company, ticker, filing, section, score_rank)
            token_count : approximate tokens in the query
            latency_s   : wall-clock retrieval time
        """
        logger.info(f"[Researcher] Query received: '{query}'")
        t0 = time.time()

        # ── Hybrid retrieval ────────────────────────────────────────────────────
        chunks = retrieve(query, k=top_k)

        latency = time.time() - t0
        token_count = len(_enc.encode(query))

        logger.info(
            f"[Researcher] Retrieved {len(chunks)} chunks in {latency:.2f}s "
            f"| query_tokens={token_count}"
        )

        # ── Log sources to console ──────────────────────────────────────────────
        for i, chunk in enumerate(chunks, 1):
            logger.info(
                f"[Researcher]   Chunk {i}: {chunk['company']} | "
                f"{chunk['filing']} | {chunk['section']}"
            )

        return {
            "chunks": chunks,
            "token_count": token_count,
            "latency_s": latency,
        }
