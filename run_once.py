# =============================================================================
# run_once.py — One scrape + score cycle (runs every 3 hours via GitHub Actions)
#
# Flow:
#   1. Scrape general job boards + direct cap-exempt org career pages
#   2. Local title / freshness / eligibility filters before any Gemini call
#   3. Score a capped number of fresh eligible jobs with Gemini
#   4. Log matches to the main Job Bot Log
#   5. Log unscored/deferred jobs to the Daily Scrape Log
#   6. Send ONE digest email for this run's top matches
#
# Important behavior:
#   - Irrelevant, stale, locally rejected, and attempted jobs are marked seen.
#   - Deferred jobs caused only by MAX_SCORE_PER_RUN are NOT marked seen, so they
#     can be tried in the next run while still fresh.
#   - If Gemini daily quota is exhausted, the remaining relevant jobs are logged
#     and emailed as unscored, then marked seen to avoid repeated quota emails.
# =============================================================================

from __future__ import annotations

import re
import time
from datetime import datetime

from config import MATCH_THRESHOLD, REJECT_SENIORITY_KEYWORDS, TIER_LABELS
from database import init_db, is_seen, mark_seen, get_seen_count
from scraper import scrape_all_sources
from sources_contract import scrape_all_contract_sources
from org_scraper import scrape_all_orgs
from scorer import evaluate_job, sort_matches
import scorer  # read scorer.DAILY_QUOTA_EXHAUSTED after evaluate_job()
from logger import log_to_sheets, send_digest_email
from daily_log import log_scraped_job, batch_log_unscored, send_unscored_digest

# ─────────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────────

MAX_SCORE_PER_RUN = 80   # Safe cap for Gemini free tier
MAX_AGE_DAYS      = 1    # Score only jobs posted in the last 24 hours when date is known
DIGEST_TOP_N      = 20   # Top N matches to include in the digest email
SLEEP_BETWEEN_SCORES = 5 # Helps avoid per-minute rate limits

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
    "grants manager", "grants coordinator", "grants administrator",
    "research coordinator", "research program", "research administrator",
    "sponsored programs", "sponsored research",
    "clinical program", "clinical coordinator", "clinical operations",
    "study coordinator", "study start-up", "trial coordinator",
    "alliance management", "clinical outsourcing",
    "success manager", "engagement manager",
    "implementation manager", "delivery manager",
    "portfolio manager", "initiative manager",
    "special projects", "academic program", "faculty affairs",
    "pmo analyst", "pmo coordinator", "program operations",
    # Internship lane
    "program management intern", "project management intern",
    "operations intern", "program intern", "project intern",
    "pmo intern", "mba intern", "graduate intern",
    "strategy and operations intern", "business operations intern",
    "co-op", "program co-op", "project co-op",
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
    """Fast local title filter. No API calls."""
    title_lower = (title or "").lower()
    padded = " " + title_lower + " "

    if any(bl in title_lower for bl in TITLE_BLOCKLIST):
        return False

    for word in REJECT_SENIORITY_KEYWORDS:
        # Keep whole-phrase matching so "coo" does not reject "coordinator".
        if " " + word.lower() + " " in padded:
            return False

    return any(kw in title_lower for kw in RELEVANT_TITLE_KEYWORDS)


def is_recent_posting(job: dict, max_age_days: int = MAX_AGE_DAYS) -> bool:
    """
    True if posted within max_age_days.

    General boards can be lenient because many feeds are already filtered to 24h
    but may not expose clean dates. Direct org jobs are stricter because Workday / 
    Greenhouse often return all open roles.
    """
    if max_age_days <= 0:
        return True

    is_org = bool(job.get("cap_exempt"))
    posted = (job.get("posted_date") or "").strip()

    if not posted:
        return False if is_org else True

    p = posted.lower()

    if any(x in p for x in ["just now", "just posted", "today", "hours ago", "minutes ago", "new"]):
        return True

    if "yesterday" in p or "1 day ago" in p:
        return max_age_days >= 1

    m = re.search(r"(\d+)\s*days?\s*ago", p)
    if m:
        return int(m.group(1)) <= max_age_days

    # Workday sometimes uses "30+" / "30+ days" for old postings.
    if re.search(r"\d+\+", p):
        return False

    if re.search(r"\d+\s*weeks?\s*ago", p) or re.search(r"\d+\s*months?\s*ago", p):
        return False

    # Absolute date parsing.
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S+00:00",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S",
        "%d %b %Y",
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

    return False if is_org else True


