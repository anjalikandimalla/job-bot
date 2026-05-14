# =============================================================================
# run_once.py — One full scrape + score cycle (used by GitHub Actions)
#
# Flow:
#   1. Scrape all sources
#   2. Title pre-filter (fast, local — no API)
#   3. Log ALL relevant jobs to Daily Scrape Log sheet (separate workbook)
#   4. Score with Gemini — if quota hits, stop scoring early
#   5. Log 80%+ matches to main Job Bot Log + email alerts
#   6. If quota exhausted: email unscored digest + they're already in Daily Log
# =============================================================================

import time
from datetime import datetime

from config import MATCH_THRESHOLD, SEND_INSTANT_EMAIL, SEND_DAILY_DIGEST, REJECT_SENIORITY_KEYWORDS
from database import init_db, is_seen, mark_seen, get_seen_count
from scraper import scrape_all_sources
from org_scraper import scrape_all_orgs
from scorer import evaluate_job
from logger import log_to_sheets, send_match_email, send_daily_digest
from daily_log import log_scraped_job, batch_log_unscored, send_unscored_digest

MAX_SCORE_PER_RUN = 80

# Only consider jobs posted within the last N days
# Set to 0 to disable freshness filtering (e.g. for debugging)
MAX_AGE_DAYS = 15

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

# Titles containing these words are never relevant regardless of other keywords
TITLE_BLOCKLIST = [
    "professor", "lecturer", "adjunct", "faculty",
    "teaching assistant", "postdoc", "researcher",
    "attorney", "counsel", "paralegal",
    "nurse", "physician", "therapist", "clinician",
    "engineer", "developer", "architect", "scientist",
    "accountant", "auditor", "actuary",
    "store manager", "retail", "restaurant",
]

