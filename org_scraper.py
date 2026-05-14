# =============================================================================
# org_scraper.py — Direct scraping of cap-exempt org career pages
#
# Three scraping strategies:
#   1. Workday API   — POST /wday/cxs/{tenant}/{site}/jobs, parse JSON
#   2. Greenhouse    — GET /api/v1/boards/{token}/jobs.json
#   3. HTML scrape   — for orgs with custom job boards (Boston Children's)
#
# CRITICAL: Workday URLs must include the career_site in the path:
#   https://{tenant}.wd1.myworkdayjobs.com/{site}{externalPath}
# =============================================================================

import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from org_list import get_workday_orgs, get_greenhouse_orgs, get_custom_orgs

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept":     "application/json,text/html;q=0.9",
}

SEARCH_TERMS = [
    "program manager", "project manager", "operations manager",
    "program coordinator", "operations coordinator",
    "program associate", "project coordinator", "operations analyst",
]


def clean(text: str) -> str:
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def make_id(url, title, company):
    import hashlib
    raw = f"{url}|{title}|{company}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def job(title, company, location, description, url, source, cap_exempt=True, posted_date=""):
    return {
        "id":           make_id(url, title, company),
        "title":        title.strip(),
        "company":      company.strip(),
        "location":     location.strip() or "Massachusetts",
        "description":  clean(description),
        "url":          url,
        "source":       source,
        "cap_exempt":   cap_exempt,
        "posted_date":  posted_date or datetime.now().strftime("%Y-%m-%d"),
    }


# ═══════════════════════════════════════════════════════════════
# WORKDAY SCRAPER
# ═══════════════════════════════════════════════════════════════

# Workday subdomain prefixes — most orgs use wd1, but some use wd5, wd3, etc.
WORKDAY_SUBDOMAINS = ["wd1", "wd5", "wd3", "wd2"]

# Career site name variants to try if the specified one fails
SITE_VARIANTS = ["External", "ExternalCareerSite", "Careers", "careers"]


