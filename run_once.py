# =============================================================================
# run_once.py — Runs exactly ONE scrape + score cycle.
#
# Used by GitHub Actions (which handles the scheduling externally).
# Does NOT start the APScheduler loop — just runs the pipeline once and exits.
# =============================================================================

import time
from datetime import datetime

from config import MATCH_THRESHOLD, SEND_INSTANT_EMAIL
from database import init_db, is_seen, mark_seen, get_seen_count
from scraper import scrape_all_sources
from scorer import evaluate_job
from logger import log_to_sheets, send_match_email

def run():
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"⏰ GitHub Actions cycle: {start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}")

    init_db()
    print(f"💾 DB ready — {get_seen_count()} jobs seen so far")

    # Scrape
    raw_jobs = scrape_all_sources()
    new_jobs = [j for j in raw_jobs if not is_seen(j["id"])]
    print(f"\n🆕 {len(new_jobs)} new jobs to score (out of {len(raw_jobs)} scraped)")

    if not new_jobs:
        print("😴 Nothing new this cycle.")
        return

    # Score
    matches = []
    for i, job in enumerate(new_jobs, 1):
        print(f"\n  [{i}/{len(new_jobs)}] {job.get('title')} @ {job.get('company')}")
        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

        result = evaluate_job(job)
        if result:
            matches.append(result)
            log_to_sheets(result)
            if SEND_INSTANT_EMAIL:
                send_match_email(result)

        time.sleep(4)   # Respect Gemini's 15 req/min free limit

    # Summary
    elapsed = (datetime.now() - start).seconds
    print(f"\n{'─'*60}")
    print(f"✅ Done in {elapsed}s — {len(matches)} match(es) found (≥{MATCH_THRESHOLD}%)")
    for m in sorted(matches, key=lambda x: x['match_score'], reverse=True):
        cap = " ⭐" if m.get("is_cap_exempt") else ""
        print(f"   {m['match_score']}%{cap} — {m['title']} @ {m['company']}")
    print(f"{'─'*60}\n")

if __name__ == "__main__":
    run()
