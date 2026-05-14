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
MAX_AGE_DAYS      = 1     # Only score jobs posted within last 24 hours
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
    """True if posted within max_age_days. Fails open if date unparseable."""
    if max_age_days <= 0:
        return True
    posted = (job.get("posted_date") or "").strip()
    if not posted:
        return True

    p_lower = posted.lower()
    if any(p in p_lower for p in ["today", "hours ago", "just posted", "minutes ago", "new"]):
        return True
    if "yesterday" in p_lower or "1 day ago" in p_lower:
        return max_age_days >= 1

    m = re.search(r"(\d+)\s*days?\s*ago", p_lower)
    if m:
        return int(m.group(1)) <= max_age_days
    if re.search(r"\d+\s*weeks?\s*ago", p_lower):
        return False
    if re.search(r"\d+\s*months?\s*ago", p_lower):
        return False

    formats = [
        "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S", "%d %b %Y",
    ]
    for fmt in formats:
        try:
            posted_dt = datetime.strptime(posted[:30].strip(), fmt)
            return (datetime.now() - posted_dt).days <= max_age_days
        except (ValueError, TypeError):
            continue
    try:
        posted_dt = datetime.strptime(posted[:10], "%Y-%m-%d")
        return (datetime.now() - posted_dt).days <= max_age_days
    except (ValueError, TypeError):
        pass
    return True


def run():
    start = datetime.now()
    print("\n" + "="*60)
    print(f"Cycle: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

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

    print(f"Title filter: {len(relevant)} relevant | {len(irrelevant)} irrelevant (skipped)")

    # ── Freshness filter (24 hours) ─────────────────────────────
    fresh = [j for j in relevant if is_recent_posting(j)]
    stale = [j for j in relevant if not is_recent_posting(j)]

    for job in stale:
        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

    print(f"Freshness filter (<=24h): {len(fresh)} fresh | {len(stale)} stale (skipped)\n")

    if not fresh:
        print("No fresh relevant jobs this cycle.")
        return

    # ── Mark ALL as seen BEFORE scoring ─────────────────────────
    for job in fresh:
        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

    # ── Score ───────────────────────────────────────────────────
    to_score = fresh[:MAX_SCORE_PER_RUN]
    deferred = fresh[MAX_SCORE_PER_RUN:]

    if deferred:
        print(f"Note: {len(deferred)} fresh jobs deferred to next cycle (cap={MAX_SCORE_PER_RUN})\n")

    matches      = []
    scored_count = 0
    quota_hit_at = None

    print(f"Scoring {len(to_score)} jobs...\n")

    for i, job in enumerate(to_score, 1):
        icon = "🏛️" if job.get("cap_exempt") else "📋"
        print(f"  [{i}/{len(to_score)}] {icon} {job.get('title')} @ {job.get('company')}")

        result = evaluate_job(job)

        import scorer
        if scorer.DAILY_QUOTA_EXHAUSTED:
            quota_hit_at = i
            log_scraped_job(job, score_result=None)
            print(f"\n  Quota exhausted at job {i}. Stopping.")
            break

        log_scraped_job(job, score_result=result)

        if result:
            scored_count += 1
            matches.append(result)
            log_to_sheets(result)

        time.sleep(5)

    # ── Quota exhaustion handling ───────────────────────────────
    if quota_hit_at is not None:
        not_attempted = to_score[quota_hit_at:] + deferred
        print(f"\n  Logging {len(not_attempted)} unscored jobs to Daily Scrape Log...")
        batch_log_unscored(not_attempted)
        send_unscored_digest(not_attempted, scored_count=scored_count)
    elif deferred:
        print(f"\n  Logging {len(deferred)} deferred jobs to Daily Scrape Log...")
        batch_log_unscored(deferred)

    # ── Send digest of THIS run's top matches ───────────────────
    if matches:
        top = sorted(matches, key=lambda x: x["match_score"], reverse=True)[:DIGEST_TOP_N]
        print(f"\n  Sending digest: top {len(top)} of {len(matches)} matches from this run...")
        send_digest_email(top)
    else:
        print("\n  No matches this run — no digest sent.")

    # ── Summary ─────────────────────────────────────────────────
    elapsed   = (datetime.now() - start).seconds
    contracts = [m for m in matches if m.get("is_short_contract")]
    fulltime  = [m for m in matches if not m.get("is_short_contract")]

    print("\n" + "-"*60)
    print(f"Done in {elapsed}s | Scored: {scored_count} | Matches >={MATCH_THRESHOLD}%: {len(matches)}")
    print(f"  ({len(contracts)} contract, {len(fulltime)} full-time cap-exempt)")
    if matches:
        for m in sorted(matches, key=lambda x: x["match_score"], reverse=True)[:8]:
            icon = "📋" if m.get("is_short_contract") else ("✅" if m.get("is_verified_h1b") else "⭐")
            print(f"  {m['match_score']}% {icon} {m['title']} @ {m['company']}")
    print("-"*60 + "\n")


if __name__ == "__main__":
    run()
