# =============================================================================
# scraper.py — Pulls jobs from 10 sources:
#   1. LinkedIn        (via python-jobspy)
#   2. Indeed          (via python-jobspy)
#   3. Glassdoor       (via python-jobspy)
#   4. ZipRecruiter    (via python-jobspy)
#   5. Google Jobs     (via python-jobspy)
#   6. Built In Boston (custom RSS scraper)
#   7. Idealist        (custom RSS — great for nonprofits/cap-exempt)
#   8. USAJobs         (official federal API — gov/research jobs)
#   9. SimplyHired     (RSS feed)
#  10. Dice            (RSS feed — good for tech-adjacent PM roles)
# =============================================================================

import hashlib
import time
import re
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd

try:
    from jobspy import scrape_jobs as jobspy_scrape
    JOBSPY_AVAILABLE = True
except ImportError:
    JOBSPY_AVAILABLE = False
    print("⚠️  python-jobspy not installed. Run: pip install python-jobspy")

from config import JOB_TITLES, LOCATIONS


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def make_job_id(url: str, title: str, company: str) -> str:
    """Create a stable unique ID for deduplication."""
    raw = f"{url}{title}{company}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()


def clean_text(text: str) -> str:
    """Remove excess whitespace and HTML tags."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_job(title, company, location, description, url, source, posted_date=None):
    """Return a standardized job dict regardless of source."""
    return {
        "id":          make_job_id(url, title, company),
        "title":       clean_text(title),
        "company":     clean_text(company),
        "location":    clean_text(location),
        "description": clean_text(description),
        "url":         url,
        "source":      source,
        "posted_date": posted_date or datetime.now().strftime("%Y-%m-%d"),
    }


# ─────────────────────────────────────────────────────────────
# SOURCE 1–5: python-jobspy (LinkedIn, Indeed, Glassdoor,
#             ZipRecruiter, Google Jobs)
# ─────────────────────────────────────────────────────────────

def scrape_jobspy_sources() -> list[dict]:
    """
    Uses python-jobspy to pull from LinkedIn, Indeed, Glassdoor,
    ZipRecruiter, and Google Jobs in one call per title/location combo.
    """
    if not JOBSPY_AVAILABLE:
        return []

    all_jobs = []
    sites = ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"]

    for title in JOB_TITLES:
        for location in LOCATIONS:
            print(f"  🔍 jobspy: '{title}' in '{location}'...")
            try:
                df = jobspy_scrape(
                    site_name=sites,
                    search_term=title,
                    location=location,
                    results_wanted=15,       # per site per search
                    hours_old=26,            # only recent postings
                    country_indeed="USA",
                    verbose=0,
                )
                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    job = normalize_job(
                        title=str(row.get("title", "")),
                        company=str(row.get("company", "")),
                        location=str(row.get("location", "")),
                        description=str(row.get("description", "")),
                        url=str(row.get("job_url", "")),
                        source=str(row.get("site", "jobspy")),
                        posted_date=str(row.get("date_posted", "")),
                    )
                    all_jobs.append(job)

            except Exception as e:
                print(f"    ⚠️  jobspy error for '{title}' / '{location}': {e}")

            time.sleep(3)   # Be polite — don't hammer the sites

    return all_jobs


# ─────────────────────────────────────────────────────────────
# SOURCE 6: Built In Boston (RSS scraper)
# ─────────────────────────────────────────────────────────────

BUILTIN_RSS_TEMPLATE = (
    "https://www.builtinboston.com/jobs/feed"
    "?search[keywords]={keywords}&search[job_types][]=full_time"
)

def scrape_builtin_boston() -> list[dict]:
    """Pull jobs from Built In Boston via their RSS feed."""
    all_jobs = []
    # Batch titles into a few representative searches
    search_terms = [
        "program manager",
        "project manager",
        "operations",
        "program coordinator",
        "project coordinator",
    ]

    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-bot/1.0)"}

    for term in search_terms:
        url = BUILTIN_RSS_TEMPLATE.format(keywords=term.replace(" ", "+"))
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                job = normalize_job(
                    title=entry.get("title", ""),
                    company=entry.get("author", "Unknown"),
                    location="Boston, MA",
                    description=entry.get("summary", ""),
                    url=entry.get("link", ""),
                    source="Built In Boston",
                    posted_date=entry.get("published", ""),
                )
                all_jobs.append(job)
        except Exception as e:
            print(f"    ⚠️  Built In Boston error: {e}")

        time.sleep(2)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# SOURCE 7: Idealist (nonprofits — excellent for cap-exempt H-1B)
# ─────────────────────────────────────────────────────────────

IDEALIST_RSS = (
    "https://www.idealist.org/en/jobs/rss"
    "?q={query}&loc=Boston+MA&type=JOB"
)

def scrape_idealist() -> list[dict]:
    """Pull nonprofit / mission-driven jobs from Idealist."""
    all_jobs = []
    terms = ["program manager", "project manager", "operations", "coordinator"]

    for term in terms:
        url = IDEALIST_RSS.format(query=term.replace(" ", "+"))
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                job = normalize_job(
                    title=entry.get("title", ""),
                    company=entry.get("author", ""),
                    location=entry.get("tags", [{}])[0].get("term", "Boston, MA") if entry.get("tags") else "Boston, MA",
                    description=entry.get("summary", ""),
                    url=entry.get("link", ""),
                    source="Idealist",
                    posted_date=entry.get("published", ""),
                )
                all_jobs.append(job)
        except Exception as e:
            print(f"    ⚠️  Idealist error: {e}")

        time.sleep(2)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# SOURCE 8: USAJobs (Official US Government API)
# Hospitals, universities, VA, research agencies — cap-exempt goldmine
# ─────────────────────────────────────────────────────────────

USAJOBS_API = "https://data.usajobs.gov/api/search"
USAJOBS_HEADERS = {
    "Host": "data.usajobs.gov",
    "User-Agent": "anjalikandimalla81@gmail.com",  # Required by API
    "Authorization-Key": "",  # Optional but increases rate limit
}

def scrape_usajobs() -> list[dict]:
    """Pull government / research jobs from the USAJobs public API."""
    all_jobs = []
    search_terms = ["program manager", "project manager", "operations analyst", "program coordinator"]

    for term in search_terms:
        params = {
            "Keyword": term,
            "LocationName": "Boston, MA",
            "ResultsPerPage": 25,
            "SortField": "OpenDate",
            "SortDirection": "Desc",
        }
        try:
            resp = requests.get(USAJOBS_API, headers=USAJOBS_HEADERS, params=params, timeout=15)
            data = resp.json()
            items = data.get("SearchResult", {}).get("SearchResultItems", [])

            for item in items:
                pos = item.get("MatchedObjectDescriptor", {})
                job = normalize_job(
                    title=pos.get("PositionTitle", ""),
                    company=pos.get("OrganizationName", ""),
                    location=pos.get("PositionLocationDisplay", ""),
                    description=pos.get("UserArea", {}).get("Details", {}).get("JobSummary", ""),
                    url=pos.get("PositionURI", ""),
                    source="USAJobs",
                    posted_date=pos.get("PublicationStartDate", "")[:10] if pos.get("PublicationStartDate") else "",
                )
                all_jobs.append(job)

        except Exception as e:
            print(f"    ⚠️  USAJobs error: {e}")

        time.sleep(2)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# SOURCE 9: SimplyHired (RSS)
# ─────────────────────────────────────────────────────────────

SIMPLYHIRED_RSS = (
    "https://www.simplyhired.com/search"
    "?q={query}&l={location}&pn=1&output=rss&sb=dd"
)

def scrape_simplyhired() -> list[dict]:
    """Pull from SimplyHired RSS — good aggregator of niche postings."""
    all_jobs = []
    combos = [
        ("program manager", "Boston+MA"),
        ("project coordinator", "Boston+MA"),
        ("operations analyst", "Boston+MA"),
        ("program manager", "remote"),
    ]

    for term, loc in combos:
        url = SIMPLYHIRED_RSS.format(
            query=term.replace(" ", "+"),
            location=loc
        )
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                job = normalize_job(
                    title=entry.get("title", ""),
                    company=entry.get("author", ""),
                    location=loc.replace("+", " "),
                    description=entry.get("summary", ""),
                    url=entry.get("link", ""),
                    source="SimplyHired",
                    posted_date=entry.get("published", ""),
                )
                all_jobs.append(job)
        except Exception as e:
            print(f"    ⚠️  SimplyHired error: {e}")

        time.sleep(2)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# SOURCE 10: Dice (tech-adjacent PM / ops roles)
# ─────────────────────────────────────────────────────────────

DICE_RSS = "https://www.dice.com/jobs/q-{query}-l-{location}-rss.rss"

def scrape_dice() -> list[dict]:
    """Pull tech-adjacent PM roles from Dice."""
    all_jobs = []
    combos = [
        ("program+manager", "boston+ma"),
        ("project+manager", "boston+ma"),
        ("operations+manager", "remote"),
    ]

    for term, loc in combos:
        url = DICE_RSS.format(query=term, location=loc)
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                job = normalize_job(
                    title=entry.get("title", ""),
                    company=entry.get("author", ""),
                    location=loc.replace("+", " "),
                    description=entry.get("summary", ""),
                    url=entry.get("link", ""),
                    source="Dice",
                    posted_date=entry.get("published", ""),
                )
                all_jobs.append(job)
        except Exception as e:
            print(f"    ⚠️  Dice error: {e}")

        time.sleep(2)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# MASTER SCRAPER — calls all sources and deduplicates
# ─────────────────────────────────────────────────────────────

def scrape_all_sources() -> list[dict]:
    """
    Run all scrapers and return a deduplicated list of jobs.
    Each job is a dict with: id, title, company, location,
    description, url, source, posted_date.
    """
    print("\n📡 Starting scrape across all sources...")

    all_jobs = []

    # Sources 1–5: jobspy (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google)
    print("\n[1/6] LinkedIn + Indeed + Glassdoor + ZipRecruiter + Google Jobs...")
    all_jobs += scrape_jobspy_sources()

    # Source 6: Built In Boston
    print("\n[2/6] Built In Boston...")
    all_jobs += scrape_builtin_boston()

    # Source 7: Idealist
    print("\n[3/6] Idealist (nonprofits)...")
    all_jobs += scrape_idealist()

    # Source 8: USAJobs
    print("\n[4/6] USAJobs (government/research)...")
    all_jobs += scrape_usajobs()

    # Source 9: SimplyHired
    print("\n[5/6] SimplyHired...")
    all_jobs += scrape_simplyhired()

    # Source 10: Dice
    print("\n[6/6] Dice...")
    all_jobs += scrape_dice()

    # Deduplicate by job ID
    seen_ids = set()
    unique_jobs = []
    for job in all_jobs:
        if job["id"] not in seen_ids and job["url"]:
            seen_ids.add(job["id"])
            unique_jobs.append(job)

    print(f"\n✅ Scraped {len(all_jobs)} total postings → {len(unique_jobs)} unique jobs")
    return unique_jobs
