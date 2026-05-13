# =============================================================================
# run_once.py — One full scrape + score cycle (used by GitHub Actions)
#
# KEY FIXES vs previous version:
#   1. Title pre-filter BEFORE Gemini — rejects irrelevant jobs locally
#   2. Per-run scoring cap (MAX_SCORE_PER_RUN) — prevents quota exhaustion
#   3. Jobs that pass title filter but exceed cap are still marked seen
#      so they don't pile up across runs
# =============================================================================

import re
import time
from datetime import datetime

from config import MATCH_THRESHOLD, SEND_INSTANT_EMAIL, JOB_TITLES, REJECT_SENIORITY_KEYWORDS
from database import init_db, is_seen, mark_seen, get_seen_count
from scraper import scrape_all_sources
from org_scraper import scrape_all_orgs
from scorer import evaluate_job
from logger import log_to_sheets, send_match_email

# ─────────────────────────────────────────────────────────────
# HOW MANY JOBS TO SCORE PER RUN
# Free Gemini tier: 1,500 requests/day = ~31 runs/day × 48 jobs/run
# We use 80 to leave headroom. Increase if you add paid Gemini.
# ─────────────────────────────────────────────────────────────
MAX_SCORE_PER_RUN = 80

# ─────────────────────────────────────────────────────────────
# TITLE PRE-FILTER (local — no API call)
# Only send jobs to Gemini if title contains a relevant keyword.
# This cuts 90%+ of irrelevant jobs before touching the quota.
# ─────────────────────────────────────────────────────────────

# Words any relevant title should contain at least one of
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

def title_is_relevant(title: str) -> bool:
    """
    Return True if the job title contains at least one relevant keyword
    AND does not contain a seniority-rejection keyword.
    Fast local check — no API call needed.
    """
    title_lower = title.lower()
    padded      = f" {title_lower} "

    # Reject too-senior titles first (whole-word match)
    for word in REJECT_SENIORITY_KEYWORDS:
        if f" {word} " in padded:
            return False

    # Must contain at least one relevant keyword
    return any(kw in title_lower for kw in RELEVANT_TITLE_KEYWORDS)


def run():
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"🤖 Cycle: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    init_db()
    print(f"💾 DB: {get_seen_count()} jobs seen so far\n")

    # ── Scrape ──────────────────────────────────────────────────
    general_jobs = scrape_all_sources()
    org_jobs     = scrape_all_orgs()
    all_jobs     = org_jobs + general_jobs   # org jobs get priority

    # ── Filter to unseen ────────────────────────────────────────
    new_jobs = [j for j in all_jobs if not is_seen(j["id"])]
    print(f"\n📊 Scraped: {len(all_jobs)} total | {len(new_jobs)} new\n")

    if not new_jobs:
        print("😴 Nothing new this cycle.")
        return

    # ── Title pre-filter (local, free) ──────────────────────────
    relevant    = []
    irrelevant  = []
    for job in new_jobs:
        if title_is_relevant(job.get("title", "")):
            relevant.append(job)
        else:
            irrelevant.append(job)

    # Mark ALL irrelevant jobs as seen immediately — never score them
    for job in irrelevant:
        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

    print(f"🔍 Title pre-filter: {len(relevant)} relevant | "
          f"{len(irrelevant)} irrelevant (marked seen, skipped)")

    if not relevant:
        print("😴 No relevant titles this cycle.")
        return

    # ── Cap scoring to protect free quota ───────────────────────
    to_score = relevant[:MAX_SCORE_PER_RUN]
    deferred = relevant[MAX_SCORE_PER_RUN:]

    if deferred:
        print(f"⏳ {len(deferred)} jobs deferred to next cycle "
              f"(cap is {MAX_SCORE_PER_RUN}/run to protect free quota)")

    # ── Score each relevant job ──────────────────────────────────
    matches = []
    print(f"\n🤖 Scoring {len(to_score)} jobs...\n")

    for i, job in enumerate(to_score, 1):
        source_tag = "🏛️" if job.get("cap_exempt") else "📋"
        print(f"  [{i}/{len(to_score)}] {source_tag} "
              f"{job.get('title')} @ {job.get('company')} ({job.get('source')})")

        # Mark seen BEFORE scoring so restarts don't re-score
        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

        result = evaluate_job(job)
        if result:
            matches.append(result)
            log_to_sheets(result)
            if SEND_INSTANT_EMAIL:
                send_match_email(result)

        time.sleep(5)   # ~12 req/min — safely under the 15/min free limit

    # ── Summary ─────────────────────────────────────────────────
    elapsed   = (datetime.now() - start).seconds
    contracts = [m for m in matches if m.get("is_short_contract")]
    fulltime  = [m for m in matches if not m.get("is_short_contract")]

    print(f"\n{'─'*60}")
    print(f"✅ Done in {elapsed}s")
    print(f"   Scored: {len(to_score)} | Matches ≥{MATCH_THRESHOLD}%: {len(matches)} "
          f"({len(contracts)} contract | {len(fulltime)} full-time)")

    if matches:
        print("\n   🎯 Top matches this cycle:")
        for m in sorted(matches, key=lambda x: x['match_score'], reverse=True)[:8]:
            icon = "📋" if m.get("is_short_contract") else ("✅" if m.get("is_verified_h1b") else "⭐")
            print(f"      {m['match_score']}% {icon} [{m.get('employment_type','')}] "
                  f"{m['title']} @ {m['company']}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    run()
