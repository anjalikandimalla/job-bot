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
    jobs = []
    for term in SEARCH_TERMS_SHORT:
        for loc in ["Boston+MA", "remote"]:
            entries = rss(f"https://www.indeed.com/rss?q={term}&l={loc}&sort=date&fromage=1", "Indeed")
            for e in entries:
                company = getattr(getattr(e, 'source', None), 'title', '')
                desc = e.get("summary","")
                jobs.append(norm(e.get("title",""), company, loc.replace("+"," "), desc, e.get("link",""), "Indeed", e.get("published","")))
            time.sleep(1.5)
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
    jobs = []
    for term in ["program+manager","project+manager","operations","coordinator"]:
        entries = rss(f"https://www.builtinboston.com/jobs/feed?search[keywords]={term}&search[job_types][]=full_time", "Built In Boston")
        for e in entries:
            jobs.append(norm(e.get("title",""), e.get("author",""), "Boston, MA",
                             e.get("summary",""), e.get("link",""), "Built In Boston", e.get("published","")))
        time.sleep(1.5)
    return jobs


# ─────────────────────────────────────────────────────────────
# 4. IDEALIST (nonprofits — many are cap-exempt)
# ─────────────────────────────────────────────────────────────
def scrape_idealist():
    jobs = []
    for term in ["program+manager","project+manager","operations","coordinator"]:
        entries = rss(f"https://www.idealist.org/en/jobs/rss?q={term}&loc=Boston+MA&type=JOB", "Idealist")
        for e in entries:
            loc = e["tags"][0].get("term","Boston, MA") if e.get("tags") else "Boston, MA"
            jobs.append(norm(e.get("title",""), e.get("author",""), loc,
                             e.get("summary",""), e.get("link",""), "Idealist", e.get("published","")))
        time.sleep(1.5)
    return jobs


# ─────────────────────────────────────────────────────────────
# 5. IMPACT OPPORTUNITY (mission-driven, many cap-exempt orgs)
# ─────────────────────────────────────────────────────────────
def scrape_impactopportunity():
    jobs = []
    search_terms = ["program manager", "project manager", "operations", "coordinator"]
    for term in search_terms:
        try:
            url  = f"https://impactopportunity.org/jobs/?search={term.replace(' ','+')}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job-listing, .job-card, article.type-job"):
                t = card.select_one("h2, h3, .job-title")
                a = card.select_one("a[href]")
                c = card.select_one(".company, .organization, .employer")
                l = card.select_one(".location")
                if t and a:
                    href = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://impactopportunity.org" + href
                    jobs.append(norm(
                        t.get_text(strip=True),
                        c.get_text(strip=True) if c else "",
                        l.get_text(strip=True) if l else "",
                        "", href, "ImpactOpportunity"
                    ))
        except Exception as e:
            print(f"    ⚠️  ImpactOpportunity: {e}")
        time.sleep(2)
    return jobs


# ─────────────────────────────────────────────────────────────
# 6. TECH JOBS FOR GOOD
# ─────────────────────────────────────────────────────────────
def scrape_techjobsforgood():
    jobs = []
    try:
        for term in ["program-manager", "project-manager", "operations"]:
            url  = f"https://techjobsforgood.com/jobs/?q={term}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job, .job-post, .job-listing, article"):
                t = card.select_one("h2, h3, .title")
                a = card.select_one("a[href]")
                c = card.select_one(".company, .org")
                if t and a:
                    href = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://techjobsforgood.com" + href
                    jobs.append(norm(t.get_text(strip=True), c.get_text(strip=True) if c else "",
                                     "Various", "", href, "TechJobsForGood"))
            time.sleep(2)
    except Exception as e:
        print(f"    ⚠️  TechJobsForGood: {e}")
    return jobs


# ─────────────────────────────────────────────────────────────
# 7. 80000 HOURS (high-impact org jobs, many cap-exempt)
# ─────────────────────────────────────────────────────────────
def scrape_80000hours():
    jobs = []
    try:
        url  = "https://jobs.80000hours.org/?refinementList%5Btags_area%5D%5B0%5D=Operations&refinementList%5Btags_area%5D%5B1%5D=Project+management"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.select(".job, .chakra-stack, article, [class*='job']"):
            t = card.select_one("h2, h3, h4, [class*='title']")
            a = card.select_one("a[href]")
            c = card.select_one("[class*='company'], [class*='org']")
            if t and a and len(t.get_text(strip=True)) > 3:
                href = a.get("href","")
                if not href.startswith("http"):
                    href = "https://jobs.80000hours.org" + href
                jobs.append(norm(t.get_text(strip=True), c.get_text(strip=True) if c else "",
                                 "Remote / Various", "", href, "80000hours"))
    except Exception as e:
        print(f"    ⚠️  80000hours: {e}")
    return jobs


