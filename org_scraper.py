# =============================================================================
# org_scraper.py — Scrapes career pages of cap-exempt H-1B orgs directly.
#
# Uses public ATS APIs (no login, no CAPTCHA):
#   Workday   — POST API, covers ~40+ orgs in one pattern
#   Greenhouse— GET API, covers ~15+ nonprofit/research orgs
#   HigherEdJobs RSS — covers hundreds of universities at once
#   Custom    — org-specific scrapers for Harvard, MIT, etc.
# =============================================================================

import time
import hashlib
import re
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime

from org_list import get_workday_orgs, get_greenhouse_orgs, get_custom_orgs
from config import JOB_TITLES

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

SEARCH_TERMS = [
    "program manager", "project manager", "operations manager",
    "program coordinator", "project coordinator", "operations analyst",
    "associate program manager", "associate project manager",
]

def make_id(url, title, company):
    return hashlib.md5(f"{url}{title}{company}".lower().encode()).hexdigest()

def clean(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', str(text))
    return re.sub(r'\s+', ' ', text).strip()

def job(title, company, location, description, url, source, cap_exempt=True, posted_date=""):
    return {
        "id":           make_id(url, title, company),
        "title":        clean(title),
        "company":      clean(company),
        "location":     clean(location),
        "description":  clean(description),
        "url":          url,
        "source":       source,
        "cap_exempt":   cap_exempt,   # Always True for direct org scrapes
        "posted_date":  posted_date or datetime.now().strftime("%Y-%m-%d"),
    }


# ─────────────────────────────────────────────────────────────
# WORKDAY SCRAPER
# ─────────────────────────────────────────────────────────────

def scrape_workday_org(org: dict, search_term: str) -> list:
    """
    Uses Workday's public job search API.
    Pattern: POST https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{career_site}/jobs
    """
    tenant = org["tenant"]
    site   = org.get("career_site", "External")
    url    = f"https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"

    payload = {
        "limit": 20,
        "offset": 0,
        "searchText": search_term,
        "appliedFacets": {}
    }

    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        data     = resp.json()
        postings = data.get("jobPostings", [])
        results  = []

        for p in postings:
            title    = p.get("title", "")
            ext_path = p.get("externalPath", "")
            job_url  = f"https://{tenant}.wd1.myworkdayjobs.com{ext_path}"
            posted   = p.get("postedOn", "")[:10] if p.get("postedOn") else ""

            # Location
            loc_data = p.get("locationsText", "") or p.get("location", {})
            if isinstance(loc_data, dict):
                location = loc_data.get("descriptor", "")
            else:
                location = str(loc_data)

            # Brief description from listing (full description needs another call)
            description = p.get("jobDescription", {})
            if isinstance(description, dict):
                description = description.get("descriptor", "")
            description = clean(description) or f"See full description at {job_url}"

            results.append(job(
                title=title,
                company=org["name"],
                location=location or "Massachusetts",
                description=description if len(description) > 30 else f"{org['name']} — {title}. See full job description at: {job_url}",
                url=job_url,
                source=f"Direct: {org['name']}",
                cap_exempt=True,
                posted_date=posted,
            ))
        return results

    except Exception as e:
        return []


def scrape_all_workday(max_orgs=None) -> list:
    """Scrape all Workday orgs in org_list.py."""
    orgs     = get_workday_orgs()
    if max_orgs:
        orgs = orgs[:max_orgs]

    all_jobs = []
    print(f"  Workday: scraping {len(orgs)} orgs × {len(SEARCH_TERMS)} terms...")

    for org in orgs:
        org_jobs = []
        for term in SEARCH_TERMS:
            results = scrape_workday_org(org, term)
            org_jobs.extend(results)
            time.sleep(1.0)   # Polite delay

        if org_jobs:
            print(f"    ✓ {org['name']}: {len(org_jobs)} listings")
        all_jobs.extend(org_jobs)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# GREENHOUSE SCRAPER
# ─────────────────────────────────────────────────────────────

def scrape_greenhouse_org(org: dict) -> list:
    """
    Uses Greenhouse's public jobs API.
    GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
    """
    token = org["tenant"]
    url   = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        jobs_data = resp.json().get("jobs", [])
        results   = []

        for j in jobs_data:
            title = j.get("title", "")

            # Filter to relevant titles only
            title_lower = title.lower()
            if not any(t.lower() in title_lower for t in [
                "program", "project", "operations", "coordinator",
                "manager", "analyst", "administrator"
            ]):
                continue

            location = j.get("location", {}).get("name", "")
            job_url  = j.get("absolute_url", "")
            content  = j.get("content", "")
            posted   = j.get("updated_at", "")[:10] if j.get("updated_at") else ""

            results.append(job(
                title=title,
                company=org["name"],
                location=location,
                description=clean(content)[:2000] if content else f"See full description at {job_url}",
                url=job_url,
                source=f"Direct: {org['name']}",
                cap_exempt=True,
                posted_date=posted,
            ))

        return results

    except Exception as e:
        return []


def scrape_all_greenhouse() -> list:
    orgs     = get_greenhouse_orgs()
    all_jobs = []
    print(f"  Greenhouse: scraping {len(orgs)} orgs...")

    for org in orgs:
        results = scrape_greenhouse_org(org)
        if results:
            print(f"    ✓ {org['name']}: {len(results)} listings")
        all_jobs.extend(results)
        time.sleep(1.5)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# HIGHEREDJOBS — covers hundreds of universities via one RSS
# ─────────────────────────────────────────────────────────────

HIGHEREDJOBS_RSS_URLS = [
    # Massachusetts — specific job titles only (avoids the firehose)
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+manager&Location=MA&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=project+manager&Location=MA&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+coordinator&Location=MA&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=operations+manager&Location=MA&MaxResults=25",
    # Remote higher ed — specific titles only
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+manager&Remote=1&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+coordinator&Remote=1&MaxResults=25",
]

def scrape_higheredjobs() -> list:
    all_jobs = []
    print(f"  HigherEdJobs: fetching {len(HIGHEREDJOBS_RSS_URLS)} RSS feeds...")

    for url in HIGHEREDJOBS_RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                # Extract company/institution from title or author
                title   = e.get("title", "")
                company = e.get("author", "")
                if " - " in title:
                    parts   = title.rsplit(" - ", 1)
                    title   = parts[0].strip()
                    company = parts[1].strip() if not company else company

                all_jobs.append(job(
                    title=title,
                    company=company or "Higher Education Institution",
                    location=e.get("tags",[{}])[0].get("term","") if e.get("tags") else "Massachusetts",
                    description=e.get("summary",""),
                    url=e.get("link",""),
                    source="HigherEdJobs",
                    cap_exempt=True,   # All HigherEdJobs listings are at universities
                    posted_date=e.get("published",""),
                ))
        except Exception as e:
            print(f"    ⚠️  HigherEdJobs RSS error: {e}")
        time.sleep(1.5)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# HARVARD CAREERS (custom scraper)
# ─────────────────────────────────────────────────────────────

def scrape_harvard() -> list:
    """Harvard uses BrassRing/Kenexa — query their public search API."""
    all_jobs = []
    base_url = "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad"

    for term in ["program manager", "project manager", "operations", "coordinator"]:
        try:
            search_url = (
                f"https://sjobs.brassring.com/TGnewUI/Search/Home/HomeWithPreLoad"
                f"?partnerid=25240&siteid=5341&PageType=JobSearch"
                f"&SearchTerms={term.replace(' ', '+')}"
            )
            resp = requests.get(search_url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=12)
            soup = BeautifulSoup(resp.text, "lxml")

            for row in soup.select(".jobProperty, .ng-scope"):
                title_el = row.select_one(".jobTitle, .job-title, h4")
                link_el  = row.select_one("a[href]")
                if title_el and link_el:
                    href = link_el.get("href","")
                    if not href.startswith("http"):
                        href = "https://sjobs.brassring.com" + href
                    all_jobs.append(job(
                        title=title_el.get_text(strip=True),
                        company="Harvard University",
                        location="Cambridge, MA",
                        description=f"Harvard University position. See full description at {href}",
                        url=href,
                        source="Direct: Harvard University",
                        cap_exempt=True,
                    ))
        except Exception:
            pass
        time.sleep(2)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# MIT CAREERS (custom — MIT has a public jobs JSON endpoint)
# ─────────────────────────────────────────────────────────────

def scrape_mit() -> list:
    """MIT careers uses a searchable public endpoint."""
    all_jobs = []
    for term in ["program manager", "project manager", "operations", "coordinator"]:
        try:
            url  = f"https://careers.mit.edu/search-jobs?keywords={term.replace(' ', '+')}&location=Cambridge%2C+Massachusetts"
            resp = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=12)
            soup = BeautifulSoup(resp.text, "lxml")

            for card in soup.select("li.search-results__item, .job-listing"):
                title_el = card.select_one("h2, h3, .job-title")
                link_el  = card.select_one("a[href]")
                loc_el   = card.select_one(".job-location, .location")
                if title_el and link_el:
                    href = link_el.get("href","")
                    if not href.startswith("http"):
                        href = "https://careers.mit.edu" + href
                    all_jobs.append(job(
                        title=title_el.get_text(strip=True),
                        company="MIT",
                        location=loc_el.get_text(strip=True) if loc_el else "Cambridge, MA",
                        description=f"MIT position. See full description at {href}",
                        url=href,
                        source="Direct: MIT",
                        cap_exempt=True,
                    ))
        except Exception:
            pass
        time.sleep(2)

    return all_jobs


# ─────────────────────────────────────────────────────────────
# MASTER ORG SCRAPER — calls everything
# ─────────────────────────────────────────────────────────────

def scrape_all_orgs() -> list:
    """
    Run all org scrapers and return deduplicated job list.
    All results are pre-flagged as cap_exempt=True.
    """
    print("\n🏛️  Scraping cap-exempt org career pages directly...")
    all_jobs = []

    print("\n  [A] Workday orgs (hospitals, universities, research)...")
    all_jobs += scrape_all_workday()

    print("\n  [B] Greenhouse orgs (nonprofits, research institutes)...")
    all_jobs += scrape_all_greenhouse()

    print("\n  [C] HigherEdJobs (university-wide RSS)...")
    all_jobs += scrape_higheredjobs()

    print("\n  [D] Harvard University (custom)...")
    all_jobs += scrape_harvard()

    print("\n  [E] MIT (custom)...")
    all_jobs += scrape_mit()

    # Deduplicate
    seen = set()
    unique = []
    for j in all_jobs:
        if j["id"] not in seen and j["url"]:
            seen.add(j["id"])
            unique.append(j)

    print(f"\n  🏛️  Org scraper: {len(all_jobs)} total → {len(unique)} unique cap-exempt listings")
    return unique
