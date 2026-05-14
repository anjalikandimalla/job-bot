# =============================================================================
# database.py — SQLite deduplication + digest queue
# =============================================================================

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "seen_jobs.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as c:
        # Seen jobs — dedup across all runs
        c.execute("""
            CREATE TABLE IF NOT EXISTS seen_jobs (
                id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                url TEXT,
                seen_at TEXT
            )
        """)
        # Digest queue — matches waiting to be sent in the next 3-hour digest
        c.execute("""
            CREATE TABLE IF NOT EXISTS digest_queue (
                id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                url TEXT,
                source TEXT,
                score INTEGER,
                employment_type TEXT,
                h1b_status TEXT,
                is_cap_exempt INTEGER,
                is_verified_h1b INTEGER,
                is_short_contract INTEGER,
                role_fit INTEGER,
                skill_match INTEGER,
                experience_fit INTEGER,
                environment_fit INTEGER,
                top_matching_skills TEXT,
                missing_skills TEXT,
                summary TEXT,
                posted_date TEXT,
                h1b_verify_url TEXT,
                cap_exempt_bonus INTEGER,
                queued_at TEXT
            )
        """)
        # Digest send log — tracks when last digest was sent
        c.execute("""
            CREATE TABLE IF NOT EXISTS digest_log (
                id INTEGER PRIMARY KEY,
                sent_at TEXT
            )
        """)


def is_seen(job_id: str) -> bool:
    with _conn() as c:
        row = c.execute("SELECT 1 FROM seen_jobs WHERE id=?", (job_id,)).fetchone()
        return row is not None


def mark_seen(job_id: str, title: str = "", company: str = "", url: str = ""):
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO seen_jobs (id, title, company, url, seen_at) VALUES (?,?,?,?,?)",
            (job_id, title, company, url, datetime.now().isoformat())
        )


def get_seen_count() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]


def queue_match_for_digest(result: dict):
    """Add a scored match to the digest queue."""
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO digest_queue (
                id, title, company, location, url, source, score,
                employment_type, h1b_status, is_cap_exempt, is_verified_h1b,
                is_short_contract, role_fit, skill_match, experience_fit,
                environment_fit, top_matching_skills, missing_skills, summary,
                posted_date, h1b_verify_url, cap_exempt_bonus, queued_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            result["id"], result["title"], result["company"], result["location"],
            result["url"], result["source"], result["match_score"],
            result["employment_type"], result["h1b_status"],
            int(result["is_cap_exempt"]), int(result["is_verified_h1b"]),
            int(result["is_short_contract"]),
            result["role_fit"], result["skill_match"], result["experience_fit"],
            result["environment_fit"], result["top_matching_skills"],
            result["missing_skills"], result["summary"],
            result["posted_date"], result["h1b_verify_url"],
            result.get("cap_exempt_bonus", 0),
            datetime.now().isoformat()
        ))


def get_digest_queue() -> list[dict]:
    """Return all pending matches sorted by score descending."""
    with _conn() as c:
        rows = c.execute("""
            SELECT id, title, company, location, url, source, score,
                   employment_type, h1b_status, is_cap_exempt, is_verified_h1b,
                   is_short_contract, role_fit, skill_match, experience_fit,
                   environment_fit, top_matching_skills, missing_skills, summary,
                   posted_date, h1b_verify_url, cap_exempt_bonus, queued_at
            FROM digest_queue
            ORDER BY score DESC
        """).fetchall()
        return [dict(zip([
            "id","title","company","location","url","source","match_score",
            "employment_type","h1b_status","is_cap_exempt","is_verified_h1b",
            "is_short_contract","role_fit","skill_match","experience_fit",
            "environment_fit","top_matching_skills","missing_skills","summary",
            "posted_date","h1b_verify_url","cap_exempt_bonus","queued_at"
        ], row)) for row in rows]


def clear_digest_queue():
    """Clear the queue after sending a digest."""
    with _conn() as c:
        c.execute("DELETE FROM digest_queue")


def hours_since_last_digest() -> float:
    """Return hours since the last digest was sent. Returns 999 if never sent."""
    with _conn() as c:
        row = c.execute(
            "SELECT sent_at FROM digest_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return 999.0
        last = datetime.fromisoformat(row[0])
        return (datetime.now() - last).total_seconds() / 3600


def record_digest_sent():
    """Record that a digest was just sent."""
    with _conn() as c:
        c.execute(
            "INSERT INTO digest_log (sent_at) VALUES (?)",
            (datetime.now().isoformat(),)
        )
