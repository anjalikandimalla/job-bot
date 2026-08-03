# =============================================================================
# sources_contract.py — Contract, temp and internship focused job sources
#
# Added for the 12-month-and-under pivot. Ordered by tier value:
#   Tier 1  HERC (higher ed consortium — universities, teaching hospitals,
#           research institutes, education nonprofits)
#   Tier 2  MassBio Career Center, BioSpace
#   Mixed   Yoh (Harvard's contingent workforce MSP), Actalent, Medix
#
# NOTE ON MAINTENANCE
# These are HTML scrapers, not APIs. Selectors drift. Every function is
# defensive: it returns [] on any failure rather than raising, and
# _extract_cards() tries several DOM shapes before giving up. If a source
# starts returning 0 listings for several runs, re-inspect the markup.
# =============================================================================

import hashlib
import re
import time
from datetime import datetime
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 12
POLITE_DELAY = 1.5   # seconds between requests to the same host


# ─────────────────────────────────────────────────────────────
# SEARCH TERMS
# ─────────────────────────────────────────────────────────────

CONTRACT_TERMS = [
    "program coordinator",
    "project coordinator",
    "research program coordinator",
    "grants coordinator",
    "program manager",
    "project manager",
    "operations coordinator",
    "special projects coordinator",
]

INTERNSHIP_TERMS = [
    "program management intern",
    "project management intern",
    "operations intern",
]

# Appended to keyword searches on boards that support free-text matching.
# These are the phrases that actually identify term-limited work.
CONTRACT_MODIFIERS = ["temporary", "contract", "term", "interim"]


# ─────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────

def make_id(url, title, company):
    return hashlib.md5(f"{url}{title}{company}".lower().encode()).hexdigest()


def clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(text))
    return re.sub(r"\s+", " ", text).strip()


def norm(title, company, location, description, url, source, posted_date=""):
    return {
        "id":          make_id(url, title, company),
        "title":       clean(title),
        "company":     clean(company),
        "location":    clean(location),
        "description": clean(description),
        "url":         url,
        "source":      source,
        "cap_exempt":  False,
        "posted_date": posted_date or datetime.now().strftime("%Y-%m-%d"),
    }


def _get(url, params=None):
    """GET with a shared UA. Returns soup or None. Never raises."""
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, "lxml")
    except Exception:
        return None


def _extract_cards(soup, link_pattern):
    """
    Generic job-card extractor. Finds anchors whose href matches link_pattern
    and walks up to the nearest container for surrounding text.

    Returns a list of (title, href, container_text) tuples.
    """
    if not soup:
        return []

    rx = re.compile(link_pattern, re.IGNORECASE)
    out, seen = [], set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not rx.search(href):
            continue
        title = clean(a.get_text())
        if not title or len(title) < 4:
            continue
        if href in seen:
            continue
        seen.add(href)

        # Walk up a few levels to capture company/location/snippet text.
        container = a
        for _ in range(4):
            if container.parent is None:
                break
            container = container.parent
            if len(container.get_text(strip=True)) > 120:
                break

        out.append((title, href, clean(container.get_text(separator=" "))))

    return out


def _guess_company(card_text, title, fallback):
    """Pull a company name out of card text when the board does not label it."""
    txt = card_text.replace(title, " ", 1).strip(" -|•·\u2013\u2014")
    m = re.match(r"([A-Z][A-Za-z&.,'\- ]{3,60}?)(?:\s{2,}|\s[-|•·]\s|,\s)", txt)
    if m:
        return m.group(1).strip()
    return fallback


# ─────────────────────────────────────────────────────────────
# 1. HERC — Higher Education Recruitment Consortium  (TIER 1)
#
# The public site at hercjobs.org is marketing; the job board runs at
# main.hercjobs.org/jobs. It supports free-text keywords plus an
# employer:"Name" syntax, and covers universities, teaching hospitals,
# research institutes and education nonprofits nationwide.
# ─────────────────────────────────────────────────────────────

HERC_BASE = "https://main.hercjobs.org"