def is_recent_posting(job: dict, max_age_days: int = MAX_AGE_DAYS) -> bool:
    """
    Return True if the job was posted within the last N days.
    Tries multiple date formats: YYYY-MM-DD, ISO 8601, RFC 2822, relative phrases.
    If date is empty/unparseable, treat as fresh (don't filter out).
    """
    if max_age_days <= 0:
        return True

    posted = (job.get("posted_date") or "").strip()
    if not posted:
        return True  # No date — assume fresh

    # Relative phrases like "Posted Today", "3 days ago", "Just posted"
    p_lower = posted.lower()
    if any(p in p_lower for p in ["today", "hours ago", "just posted", "minutes ago", "new"]):
        return True
    if "yesterday" in p_lower or "1 day ago" in p_lower:
        return True
    # "2 days ago", "3 days ago", etc
    import re
    m = re.search(r"(\d+)\s*days?\s*ago", p_lower)
    if m:
        return int(m.group(1)) <= max_age_days
    m = re.search(r"(\d+)\s*weeks?\s*ago", p_lower)
    if m:
        return False  # weeks ago = not fresh
    m = re.search(r"(\d+)\s*months?\s*ago", p_lower)
    if m:
        return False

    # Try absolute date formats
    from datetime import datetime
    formats = [
        "%Y-%m-%d",                   # 2026-05-14
        "%Y-%m-%dT%H:%M:%S",          # ISO 8601
        "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %Z",   # RFC 2822 (e.g. "Mon, 13 May 2026 12:00:00 GMT")
        "%a, %d %b %Y %H:%M:%S",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            posted_dt = datetime.strptime(posted[:30].strip(), fmt)
            age_days = (datetime.now() - posted_dt).days
            return age_days <= max_age_days
        except (ValueError, TypeError):
            continue

    # Try ISO date with just first 10 chars
    try:
        posted_dt = datetime.strptime(posted[:10], "%Y-%m-%d")
        age_days = (datetime.now() - posted_dt).days
        return age_days <= max_age_days
    except (ValueError, TypeError):
        pass

    # Unparseable — keep it (better to include than miss)
    return True


def title_is_relevant(title: str) -> bool:
    title_lower = title.lower()
    padded = f" {title_lower} "

    # Hard blocklist — skip even if title has a PM keyword
    if any(bl in title_lower for bl in TITLE_BLOCKLIST):
        return False

    # Too-senior check
    for word in REJECT_SENIORITY_KEYWORDS:
        if f" {word} " in padded:
            return False

    return any(kw in title_lower for kw in RELEVANT_TITLE_KEYWORDS)


def run():
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"Robot Cycle: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    init_db()
    print(f"DB: {get_seen_count()} jobs seen so far\n")

    # ── Scrape ──────────────────────────────────────────────────
    general_jobs = scrape_all_sources()
    org_jobs     = scrape_all_orgs()
    all_jobs     = org_jobs + general_jobs

    new_jobs = [j for j in all_jobs if not is_seen(j["id"])]
    print(f"\nScraped: {len(all_jobs)} total | {len(new_jobs)} new\n")

    if not new_jobs:
        print("Nothing new this cycle.")
        return

    # ── Title pre-filter ────────────────────────────────────────
    relevant   = [j for j in new_jobs if title_is_relevant(j.get("title", ""))]
    irrelevant = [j for j in new_jobs if not title_is_relevant(j.get("title", ""))]

    for job in irrelevant:
        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

    print(f"Title pre-filter: {len(relevant)} relevant | {len(irrelevant)} irrelevant (skipped)\n")

    if not relevant:
        print("No relevant titles this cycle.")
        return

    # ── Score (capped per run) ──────────────────────────────────
    to_score = relevant[:MAX_SCORE_PER_RUN]
    deferred = relevant[MAX_SCORE_PER_RUN:]
    if deferred:
        print(f"Note: {len(deferred)} jobs deferred to next cycle (cap={MAX_SCORE_PER_RUN}/run)\n")

    matches      = []
    scored_count = 0
    quota_hit_at = None   # index where quota was exhausted

    print(f"Scoring {len(to_score)} jobs...\n")

    for i, job in enumerate(to_score, 1):
        icon = "🏛️" if job.get("cap_exempt") else "📋"
        print(f"  [{i}/{len(to_score)}] {icon} {job.get('title')} @ {job.get('company')}")

        result = evaluate_job(job)

        import scorer
        if scorer.DAILY_QUOTA_EXHAUSTED:
            quota_hit_at = i
            # Log this job as unscored (scoring was attempted but quota hit)
            log_scraped_job(job, score_result=None)
            print(f"\n  Quota exhausted at job {i}. Stopping scoring.")
            break

        # Log to daily scrape sheet (with score if we got one)
        log_scraped_job(job, score_result=result)

        if result:
            scored_count += 1
            matches.append(result)
            log_to_sheets(result)
            if SEND_INSTANT_EMAIL:
                send_match_email(result)

        time.sleep(5)

    # ── Handle quota exhaustion ─────────────────────────────────
    if quota_hit_at is not None:
        # Jobs that weren't attempted at all
        not_attempted = to_score[quota_hit_at:] + deferred

        print(f"\n  Logging {len(not_attempted)} unscored jobs to Daily Scrape Log...")
        batch_log_unscored(not_attempted)

        # Mark them as seen so they aren't re-queued tomorrow
        # (they'll appear in the daily log for manual review)
        for job in not_attempted:
            mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

        # Email unscored digest
        all_unscored = to_score[quota_hit_at - 1:] + deferred  # include the one that hit quota
        send_unscored_digest(all_unscored, scored_count=scored_count)
        print(f"  Quota reset: midnight UTC (8 PM Eastern). Bot resumes scoring automatically.")

    elif deferred:
        # Quota fine, but some deferred jobs — log them to daily sheet too
        print(f"\n  Logging {len(deferred)} deferred jobs to Daily Scrape Log...")
        batch_log_unscored(deferred)
        for job in deferred:
            mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

    # ── Send one combined match email for this run ───────────────
    if matches and SEND_DAILY_DIGEST:
        send_daily_digest(matches)
        print(f"  📧 Match digest sent: {len(matches)} matches")

    # ── Summary ─────────────────────────────────────────────────
    elapsed   = (datetime.now() - start).seconds
    contracts = [m for m in matches if m.get("is_short_contract")]
    fulltime  = [m for m in matches if not m.get("is_short_contract")]

    print(f"\n{'─'*60}")
    print(f"Done in {elapsed}s")
    print(f"  Scored: {scored_count} | Matches >= {MATCH_THRESHOLD}%: {len(matches)}")
    print(f"  ({len(contracts)} contract | {len(fulltime)} full-time cap-exempt)")

    if matches:
        print("\n  Top matches this cycle:")
        for m in sorted(matches, key=lambda x: x['match_score'], reverse=True)[:8]:
            icon = "📋" if m.get("is_short_contract") else ("✅" if m.get("is_verified_h1b") else "⭐")
            print(f"    {m['match_score']}% {icon} {m['title']} @ {m['company']}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    run()
