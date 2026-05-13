# =============================================================================
# run_once.py — One full scrape + score cycle (used by GitHub Actions)
# =============================================================================

import time
from datetime import datetime

from config import MATCH_THRESHOLD, SEND_INSTANT_EMAIL
from database import init_db, is_seen, mark_seen, get_seen_count
from scraper import scrape_all_sources          # General job boards
from org_scraper import scrape_all_orgs         # Direct org career pages
from scorer import evaluate_job
from logger import log_to_sheets, send_match_email


def run():
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"🤖 Cycle: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    init_db()
    print(f"💾 DB: {get_seen_count()} jobs seen so far\n")

    # ── Scrape both sources ─────────────────────────────────────
    general_jobs = scrape_all_sources()    # Indeed, LinkedIn, BIB, staffing, etc.
    org_jobs     = scrape_all_orgs()       # Workday, Greenhouse, HigherEdJobs, Harvard, MIT

    # Merge — org jobs first (higher priority)
    all_jobs = org_jobs + general_jobs

    # Filter to unseen
    new_jobs = [j for j in all_jobs if not is_seen(j["id"])]
    print(f"\n📊 Total scraped: {len(all_jobs)} | New: {len(new_jobs)}")

    if not new_jobs:
        print("😴 Nothing new this cycle.")
        return

    # ── Score each new job ──────────────────────────────────────
    matches = []
    print(f"\n🤖 Scoring {len(new_jobs)} new jobs...\n")

    for i, job in enumerate(new_jobs, 1):
        source_tag = "🏛️" if job.get("cap_exempt") else "📋"
        print(f"  [{i}/{len(new_jobs)}] {source_tag} {job.get('title')} @ {job.get('company')} ({job.get('source')})")

        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

        result = evaluate_job(job)
        if result:
            matches.append(result)
            log_to_sheets(result)
            if SEND_INSTANT_EMAIL:
                send_match_email(result)

        time.sleep(4)   # Respect Gemini 15 req/min free limit

    # ── Summary ─────────────────────────────────────────────────
    elapsed = (datetime.now() - start).seconds
    contracts = [m for m in matches if m.get("is_short_contract")]
    fulltime  = [m for m in matches if not m.get("is_short_contract")]

    print(f"\n{'─'*60}")
    print(f"✅ Done in {elapsed}s")
    print(f"   Matches ≥{MATCH_THRESHOLD}%: {len(matches)} total "
          f"({len(contracts)} contract | {len(fulltime)} full-time cap-exempt)")

    if matches:
        print("\n   🎯 Top matches:")
        for m in sorted(matches, key=lambda x: x['match_score'], reverse=True)[:8]:
            icon = "📋" if m.get("is_short_contract") else ("✅" if m.get("is_verified_h1b") else "⭐")
            print(f"      {m['match_score']}% {icon} [{m.get('employment_type','')}] "
                  f"{m['title']} @ {m['company']}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    run()