def scrape_herc() -> list:
    jobs = []
    searches = []

    for term in CONTRACT_TERMS[:6]:
        for modifier in ("temporary", "term"):
            searches.append(f"{term} {modifier}")
    for term in INTERNSHIP_TERMS:
        searches.append(term)

    for kw in searches:
        soup = _get(f"{HERC_BASE}/jobs", params={"keywords": kw})
        for title, href, card_text in _extract_cards(soup, r"/jobs/\d+"):
            url = urljoin(HERC_BASE, href)
            company = _guess_company(card_text, title, "HERC member institution")
            loc_match = re.search(
                r"\b([A-Z][a-zA-Z .'\-]+,\s*[A-Z]{2})\b", card_text)
            location = loc_match.group(1) if loc_match else "United States"
            jobs.append(norm(
                title=title, company=company, location=location,
                description=card_text, url=url, source="HERC (Higher Ed)",
            ))
        time.sleep(POLITE_DELAY)

    return jobs


# ─────────────────────────────────────────────────────────────
# 2. MASSBIO CAREER CENTER  (TIER 2)
# Life-sciences-only board for the Massachusetts cluster.
# ─────────────────────────────────────────────────────────────

MASSBIO_BASE = "https://careers.massbio.org"


def scrape_massbio() -> list:
    jobs = []
    searches = [
        "clinical trial coordinator", "study start-up", "program coordinator",
        "project coordinator", "clinical operations coordinator",
        "alliance management", "R&D operations", "medical affairs coordinator",
        "program management intern",
    ]

    for kw in searches:
        soup = _get(f"{MASSBIO_BASE}/jobs/", params={"keywords": kw})
        for title, href, card_text in _extract_cards(soup, r"/job[s]?/\d+|/jobs/[a-z0-9\-]{8,}"):
            url = urljoin(MASSBIO_BASE, href)
            company = _guess_company(card_text, title, "MassBio member")
            loc_match = re.search(r"\b([A-Z][a-zA-Z .'\-]+,\s*[A-Z]{2})\b", card_text)
            jobs.append(norm(
                title=title, company=company,
                location=loc_match.group(1) if loc_match else "Massachusetts",
                description=card_text, url=url, source="MassBio Career Center",
            ))
        time.sleep(POLITE_DELAY)

    return jobs


# ─────────────────────────────────────────────────────────────
# 3. BIOSPACE  (TIER 2, secondary)
# ─────────────────────────────────────────────────────────────

BIOSPACE_BASE = "https://jobs.biospace.com"


def scrape_biospace() -> list:
    jobs = []
    searches = [
        "clinical project coordinator", "clinical trial coordinator",
        "program coordinator", "clinical operations", "study coordinator contract",
    ]

    for kw in searches:
        soup = _get(f"{BIOSPACE_BASE}/jobs/",
                    params={"keywords": kw, "location": "Massachusetts"})
        for title, href, card_text in _extract_cards(soup, r"/job/[a-z0-9\-]+"):
            url = urljoin(BIOSPACE_BASE, href)
            company = _guess_company(card_text, title, "BioSpace employer")
            loc_match = re.search(r"\b([A-Z][a-zA-Z .'\-]+,\s*[A-Z]{2})\b", card_text)
            jobs.append(norm(
                title=title, company=company,
                location=loc_match.group(1) if loc_match else "Massachusetts",
                description=card_text, url=url, source="BioSpace",
            ))
        time.sleep(POLITE_DELAY)

    return jobs


# ─────────────────────────────────────────────────────────────
# 4. YOH  (MIXED TIER — Harvard's contingent workforce MSP)
#
# Harvard routes contingent hiring through Yoh, and does not post payrolled
# temp roles on careers.harvard.edu. Harvard-adjacent contract work therefore
# surfaces here rather than on the university career site.
# ─────────────────────────────────────────────────────────────

YOH_BASE = "https://jobs.yoh.com"


