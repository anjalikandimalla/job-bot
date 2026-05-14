# =============================================================================
# run_once.py — One full scrape + score cycle (used by GitHub Actions)
# =============================================================================

import time
from datetime import datetime

from config import MATCH_THRESHOLD, SEND_INSTANT_EMAIL, REJECT_SENIORITY_KEYWORDS
from database import init_db, is_seen, mark_seen, get_seen_count
from scraper import scrape_all_sources
from org_scraper import scrape_all_orgs
from scorer import evaluate_job
from logger import log_to_sheets, send_match_email

MAX_SCORE_PER_RUN = 80

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
    title_lower = title.lower()
    padded = f" {title_lower} "
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

    general_jobs = scrape_all_sources()
    org_jobs     = scrape_all_orgs()
    all_jobs     = org_jobs + general_jobs

    new_jobs = [j for j in all_jobs if not is_seen(j["id"])]
    print(f"\nScraped: {len(all_jobs)} total | {len(new_jobs)} new\n")

    if not new_jobs:
        print("Nothing new this cycle.")
        return

    # Title pre-filter
    relevant   = [j for j in new_jobs if title_is_relevant(j.get("title", ""))]
    irrelevant = [j for j in new_jobs if not title_is_relevant(j.get("title", ""))]

    for job in irrelevant:
        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

    print(f"Title pre-filter: {len(relevant)} relevant | {len(irrelevant)} irrelevant (skipped)")

    if not relevant:
        print("No relevant titles this cycle.")
        return

    to_score = relevant[:MAX_SCORE_PER_RUN]
    deferred = relevant[MAX_SCORE_PER_RUN:]
    if deferred:
        print(f"Deferring {len(deferred)} jobs to next cycle (cap={MAX_SCORE_PER_RUN}/run)")

    matches = []
    print(f"\nScoring {len(to_score)} jobs...\n")

    for i, job in enumerate(to_score, 1):
        icon = "🏛️" if job.get("cap_exempt") else "📋"
        print(f"  [{i}/{len(to_score)}] {icon} {job.get('title')} @ {job.get('company')}")

        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

        result = evaluate_job(job)
        if result:
            matches.append(result)
            log_to_sheets(result)
            if SEND_INSTANT_EMAIL:
                send_match_email(result)

        # Import here to get the live value of the flag
        import scorer
        if scorer.DAILY_QUOTA_EXHAUSTED:
            remaining = len(to_score) - i
            print(f"\nDaily quota exhausted after {i} jobs.")
            print(f"  {remaining} jobs deferred — will score in tomorrow's runs.")
            print(f"  Quota resets at midnight UTC (8 PM Eastern).")
            break

        time.sleep(5)

    elapsed   = (datetime.now() - start).seconds
    contracts = [m for m in matches if m.get("is_short_contract")]
    fulltime  = [m for m in matches if not m.get("is_short_contract")]

    print(f"\n{'─'*60}")
    print(f"Done in {elapsed}s | Matches >= {MATCH_THRESHOLD}%: {len(matches)} "
          f"({len(contracts)} contract | {len(fulltime)} full-time)")
    if matches:
        print("\nTop matches:")
        for m in sorted(matches, key=lambda x: x['match_score'], reverse=True)[:8]:
            icon = "📋" if m.get("is_short_contract") else ("✅" if m.get("is_verified_h1b") else "⭐")
            print(f"  {m['match_score']}% {icon} {m['title']} @ {m['company']}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    run()
