# =============================================================================
# scraper.py — General job board scrapers (non-org-specific)
#
# Boards:
#   1.  Indeed             (RSS)
#   2.  LinkedIn           (public API)
#   3.  Built In Boston    (RSS)
#   4.  Idealist           (RSS — nonprofits)
#   5.  ImpactOpportunity  (scrape — mission-driven roles)
#   6.  TechJobsForGood    (scrape)
#   7.  80000hours         (scrape — high-impact orgs)
#   8.  HigherEdJobs       (RSS — handled in org_scraper.py too, but general search here)
#   9.  Kforce             (staffing — great for contracts)
#  10.  Robert Half        (staffing — great for contracts)
#  11.  JOHNLEONARD        (Boston staffing)
#  12.  Beacon Hill        (Boston staffing)
# =============================================================================

import hashlib, time, re, feedparser, requests
from datetime import datetime
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SEARCH_TERMS_SHORT = [
    "program+manager", "project+manager", "operations+manager",
    "program+coordinator", "project+coordinator", "operations+analyst",
]

def make_id(url, title, company):
    return hashlib.md5(f"{url}{title}{company}".lower().encode()).hexdigest()

def clean(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', str(text))
    return re.sub(r'\s+', ' ', text).strip()

def norm(title, company, location, description, url, source, posted_date=""):
    return {
        "id":          make_id(url, title, company),
        "title":       clean(title),
        "company":     clean(company),
        "location":    clean(location),
        "description": clean(description),
        "url":         url,
        "source":      source,
        "cap_exempt":  False,   # General boards — cap-exempt determined by scorer
        "posted_date": posted_date or datetime.now().strftime("%Y-%m-%d"),
    }

def rss(url, source):
    try:
        return feedparser.parse(url).entries
    except:
        return []


# ─────────────────────────────────────────────────────────────
# 1. INDEED
# ─────────────────────────────────────────────────────────────
def scrape_indeed():
    """Indeed RSS — uses working feed format with location code"""
    jobs = []
    searches = [
        ("program+manager",    "Boston,+MA"),
        ("project+manager",    "Boston,+MA"),
        ("operations+manager", "Boston,+MA"),
        ("program+coordinator","Boston,+MA"),
        ("program+manager",    "remote"),
        ("project+manager",    "remote"),
    ]
    for term, loc in searches:
        url = f"https://www.indeed.com/rss?q={term}&l={loc}&sort=date&fromage=3"
        entries = rss(url, "Indeed")
        for e in entries:
            title = e.get("title", "")
            company = e.get("author", "")
            if not company:
                company = getattr(getattr(e, "source", None), "title", "")
            jobs.append(norm(title, company, loc.replace("+"," "),
                            e.get("summary",""), e.get("link",""), "Indeed",
                            e.get("published","")))
        time.sleep(2)
    return jobs


# ─────────────────────────────────────────────────────────────
# 2. LINKEDIN
# ─────────────────────────────────────────────────────────────
def scrape_linkedin():
    jobs = []
    searches = [
        ("program+manager",         "Boston%2C+Massachusetts"),
        ("project+manager",         "Boston%2C+Massachusetts"),
        ("operations+manager",      "Boston%2C+Massachusetts"),
        ("program+coordinator",     "Boston%2C+Massachusetts"),
        ("operations+analyst",      "Boston%2C+Massachusetts"),
        ("associate+program+manager","United+States"),
        ("program+manager",         "United+States"),
    ]
    for kw, loc in searches:
        try:
            resp = requests.get(
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={kw}&location={loc}&f_TPR=r86400&start=0",
                headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.find_all("li")[:15]:
                t = card.find("h3"); c = card.find("h4"); a = card.find("a")
                if t and a:
                    href = a.get("href","").split("?")[0]
                    jobs.append(norm(t.get_text(strip=True), c.get_text(strip=True) if c else "",
                                     loc.replace("+"," ").replace("%2C",","), "", href, "LinkedIn"))
        except Exception as e:
            print(f"    ⚠️  LinkedIn: {e}")
        time.sleep(3)
    return jobs


# ─────────────────────────────────────────────────────────────
# 3. BUILT IN BOSTON
# ─────────────────────────────────────────────────────────────
def scrape_builtin():
    """Built In Boston — scrape their job search API"""
    jobs = []
    search_terms = ["program manager", "project manager", "operations manager", "program coordinator"]
    for term in search_terms:
        try:
            resp = requests.get(
                f"https://www.builtinboston.com/jobs?search={term.replace(' ', '+')}",
                headers=HEADERS, timeout=12)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select("[data-id], .jobs-list__item, article.job-card"):
                t = card.select_one("h2, h3, [class*='title']")
                c = card.select_one("[class*='company']")
                a = card.select_one("a[href]")
                d = card.select_one("[class*='description'], p")
                if t and a:
                    href = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://www.builtinboston.com" + href
                    jobs.append(norm(t.get_text(strip=True),
                                     c.get_text(strip=True) if c else "",
                                     "Boston, MA",
                                     d.get_text(strip=True) if d else "",
                                     href, "Built In Boston"))
        except Exception as e:
            print(f"    ⚠️  Built In Boston: {e}")
        time.sleep(2)
    return jobs


# ─────────────────────────────────────────────────────────────
# 4. IDEALIST (nonprofits — many are cap-exempt)
# ─────────────────────────────────────────────────────────────
def scrape_idealist():
    """Idealist — nonprofits, many are cap-exempt"""
    jobs = []
    for term in ["program+manager", "project+manager", "operations+manager", "program+coordinator"]:
        # Try both RSS and JSON API
        try:
            resp = requests.get(
                f"https://www.idealist.org/en/jobs?q={term}&loc=Boston+MA",
                headers=HEADERS, timeout=12)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select("[data-cy=idealist-card], article, .sc-1lfxrbt"):
                t = card.select_one("h2, h3, [class*=title]")
                c = card.select_one("[class*=org], [class*=company]")
                a = card.select_one("a[href]")
                if t and a:
                    href = a.get("href", "")
                    if not href.startswith("http"):
                        href = "https://www.idealist.org" + href
                    jobs.append(norm(t.get_text(strip=True),
                                     c.get_text(strip=True) if c else "",
                                     "Boston, MA", "", href, "Idealist"))
        except Exception as e:
            print(f"    ⚠️  Idealist: {e}")
        time.sleep(2)
    return jobs


def scrape_impactopportunity():
    """Mission-driven nonprofit jobs — search LinkedIn with nonprofit filter"""
    jobs = []
    # LinkedIn search for nonprofit/mission-driven orgs
    nonprofit_searches = [
        ("program+manager", "Boston%2C+Massachusetts", "nonprofit"),
        ("operations+manager", "Boston%2C+Massachusetts", "nonprofit"),
        ("program+coordinator", "Boston%2C+Massachusetts", "nonprofit"),
    ]
    for kw, loc, _ in nonprofit_searches:
        try:
            resp = requests.get(
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={kw}&location={loc}&f_I=1&f_TPR=r86400&start=0",
                # f_I=1 is Nonprofit industry filter on LinkedIn
                headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.find_all("li")[:10]:
                t = card.find("h3"); c = card.find("h4"); a = card.find("a")
                if t and a:
                    href = a.get("href", "").split("?")[0]
                    jobs.append(norm(t.get_text(strip=True),
                                     c.get_text(strip=True) if c else "",
                                     "Boston, MA", "", href, "LinkedIn (Nonprofit)"))
        except Exception as e:
            print(f"    ⚠️  Nonprofit search: {e}")
        time.sleep(3)
    return jobs


def scrape_techjobsforgood():
    """Tech for good / social impact jobs via LinkedIn"""
    jobs = []
    try:
        resp = requests.get(
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            "?keywords=program+manager&location=Boston%2C+Massachusetts&f_I=94&f_TPR=r86400",
            # f_I=94 is E-Learning / Education industry
            headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.find_all("li")[:10]:
            t = card.find("h3"); c = card.find("h4"); a = card.find("a")
            if t and a:
                href = a.get("href", "").split("?")[0]
                jobs.append(norm(t.get_text(strip=True),
                                 c.get_text(strip=True) if c else "",
                                 "Boston, MA", "", href, "LinkedIn (Education)"))
    except Exception as e:
        print(f"    ⚠️  TechJobsForGood: {e}")
    return jobs


def scrape_80khours():
    """High-impact careers — research/policy orgs, usually cap-exempt"""
    jobs = []
    try:
        # 80k Hours posts their own job board as JSON
        resp = requests.get(
            "https://jobs.80000hours.org/api/jobs?search=program+manager&location=Boston",
            headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            try:
                for j in resp.json().get("jobs", [])[:15]:
                    title = j.get("title", "")
                    org   = j.get("organization", {}).get("name", "")
                    url   = j.get("url", "")
                    loc   = j.get("location", "Remote")
                    desc  = j.get("description", "")[:300]
                    jobs.append(norm(title, org, loc, desc, url, "80,000 Hours"))
            except Exception:
                pass
    except Exception as e:
        print(f"    ⚠️  80k Hours: {e}")
    return jobs


def scrape_higheredjobs_general():
    """HigherEdJobs — filter to admin/operations/coordinator roles only."""
    jobs = []
    # Targeted keyword searches — not broad category feeds
    search_terms = [
        "program+manager",
        "project+manager",
        "operations+manager",
        "program+coordinator",
        "project+coordinator",
        "operations+coordinator",
        "grants+manager",
        "research+program+manager",
    ]
    for term in search_terms:
        entries = rss(
            f"https://www.higheredjobs.com/rss/articleRSS.cfm?PosType=1&InstType=1"
            f"&JobCat=101&Keyword={term}&Region=7",   # Region 7 = New England
            "HigherEdJobs"
        )
        for e in entries:
            jobs.append(norm(
                e.get("title",""),
                e.get("author",""),
                "New England",
                e.get("summary",""),
                e.get("link",""),
                "HigherEdJobs",
                e.get("published","")
            ))
        time.sleep(1)
    return jobs


def scrape_linkedin_contracts():
    """
    Dedicated LinkedIn search for CONTRACT roles — searches specifically
    for contract job type (f_JT=C). This catches staffing agency listings
    that the broken HTML scrapers miss.
    """
    jobs = []
    contract_searches = [
        ("program+manager",      "Boston%2C+Massachusetts"),
        ("project+manager",      "Boston%2C+Massachusetts"),
        ("operations+manager",   "Boston%2C+Massachusetts"),
        ("program+coordinator",  "Boston%2C+Massachusetts"),
        ("operations+analyst",   "Boston%2C+Massachusetts"),
        ("program+manager",      "United+States"),   # Remote contracts
        ("project+manager",      "United+States"),
    ]
    for kw, loc in contract_searches:
        try:
            # f_JT=C = Contract job type filter
            resp = requests.get(
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={kw}&location={loc}&f_JT=C&f_TPR=r86400&start=0",
                headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.find_all("li")[:15]:
                t = card.find("h3")
                c = card.find("h4")
                a = card.find("a")
                if t and a:
                    href = a.get("href","").split("?")[0]
                    jobs.append(norm(
                        t.get_text(strip=True),
                        c.get_text(strip=True) if c else "",
                        loc.replace("+"," ").replace("%2C",","),
                        "", href, "LinkedIn (Contract)"))
        except Exception as e:
            print(f"    ⚠️  LinkedIn Contracts: {e}")
        time.sleep(3)
    return jobs


def scrape_kforce():
    """Kforce — uses LinkedIn feed since their site is JS-rendered"""
    jobs = []
    try:
        resp = requests.get(
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            "?keywords=program+manager&location=Boston%2C+Massachusetts"
            "&f_C=1815&f_TPR=r86400&start=0",   # f_C=1815 = Kforce company filter
            headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.find_all("li")[:10]:
            t = card.find("h3"); a = card.find("a")
            if t and a:
                href = a.get("href","").split("?")[0]
                jobs.append(norm(t.get_text(strip=True), "Kforce", "Boston, MA",
                                 "", href, "Kforce"))
    except Exception as e:
        print(f"    ⚠️  Kforce: {e}")
    return jobs


def scrape_roberthalf():
    """Robert Half — JSON API (more reliable than scraping HTML)"""
    jobs = []
    for term in ["program manager", "project manager", "operations manager", "project coordinator"]:
        try:
            url = (f"https://www.roberthalf.com/us/en/jobs/api/jobs"
                   f"?keyword={term.replace(' ', '+')}&location=Boston%2C+MA"
                   f"&distance=25&pageNumber=1&pageSize=10")
            resp = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=15)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    listings = data.get("results", data.get("jobs", []))
                    for j in listings[:10]:
                        title = j.get("title", j.get("jobTitle", ""))
                        company = "Robert Half"
                        location = j.get("city", "Boston") + ", " + j.get("state", "MA")
                        link = j.get("canonicalUrl", j.get("url", ""))
                        if not link.startswith("http"):
                            link = "https://www.roberthalf.com" + link
                        description = j.get("description", j.get("summary", ""))[:500]
                        jobs.append(norm(title, company, location, description, link, "Robert Half"))
                except Exception:
                    pass
        except Exception as e:
            print(f"    ⚠️  Robert Half: {e}")
        time.sleep(2)
    return jobs


def scrape_johnleonard():
    """JOHNLEONARD — Boston staffing firm, HTML scraper"""
    jobs = []
    for term in ["program+manager", "project+manager", "operations", "coordinator"]:
        try:
            url  = f"https://www.johnleonard.com/find-a-job/?s={term}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job-listing, .job, article, .views-row"):
                t = card.select_one("h2, h3, .title, a")
                a = card.select_one("a[href]")
                l = card.select_one(".location, .city")
                d = card.select_one("p, .description")
                if t and a:
                    href = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://www.johnleonard.com" + href
                    jobs.append(norm(t.get_text(strip=True), "JOHNLEONARD (Staffing)",
                                     l.get_text(strip=True) if l else "Boston, MA",
                                     d.get_text(strip=True) if d else "", href, "JOHNLEONARD"))
        except Exception as e:
            print(f"    ⚠️  JOHNLEONARD: {e}")
        time.sleep(2)
    return jobs


def scrape_beaconhill():
    """Beacon Hill — Boston staffing, HTML scraper"""
    jobs = []
    for term in ["program+manager", "project+manager", "operations", "coordinator"]:
        try:
            url  = f"https://www.beaconhillstaffing.com/jobs?search={term}&location=Boston"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job, .job-card, article, .position, .views-row"):
                t = card.select_one("h2, h3, .title, .job-title, a")
                a = card.select_one("a[href]")
                l = card.select_one(".location, .city, .place")
                d = card.select_one("p, .desc, .summary")
                if t and a:
                    href = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://www.beaconhillstaffing.com" + href
                    jobs.append(norm(t.get_text(strip=True), "Beacon Hill Staffing",
                                     l.get_text(strip=True) if l else "Boston, MA",
                                     d.get_text(strip=True) if d else "", href, "Beacon Hill"))
        except Exception as e:
            print(f"    ⚠️  Beacon Hill: {e}")
        time.sleep(2)
    return jobs



# ─────────────────────────────────────────────────────────────
# MASTER GENERAL SCRAPER
# ─────────────────────────────────────────────────────────────

def scrape_all_sources() -> list:
    print("\n📡 Scraping general job boards...")
    all_jobs = []

    scrapers = [
        ("Indeed",              scrape_indeed),
        ("LinkedIn",            scrape_linkedin),
        ("LinkedIn (Contract)", scrape_linkedin_contracts),
        ("Built In Boston",     scrape_builtin),
        ("Idealist",            scrape_idealist),
        ("ImpactOpportunity",   scrape_impactopportunity),
        ("TechJobsForGood",     scrape_techjobsforgood),
        ("80000hours",          scrape_80khours),
        ("HigherEdJobs",        scrape_higheredjobs_general),
        ("Kforce",              scrape_kforce),
        ("Robert Half",         scrape_roberthalf),
        ("JOHNLEONARD",         scrape_johnleonard),
        ("Beacon Hill",         scrape_beaconhill),
    ]

    for name, fn in scrapers:
        print(f"  [{scrapers.index((name,fn))+1}/{len(scrapers)}] {name}...")
        try:
            results = fn()
            print(f"    → {len(results)} listings")
            all_jobs.extend(results)
        except Exception as e:
            print(f"    ⚠️  {name} failed: {e}")

    # Deduplicate
    seen, unique = set(), []
    for j in all_jobs:
        if j["id"] not in seen and j["url"]:
            seen.add(j["id"])
            unique.append(j)

    print(f"\n✅ General boards: {len(all_jobs)} total → {len(unique)} unique")
    return unique