# ─────────────────────────────────────────────────────────────
# SMALL HELPERS
# ─────────────────────────────────────────────────────────────

def _mark_seen(job: dict) -> None:
    """Safely mark a job as seen if it has an ID."""
    job_id = job.get("id")
    if not job_id:
        return
    mark_seen(
        job_id,
        job.get("title", ""),
        job.get("company", ""),
        job.get("url", ""),
    )


def _dedupe_jobs(jobs: list[dict]) -> list[dict]:
    """Deduplicate jobs by ID, preserving first occurrence."""
    seen_ids = set()
    unique = []
    for job in jobs:
        job_id = job.get("id")
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        unique.append(job)
    return unique


def _safe_log_daily(job: dict, result: dict | None = None, status: str | None = None) -> None:
    """
    Call daily_log.log_scraped_job with the newer optional status argument.
    Falls back gracefully if GitHub still has the older daily_log.py for one run.
    """
    try:
        log_scraped_job(job, score_result=result, status=status)
    except TypeError:
        # Older daily_log.py did not accept status=. Avoid crashing the workflow.
        log_scraped_job(job, score_result=result)


def _safe_batch_log_unscored(jobs: list[dict], status: str) -> None:
    """Batch-log unscored jobs, with fallback for older daily_log.py."""
    try:
        batch_log_unscored(jobs, status=status)
    except TypeError:
        batch_log_unscored(jobs)


# ─────────────────────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────────────────────