def scrape_workday_org(org: dict, search_term: str) -> list:
    """
    Workday public API: POST /wday/cxs/{tenant}/{site}/jobs
    Tries multiple subdomain (wd1, wd5...) and site variants.
    First combo that returns results gets cached on the org dict.
    """
    tenant = org["tenant"]

    # Build variant lists, preferring the configured values first
    subdomains = [org.get("datacenter", org.get("subdomain", "wd1"))]
    subdomains += [s for s in WORKDAY_SUBDOMAINS if s not in subdomains]

    sites = [org["career_site"]] + [s for s in SITE_VARIANTS if s != org["career_site"]]

    payload = {"limit": 20, "offset": 0,
               "searchText": search_term, "appliedFacets": {}}

    for sub in subdomains:
        for site in sites:
            api_url = f"https://{tenant}.{sub}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
            try:
                resp = requests.post(api_url, json=payload, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                postings = data.get("jobPostings", [])
                if not postings:
                    continue

                # Cache the working combination
                org["datacenter"]   = sub
                org["subdomain"]    = sub
                org["career_site"]  = site
                base_url            = f"https://{tenant}.{sub}.myworkdayjobs.com/en-US/{site}"

                results = []
                for p in postings:
                    title    = p.get("title", "")
                    ext_path = p.get("externalPath", "")
                    # Try to use externalUrl directly if Workday provides it
                    if p.get("externalUrl"):
                        job_url = p["externalUrl"]
                    else:
                        # Construct: workday job URLs include career site in path
                        # Format: https://{tenant}.{sub}.myworkdayjobs.com/{site}/job/...
                        job_url = f"https://{tenant}.{sub}.myworkdayjobs.com/{site}{ext_path}"
                    posted   = (p.get("postedOn", "") or "")[:10]

                    loc_data = p.get("locationsText", "") or p.get("location", {})
                    if isinstance(loc_data, dict):
                        location = loc_data.get("descriptor", "")
                    else:
                        location = str(loc_data)

                    desc = p.get("jobDescription", {})
                    if isinstance(desc, dict):
                        desc = desc.get("descriptor", "")
                    desc = clean(desc) or f"{org['name']} — {title}. Apply at {job_url}"

                    results.append(job(
                        title=title,
                        company=org["name"],
                        location=location or "Massachusetts",
                        description=desc,
                        url=job_url,
                        source=f"Direct: {org['name']}",
                        cap_exempt=True,
                        posted_date=posted,
                    ))
                return results

            except Exception:
                continue

    return []


def scrape_all_workday() -> list:
    """Scrape every Workday org × every search term."""
    print("  Workday orgs (universities, hospitals, research):")
    all_jobs   = []
    success    = []
    failed     = []
    orgs       = get_workday_orgs()

    for org in orgs:
        org_jobs = []
        # Try each search term, but stop searching if first 2 return empty
        # (means tenant config is wrong, no point hammering 8 terms)
        for i, term in enumerate(SEARCH_TERMS):
            results = scrape_workday_org(org, term)
            org_jobs.extend(results)
            time.sleep(0.8)
            if i == 1 and not org_jobs:
                break   # No results from first 2 terms — give up on this org

        if org_jobs:
            success.append(f"{org['name']} ({len(org_jobs)})")
            print(f"    ✓ {org['name']}: {len(org_jobs)} listings "
                  f"[{org.get('datacenter', org.get('subdomain','wd1'))}/{org['career_site']}]")
        else:
            failed.append(org["name"])
        all_jobs.extend(org_jobs)

    print(f"\n    Workday summary: {len(success)} succeeded, {len(failed)} failed")
    if failed:
        print(f"    Failed orgs (need URL verification): {', '.join(failed[:10])}")
        if len(failed) > 10:
            print(f"      ...and {len(failed)-10} more")

    return all_jobs


# ═══════════════════════════════════════════════════════════════
# GREENHOUSE SCRAPER
# ═══════════════════════════════════════════════════════════════

def scrape_greenhouse_org(org: dict) -> list:
    """Greenhouse public API: GET /api/v1/boards/{token}/jobs.json"""
    token = org["tenant"]
    url   = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        jobs_data = data.get("jobs", [])

        results = []
        for j in jobs_data:
            title = j.get("title", "")
            title_lower = title.lower()
            if not any(t in title_lower for t in [
                "program", "project", "operations", "coordinator",
                "manager", "analyst", "administrator"
            ]):
                continue

            location_obj = j.get("location", {})
            location = location_obj.get("name", "") if isinstance(location_obj, dict) else str(location_obj)
            job_url = j.get("absolute_url", "")
            body    = j.get("content", "")
            posted  = (j.get("updated_at", "") or "")[:10]

            results.append(job(
                title=title,
                company=org["name"],
                location=location or "Remote",
                description=clean(body),
                url=job_url,
                source=f"Direct: {org['name']}",
                cap_exempt=True,
                posted_date=posted,
            ))
        return results
    except Exception:
        return []


def scrape_all_greenhouse() -> list:
    print("\n  Greenhouse orgs:")
    all_jobs = []
    for org in get_greenhouse_orgs():
        results = scrape_greenhouse_org(org)
        if results:
            print(f"    ✓ {org['name']}: {len(results)} listings")
        all_jobs.extend(results)
        time.sleep(0.5)
    return all_jobs


# ═══════════════════════════════════════════════════════════════
# CUSTOM HTML SCRAPERS
# ═══════════════════════════════════════════════════════════════

def scrape_boston_childrens() -> list:
    """
    Boston Children's Hospital uses iCIMS via a custom URL.
    Searches their public job search page for relevant titles.
    """
    results = []
    base_url = "https://jobs.bostonchildrens.org/job-search-results/"
    search_terms = ["program manager", "project manager", "operations manager", "program coordinator"]

    for term in search_terms:
        url = f"{base_url}?keywords={term.replace(' ', '+')}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # Boston Children's job listings — try common selectors
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if "/job/" not in href.lower() and "/jobs/" not in href.lower():
                    continue
                if not title or len(title) < 10:
                    continue
                title_lower = title.lower()
                if not any(t in title_lower for t in ["manager", "coordinator", "analyst", "specialist", "administrator"]):
                    continue

                full_url = href if href.startswith("http") else f"https://jobs.bostonchildrens.org{href}"
                results.append(job(
                    title=title,
                    company="Boston Children's Hospital",
                    location="Boston, MA",
                    description=f"Boston Children's Hospital — {title}",
                    url=full_url,
                    source="Direct: Boston Children's Hospital",
                    cap_exempt=True,
                ))
            time.sleep(1)
        except Exception:
            continue

    # Dedupe by URL
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    if unique:
        print(f"    ✓ Boston Children's Hospital: {len(unique)} listings")
    return unique


def scrape_all_custom() -> list:
    print("\n  Custom HTML scrapers:")
    all_jobs = []
    all_jobs.extend(scrape_boston_childrens())
    return all_jobs


# ═══════════════════════════════════════════════════════════════
# HIGHEREDJOBS RSS
# ═══════════════════════════════════════════════════════════════

HIGHEREDJOBS_RSS_URLS = [
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+manager&Location=MA&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=project+manager&Location=MA&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+coordinator&Location=MA&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=operations+manager&Location=MA&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+manager&Remote=1&MaxResults=25",
    "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+coordinator&Remote=1&MaxResults=25",
]


def scrape_higheredjobs() -> list:
    print("\n  HigherEdJobs RSS feeds:")
    results = []
    for url in HIGHEREDJOBS_RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                results.append(job(
                    title=e.get("title", ""),
                    company=e.get("author", "Higher Ed Institution"),
                    location="Massachusetts",
                    description=e.get("summary", ""),
                    url=e.get("link", ""),
                    source="HigherEdJobs (cap-exempt)",
                    cap_exempt=True,
                    posted_date=e.get("published", "")[:10],
                ))
            time.sleep(0.5)
        except Exception:
            continue
    if results:
        print(f"    ✓ HigherEdJobs: {len(results)} listings across all feeds")
    return results


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def scrape_all_orgs() -> list:
    print("\n🏛️  Scraping cap-exempt org career pages directly...\n")
    all_jobs = []
    all_jobs.extend(scrape_all_workday())
    all_jobs.extend(scrape_all_greenhouse())
    all_jobs.extend(scrape_all_custom())
    all_jobs.extend(scrape_higheredjobs())

    # Deduplicate
    seen = set()
    unique = []
    for j in all_jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)

    print(f"\n  🏛️  Org scraper total: {len(all_jobs)} raw → {len(unique)} unique cap-exempt listings\n")
    return unique
