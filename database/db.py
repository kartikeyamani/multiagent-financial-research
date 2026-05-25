"""
database/db.py
--------------
SQLite database layer for persisting agent run history.
Records every run's query, status, retrieved chunks, analysis, report, and RAGAS scores.
"""

import sqlite3
import json
import time
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "./runs.db")


def _get_connection() -> sqlite3.Connection:
    """Create and return a SQLite connection with WAL mode for concurrent access."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    """Context manager that yields a connection and commits/rolls back automatically."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the run_history table if it doesn't already exist."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id        TEXT    UNIQUE NOT NULL,
                query         TEXT    NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'pending',
                current_agent TEXT,
                retrieved_chunks TEXT,   -- JSON
                analysis      TEXT,      -- JSON
                approval_decision TEXT,
                report        TEXT,
                evaluation_scores TEXT,  -- JSON
                token_counts  TEXT,      -- JSON
                latencies     TEXT,      -- JSON
                error         TEXT,
                created_at    REAL    NOT NULL,
                updated_at    REAL    NOT NULL
            )
            """
        )
    logger.info(f"[DB] Initialized database at {DB_PATH}")


def create_run(job_id: str, query: str) -> None:
    """Insert a new run record when a job is first submitted."""
    now = time.time()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO run_history (job_id, query, status, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (job_id, query, now, now),
        )
    logger.info(f"[DB] Created run record: job_id={job_id}")


def update_run(job_id: str, **fields) -> None:
    """
    Update arbitrary fields on an existing run record.
    JSON-serializable objects (dict, list) are automatically serialised.
    """
    if not fields:
        return

    serialised = {}
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            serialised[k] = json.dumps(v)
        else:
            serialised[k] = v

    serialised["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in serialised)
    values = list(serialised.values()) + [job_id]

    with get_db() as conn:
        conn.execute(
            f"UPDATE run_history SET {set_clause} WHERE job_id = ?", values
        )
    logger.debug(f"[DB] Updated job_id={job_id} fields={list(fields.keys())}")


def get_run(job_id: str) -> dict | None:
    """Fetch a single run record and deserialize JSON fields."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM run_history WHERE job_id = ?", (job_id,)
        ).fetchone()

    if row is None:
        return None

    record = dict(row)
    for key in ("retrieved_chunks", "analysis", "evaluation_scores", "token_counts", "latencies"):
        if record.get(key):
            try:
                record[key] = json.loads(record[key])
            except json.JSONDecodeError:
                pass  # leave as string if not valid JSON
    return record


def list_runs(limit: int = 50) -> list[dict]:
    """Return the most recent `limit` run records ordered by creation time."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT job_id, query, status, current_agent, created_at, updated_at "
            "FROM run_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