def run() -> None:
    start = datetime.now()
    print("\n" + "=" * 72)
    print(f"Cycle: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    init_db()
    print(f"DB: {get_seen_count()} jobs seen so far\n")

    # Reset the in-memory quota flag for this process/run.
    scorer.DAILY_QUOTA_EXHAUSTED = False

    # 1) Scrape both source groups.
    print("📡 Scraping sources...")
    org_jobs = scrape_all_orgs()
    general_jobs = scrape_all_sources()
    contract_jobs = scrape_all_contract_sources()
    all_jobs = _dedupe_jobs(org_jobs + general_jobs + contract_jobs)
    print(f"\nScraped: {len(org_jobs)} org + {len(general_jobs)} general "
          f"+ {len(contract_jobs)} contract = {len(all_jobs)} unique jobs")

    # 2) Remove jobs already seen from previous runs.
    new_jobs = [j for j in all_jobs if not is_seen(j.get("id", ""))]
    print(f"New jobs not in DB: {len(new_jobs)}\n")

    if not new_jobs:
        print("Nothing new this cycle.")
        return

    # 3) Title pre-filter. Mark irrelevant titles as seen so they do not repeat.
    title_relevant = []
    title_irrelevant = []
    for job in new_jobs:
        if title_is_relevant(job.get("title", "")):
            title_relevant.append(job)
        else:
            title_irrelevant.append(job)
            _mark_seen(job)

    print(f"Title filter: {len(title_relevant)} relevant | {len(title_irrelevant)} irrelevant (marked seen)")

    # 4) Freshness filter. Mark stale jobs as seen so old open roles do not repeat.
    fresh = []
    stale = []
    for job in title_relevant:
        if is_recent_posting(job):
            fresh.append(job)
        else:
            stale.append(job)
            _mark_seen(job)

    print(f"Freshness filter (≤{MAX_AGE_DAYS} day): {len(fresh)} fresh | {len(stale)} stale (marked seen)")

    if not fresh:
        print("No fresh relevant jobs this cycle.")
        return

    # 5) Local eligibility filter from scorer.py before Gemini.
    #    This saves API quota by removing non-cap-exempt full-time roles, long/unknown contracts,
    #    senior roles, unpaid roles, etc. before scoring.
    eligible = []
    local_rejected = []
    for job in fresh:
        try:
            passes, reason, emp_type, cap_exempt, verified = scorer.passes_local_filter(job)
        except Exception as e:
            passes, reason, emp_type, cap_exempt, verified = False, f"Local filter error: {e}", "unknown", False, False

        # Preserve useful metadata for daily log/status readability.
        job["detected_employment_type"] = emp_type
        job["detected_cap_exempt"] = cap_exempt
        job["detected_verified_h1b"] = verified

        if passes:
            eligible.append(job)
        else:
            local_rejected.append((job, reason))
            _safe_log_daily(job, status=f"🚫 Local filter rejected: {reason}")
            _mark_seen(job)

    print(f"Eligibility filter: {len(eligible)} eligible for Gemini | {len(local_rejected)} locally rejected")

    if not eligible:
        print("No eligible jobs left after local filters.")
        return

    # 6) Score only up to the per-run cap. True deferrals stay un-seen so they can
    #    be attempted in the next scheduled run.
    to_score = eligible[:MAX_SCORE_PER_RUN]
    deferred = eligible[MAX_SCORE_PER_RUN:]

    print(f"\nScoring {len(to_score)} jobs with Gemini...", end="")
    if deferred:
        print(f" ({len(deferred)} deferred due to cap={MAX_SCORE_PER_RUN})")
    else:
        print()

    matches = []
    scored_attempts = 0
    quota_exhausted = False

    for idx, job in enumerate(to_score, start=1):
        icon = "🏛️" if job.get("cap_exempt") else "📋"
        print(f"\n[{idx}/{len(to_score)}] {icon} {job.get('title')} @ {job.get('company')}")

        result = evaluate_job(job)

        # If Gemini daily quota is exhausted, this job and every remaining job were
        # not scored. Log/email them as unscored and mark them seen to prevent the
        # same quota-failure digest every 3 hours.
        if scorer.DAILY_QUOTA_EXHAUSTED:
            quota_exhausted = True
            unscored = to_score[idx - 1:] + deferred
            print(f"\n🚫 Gemini quota exhausted. Logging {len(unscored)} unscored jobs.")
            _safe_batch_log_unscored(unscored, status="⏸️ Quota exceeded — not scored")
            send_unscored_digest(unscored, scored_count=scored_attempts)
            for unscored_job in unscored:
                _mark_seen(unscored_job)
            break

        scored_attempts += 1

        if result:
            matches.append(result)
            log_to_sheets(result)
            _safe_log_daily(job, result=result, status=f"✅ Scored match: {result.get('match_score', 0)}%")
        else:
            _safe_log_daily(job, status="📉 Scored/reviewed — below threshold or rejected by AI")

        # Mark every attempted job as seen whether it matched or not.
        _mark_seen(job)
        time.sleep(SLEEP_BETWEEN_SCORES)

    # If no quota failure happened, log true cap deferrals and leave them un-seen.
    # They can be attempted in the next run while still within the freshness window.
    if deferred and not quota_exhausted:
        print(f"\n⏭️  Logging {len(deferred)} deferred jobs to Daily Scrape Log; they remain un-seen for next run.")
        _safe_batch_log_unscored(
            deferred,
            status=f"⏭️ Deferred — scoring cap reached ({MAX_SCORE_PER_RUN}/run); will retry next run",
        )

    # 7) Send one digest of THIS run's top matches.
    if matches:
        top = sort_matches(matches)[:DIGEST_TOP_N]
        print(f"\n📧 Sending digest: top {len(top)} of {len(matches)} matches from this run...")
        send_digest_email(top)
    else:
        print(f"\nNo ≥{MATCH_THRESHOLD}% matches this run — no match digest sent.")

    # 8) Summary.
    elapsed = int((datetime.now() - start).total_seconds())
    by_tier = {}
    for m in matches:
        by_tier.setdefault(m.get("tier", 9), []).append(m)

    print("\n" + "-" * 72)
    print(f"Done in {elapsed}s | Attempted: {scored_attempts} | Matches ≥{MATCH_THRESHOLD}%: {len(matches)}")
    for tier in sorted(by_tier):
        print(f"  {TIER_LABELS.get(tier, f'Tier {tier}')}: {len(by_tier[tier])}")
    if deferred and not quota_exhausted:
        print(f"  Deferred for next run: {len(deferred)}")
    if quota_exhausted:
        print("  Quota exhausted: unscored jobs were logged + emailed.")
    if matches:
        for m in sort_matches(matches)[:8]:
            dur = m.get("duration_confidence", "")
            flag = " ⚠️unconfirmed" if dur == "unconfirmed" else ""
            print(f"  T{m.get('tier','?')} {m.get('match_score')}% "
                  f"{m.get('title')} @ {m.get('company')}{flag}")
    print("-" * 72 + "\n")


if __name__ == "__main__":
    run()
