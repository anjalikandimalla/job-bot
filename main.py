# =============================================================================
# main.py — The orchestrator. Runs every 25 minutes:
#   1. Scrapes all 10 job sources
#   2. Skips jobs already seen (deduplication)
#   3. Scores each new job with Claude API
#   4. Logs 80%+ matches to Google Sheets
#   5. Emails you instantly for each match
#   6. Sends a daily digest at 8:00 AM
#
# HOW TO RUN:
#   python main.py
#
# To run in the background (won't stop when you close terminal):
#   nohup python main.py &
# =============================================================================

import time
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import POLL_INTERVAL_MINUTES, MATCH_THRESHOLD, SEND_INSTANT_EMAIL, SEND_DAILY_DIGEST
from database import init_db, is_seen, mark_seen, get_seen_count
from scraper import scrape_all_sources
from scorer import evaluate_job
from logger import log_to_sheets, send_match_email, send_daily_digest

# Track today's matches for the daily digest
todays_matches: list[dict] = []


def run_job_cycle():
    """
    One full cycle: scrape → deduplicate → score → log → notify.
    Called every POLL_INTERVAL_MINUTES.
    """
    global todays_matches
    cycle_start = datetime.now()
    print(f"\n{'='*60}")
    print(f"⏰ Cycle started at {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Total jobs seen so far: {get_seen_count()}")
    print(f"{'='*60}")

    # ── STEP 1: Scrape all sources ──────────────────────────────
    raw_jobs = scrape_all_sources()
    print(f"\n📦 {len(raw_jobs)} unique jobs found across all sources")

    # ── STEP 2: Filter to unseen jobs ──────────────────────────
    new_jobs = [j for j in raw_jobs if not is_seen(j["id"])]
    print(f"🆕 {len(new_jobs)} are new (not seen before)")

    if not new_jobs:
        print("   Nothing new this cycle. See you in 25 minutes! 😴")
        return

    # ── STEP 3: Score each new job ──────────────────────────────
    matches = []
    print(f"\n🤖 Scoring {len(new_jobs)} new jobs with Claude...")

    for i, job in enumerate(new_jobs, 1):
        print(f"\n  [{i}/{len(new_jobs)}] {job.get('title')} @ {job.get('company')} ({job.get('source')})")

        # Mark as seen BEFORE scoring (so even rejected ones aren't re-evaluated)
        mark_seen(job["id"], job.get("title",""), job.get("company",""), job.get("url",""))

        result = evaluate_job(job)

        if result is not None:
            matches.append(result)
            todays_matches.append(result)

            # ── STEP 4: Log to Google Sheets ────────────────────
            log_to_sheets(result)

            # ── STEP 5: Instant email alert ─────────────────────
            if SEND_INSTANT_EMAIL:
                send_match_email(result)

        # Small delay between Claude API calls
        time.sleep(1.5)

    # ── CYCLE SUMMARY ───────────────────────────────────────────
    elapsed = (datetime.now() - cycle_start).seconds
    print(f"\n{'─'*60}")
    print(f"✅ Cycle complete in {elapsed}s")
    print(f"   Scored: {len(new_jobs)} jobs | Matches (≥{MATCH_THRESHOLD}%): {len(matches)}")
    if matches:
        print(f"\n   🎯 Top matches this cycle:")
        for m in sorted(matches, key=lambda x: x['match_score'], reverse=True)[:5]:
            cap = " ⭐" if m.get("is_cap_exempt") else ""
            print(f"      {m['match_score']}%{cap} — {m['title']} @ {m['company']}")
    print(f"{'─'*60}\n")


def send_morning_digest():
    """Sends a digest of all matches from the past 24 hours. Runs at 8 AM."""
    global todays_matches
    print(f"\n📬 Sending morning digest ({len(todays_matches)} matches today)...")
    if SEND_DAILY_DIGEST:
        send_daily_digest(todays_matches)
    todays_matches = []  # Reset for the new day


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║           🤖 JOB APPLICATION BOT — STARTING UP          ║
╠══════════════════════════════════════════════════════════╣
║  Targets:  Program/Project Manager, Coordinator,         ║
║            Operations roles (entry to mid-level)         ║
║  Sources:  LinkedIn, Indeed, Glassdoor, ZipRecruiter,    ║
║            Google Jobs, Built In Boston, Idealist,        ║
║            USAJobs, SimplyHired, Dice                    ║
║  Threshold: 80% match minimum                            ║
║  Interval:  Every 25 minutes                             ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Initialize the database
    init_db()
    print(f"💾 Database initialized ({get_seen_count()} jobs seen so far)\n")

    # Run once immediately on startup
    print("🚀 Running first cycle now...")
    run_job_cycle()

    # Schedule recurring cycles
    scheduler = BlockingScheduler()

    # Every 25 minutes: scrape + score
    scheduler.add_job(
        run_job_cycle,
        trigger=IntervalTrigger(minutes=POLL_INTERVAL_MINUTES),
        id="job_cycle",
        name="Scrape & Score",
        misfire_grace_time=120,
    )

    # Every morning at 8 AM: daily digest email
    scheduler.add_job(
        send_morning_digest,
        trigger=CronTrigger(hour=8, minute=0),
        id="morning_digest",
        name="Daily Digest",
    )

    print(f"\n⏰ Scheduler running. Next cycle in {POLL_INTERVAL_MINUTES} minutes.")
    print("   Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n\n👋 Bot stopped. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
