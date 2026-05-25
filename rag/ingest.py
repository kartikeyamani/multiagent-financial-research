"""
rag/ingest.py
-------------
One-time ingestion of sample SEC filing data into the FAISS index.
Call `ingest_sample_data()` on first run or to rebuild the index.
"""

import logging
from rag.pipeline import chunk_documents, build_retriever
from data.sample_filings import SAMPLE_FILINGS

logger = logging.getLogger(__name__)


def ingest_sample_data():
    """
    Load sample filings, chunk them, build the FAISS index and BM25 retriever.
    """
    logger.info(f"[Ingest] Processing {len(SAMPLE_FILINGS)} sample SEC filing sections …")
    documents = chunk_documents(SAMPLE_FILINGS)
    build_retriever(documents)
    logger.info("[Ingest] Ingestion complete – FAISS index ready")


if __name__ == "__main__":
    # Run standalone:  python -m rag.ingest
    import os
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ingest_sample_data()
    print("✅ Ingest complete")
