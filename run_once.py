# =============================================================================
# run_once.py — One scrape + score cycle (runs every 3 hours via GitHub Actions)
#
# Flow:
#   1. Scrape all sources
#   2. Title pre-filter (local, no API)
#   3. Freshness filter (24-hour window)
#   4. Score with Gemini
#   5. Send digest of THIS run's top 20 matches
#   6. Log all matches to Google Sheets
#
# No-repeat guarantee: seen_jobs DB marks every job after scoring.
# A job never appears in two digests because it is never re-scored.
# =============================================================================

import re
import time
from datetime import datetime

from config import MATCH_THRESHOLD, REJECT_SENIORITY_KEYWORDS
from database import init_db, is_seen, mark_seen, get_seen_count
from scraper import scrape_all_sources
from org_scraper import scrape_all_orgs
from scorer import evaluate_job
from logger import log_to_sheets, send_digest_email
from daily_log import log_scraped_job, batch_log_unscored, send_unscored_digest

# ─────────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────────

MAX_SCORE_PER_RUN = 80    # Gemini free tier: 1500/day, 8 runs/day = safe
MAX_AGE_DAYS      = 1      # Only score jobs posted in the last 24 hours
DIGEST_TOP_N      = 20    # Top N matches to include in the digest email

# ─────────────────────────────────────────────────────────────
# TITLE FILTERS
# ─────────────────────────────────────────────────────────────

RELEVANT_TITLE_KEYWORDS = [
    "program manager", "project manager", "operations manager",
    "program coordinator", "project coordinator",
    "operations coordinator", "operations analyst",
    "associate program", "associate project",
    "senior program coordinator", "senior project coordinator",
    "program specialist", "project specialist",
    "operations specialist", "program administrator",
    "project administrator", "program associate",
    "project associate", "operations associate",
    "program lead", "project lead", "operations lead",
    "program officer", "project officer",
    "program analyst", "project analyst",
    "grants manager", "grants coordinator",
    "research coordinator", "research program",
    "clinical program", "clinical coordinator",
    "success manager", "engagement manager",
    "implementation manager", "delivery manager",
    "portfolio manager", "initiative manager",
]

TITLE_BLOCKLIST = [
    "professor", "lecturer", "adjunct", "faculty",
    "teaching assistant", "postdoc", "researcher",
    "attorney", "counsel", "paralegal",
    "nurse", "physician", "therapist", "clinician",
    "engineer", "developer", "architect", "scientist",
    "accountant", "auditor", "actuary",
    "store manager", "retail", "restaurant",
]


def title_is_relevant(title: str) -> bool:
    title_lower = title.lower()
    padded = " " + title_lower + " "
    if any(bl in title_lower for bl in TITLE_BLOCKLIST):
        return False
    for word in REJECT_SENIORITY_KEYWORDS:
        if " " + word + " " in padded:
            return False
    return any(kw in title_lower for kw in RELEVANT_TITLE_KEYWORDS)


def is_recent_posting(job: dict, max_age_days: int = MAX_AGE_DAYS) -> bool:
    """
    True if posted within max_age_days.
    Org jobs (cap_exempt=True): strict — excludes if date missing or unparseable.
    General board jobs: lenient — pre-filtered to 24h at the source.
    """
    if max_age_days <= 0:
        return True

    is_org = bool(job.get("cap_exempt"))
    posted  = (job.get("posted_date") or "").strip()

    # Empty date
    if not posted:
        return False if is_org else True

    p = posted.lower()

    # "Just now" / "today" / "X hours ago" / "X minutes ago"
    if any(x in p for x in ["just now", "just posted", "today", "hours ago", "minutes ago", "new"]):
        return True

    # "yesterday" / "1 day ago"
    if "yesterday" in p or "1 day ago" in p:
        return max_age_days >= 1

    # "N days ago" — explicit number e.g. "2 days ago"
    m = re.search(r"(\d+)\s*days?\s*ago", p)
    if m:
        return int(m.group(1)) <= max_age_days

    # "30+" or "30+ days" — Workday's way of saying ≥30 days old
    m = re.search(r"(\d+)\+", p)
    if m:
        return False   # Always older than any sensible window

    # "N weeks ago" / "N months ago"
    if re.search(r"\d+\s*weeks?\s*ago", p) or re.search(r"\d+\s*months?\s*ago", p):
        return False

    # Absolute date parsing
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S+00:00",
                "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S", "%d %b %Y"]:
        try:
            return (datetime.now() - datetime.strptime(posted[:30].strip(), fmt)).days <= max_age_days
        except (ValueError, TypeError):
            continue

    # Try YYYY-MM-DD from first 10 chars
    try:
        return (datetime.now() - datetime.strptime(posted[:10], "%Y-%m-%d")).days <= max_age_days
    except (ValueError, TypeError):
        pass

    # Unparseable date — be strict for org jobs, lenient for general boards
    return False if is_org else True