# ─────────────────────────────────────────────────────────────
# 8. HIGHEREDJOBS (general search — org_scraper also has targeted version)
# ─────────────────────────────────────────────────────────────
def scrape_higheredjobs_general():
    jobs = []
    urls = [
        "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=program+manager",
        "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=operations+manager",
        "https://www.higheredjobs.com/rss/articleFeed.cfm?feedType=2&JobCatNos=7&Keyword=project+coordinator",
    ]
    for url in urls:
        entries = rss(url, "HigherEdJobs")
        for e in entries:
            title = e.get("title","")
            company = e.get("author","")
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, company = parts[0].strip(), parts[1].strip()
            jobs.append(norm(title, company or "Higher Ed Institution", "Massachusetts",
                             e.get("summary",""), e.get("link",""), "HigherEdJobs", e.get("published","")))
        time.sleep(1.5)
    return jobs


# ─────────────────────────────────────────────────────────────
# 9. KFORCE (staffing — excellent for contract roles)
# ─────────────────────────────────────────────────────────────
def scrape_kforce():
    jobs = []
    for term in ["program+manager", "project+manager", "operations+manager", "project+coordinator"]:
        try:
            url  = f"https://www.kforce.com/job-search/?skill={term}&location=Boston%2C+MA&radius=25"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job-card, .search-result, article.job"):
                t = card.select_one("h2, h3, .job-title")
                a = card.select_one("a[href]")
                l = card.select_one(".location")
                d = card.select_one(".description, .summary")
                if t and a:
                    href = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://www.kforce.com" + href
                    jobs.append(norm(t.get_text(strip=True), "Kforce (Staffing)",
                                     l.get_text(strip=True) if l else "Boston, MA",
                                     d.get_text(strip=True) if d else "", href, "Kforce"))
        except Exception as e:
            print(f"    ⚠️  Kforce: {e}")
        time.sleep(2)
    return jobs


# ─────────────────────────────────────────────────────────────
# 10. ROBERT HALF (staffing — contracts + perm)
# ─────────────────────────────────────────────────────────────
def scrape_roberthalf():
    jobs = []
    for term in ["program manager", "project manager", "operations manager", "project coordinator"]:
        try:
            url  = f"https://www.roberthalf.com/us/en/jobs/all-jobs?keywords={term.replace(' ','+')}&location=Boston+MA"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select("[class*='job-card'], [class*='search-result']"):
                t = card.select_one("h2, h3, [class*='title']")
                a = card.select_one("a[href]")
                l = card.select_one("[class*='location']")
                d = card.select_one("[class*='description'], [class*='summary']")
                if t and a:
                    href = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://www.roberthalf.com" + href
                    jobs.append(norm(t.get_text(strip=True), "Robert Half (Staffing)",
                                     l.get_text(strip=True) if l else "Boston, MA",
                                     d.get_text(strip=True) if d else "", href, "Robert Half"))
        except Exception as e:
            print(f"    ⚠️  Robert Half: {e}")
        time.sleep(2)
    return jobs


# ─────────────────────────────────────────────────────────────
# 11. JOHNLEONARD (Boston staffing — contracts + direct hire)
# ─────────────────────────────────────────────────────────────
def scrape_johnleonard():
    jobs = []
    for term in ["program+manager", "project+manager", "operations", "coordinator"]:
        try:
            url  = f"https://www.johnleonard.com/find-a-job/?s={term}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job-listing, .job, article"):
                t = card.select_one("h2, h3, .title")
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


# ─────────────────────────────────────────────────────────────
# 12. BEACON HILL STAFFING (Boston — strong in admin/ops)
# ─────────────────────────────────────────────────────────────
def scrape_beaconhill():
    jobs = []
    for term in ["program+manager", "project+manager", "operations", "coordinator"]:
        try:
            url  = f"https://www.beaconhillstaffing.com/jobs?search={term}&location=Boston"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job, .job-card, article, .position"):
                t = card.select_one("h2, h3, .title, .job-title")
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
        ("Built In Boston",     scrape_builtin),
        ("Idealist",            scrape_idealist),
        ("ImpactOpportunity",   scrape_impactopportunity),
        ("TechJobsForGood",     scrape_techjobsforgood),
        ("80000hours",          scrape_80000hours),
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