def scrape_yoh() -> list:
    jobs = []
    searches = [
        "program coordinator", "project coordinator", "program manager",
        "project manager", "operations coordinator", "research coordinator",
    ]

    for kw in searches:
        soup = _get(f"{YOH_BASE}/jobs",
                    params={"keyword": kw, "location": "Massachusetts"})
        for title, href, card_text in _extract_cards(soup, r"/jobs?/\d+|/job/[a-z0-9\-]+"):
            url = urljoin(YOH_BASE, href)
            loc_match = re.search(r"\b([A-Z][a-zA-Z .'\-]+,\s*[A-Z]{2})\b", card_text)
            jobs.append(norm(
                title=title, company="Yoh (staffing — client not named)",
                location=loc_match.group(1) if loc_match else "Massachusetts",
                description=card_text, url=url, source="Yoh (contract)",
            ))
        time.sleep(POLITE_DELAY)

    return jobs


# ─────────────────────────────────────────────────────────────
# 5. ACTALENT  (TIER 2 — high contract volume, durations usually stated)
# ─────────────────────────────────────────────────────────────

ACTALENT_BASE = "https://careers.actalentservices.com"


def scrape_actalent() -> list:
    jobs = []
    searches = ["clinical research coordinator", "clinical project coordinator",
                "program coordinator", "project coordinator"]

    for kw in searches:
        soup = _get(f"{ACTALENT_BASE}/us/en/search-results",
                    params={"keywords": kw, "location": "Massachusetts"})
        for title, href, card_text in _extract_cards(soup, r"/us/en/job/[A-Z0-9]+"):
            url = urljoin(ACTALENT_BASE, href)
            loc_match = re.search(r"\b([A-Z][a-zA-Z .'\-]+,\s*[A-Z]{2})\b", card_text)
            jobs.append(norm(
                title=title, company="Actalent (staffing — client not named)",
                location=loc_match.group(1) if loc_match else "Massachusetts",
                description=card_text, url=url, source="Actalent (contract)",
            ))
        time.sleep(POLITE_DELAY)

    return jobs


# ─────────────────────────────────────────────────────────────
# 6. MEDIX  (TIER 2 — life sciences desk)
# ─────────────────────────────────────────────────────────────

MEDIX_BASE = "https://www.medixteam.com"


def scrape_medix() -> list:
    jobs = []
    searches = ["clinical research coordinator", "clinical project coordinator",
                "program coordinator"]

    for kw in searches:
        soup = _get(f"{MEDIX_BASE}/jobs/",
                    params={"keywords": kw, "location": "Massachusetts"})
        for title, href, card_text in _extract_cards(soup, r"/job[s]?/[a-z0-9\-]{6,}"):
            url = urljoin(MEDIX_BASE, href)
            loc_match = re.search(r"\b([A-Z][a-zA-Z .'\-]+,\s*[A-Z]{2})\b", card_text)
            jobs.append(norm(
                title=title, company="Medix (staffing — client not named)",
                location=loc_match.group(1) if loc_match else "Massachusetts",
                description=card_text, url=url, source="Medix (contract)",
            ))
        time.sleep(POLITE_DELAY)

    return jobs


# ─────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────

CONTRACT_SOURCES = [
    ("HERC (Higher Ed)",      scrape_herc),
    ("MassBio Career Center", scrape_massbio),
    ("BioSpace",              scrape_biospace),
    ("Yoh (contract)",        scrape_yoh),
    ("Actalent (contract)",   scrape_actalent),
    ("Medix (contract)",      scrape_medix),
]


def scrape_all_contract_sources() -> list:
    print("\n📋 Scraping contract & internship sources...")
    all_jobs = []

    for idx, (name, fn) in enumerate(CONTRACT_SOURCES, start=1):
        print(f"  [{idx}/{len(CONTRACT_SOURCES)}] {name}...")
        try:
            results = fn()
            print(f"    → {len(results)} listings")
            all_jobs.extend(results)
        except Exception as e:
            print(f"    ⚠️  {name} failed: {e}")

    seen, unique = set(), []
    for j in all_jobs:
        if j["id"] not in seen and j["url"]:
            seen.add(j["id"])
            unique.append(j)

    print(f"\n✅ Contract sources: {len(all_jobs)} total → {len(unique)} unique")
    return unique
