# =============================================================================
# database.py — Keeps track of jobs already seen so we never process
# the same posting twice, even across bot restarts.
# Uses SQLite, which is a simple file-based database built into Python.
# =============================================================================

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "seen_jobs.db")


def init_db():
    """Create the database and table if they don't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_id      TEXT PRIMARY KEY,
            title       TEXT,
            company     TEXT,
            url         TEXT,
            seen_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def is_seen(job_id: str) -> bool:
    """Return True if we've already processed this job."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mark_seen(job_id: str, title: str, company: str, url: str):
    """Record a job so we skip it next time."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO seen_jobs (job_id, title, company, url) VALUES (?, ?, ?, ?)",
        (job_id, title, company, url)
    )
    conn.commit()
    conn.close()


def get_seen_count() -> int:
    """How many jobs have we processed total (for logging)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM seen_jobs")
    count = cursor.fetchone()[0]
    conn.close()
    return count
