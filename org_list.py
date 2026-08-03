# =============================================================================
# org_list.py — Verified cap-exempt H-1B organization career endpoints
#
# Each entry has the EXACT API URL discovered by visiting the org's careers page
# and inspecting Network → look for POST to /wday/cxs/{tenant}/{site}/jobs
#
# URL format:  https://{tenant}.{datacenter}.myworkdayjobs.com/{site}
#   datacenter can be wd1, wd3, wd5, wd12 etc — depends on Workday region
# =============================================================================

ORGS = [
    # ════════════════════════════════════════════════════════════════
    # WORKDAY — VERIFIED from real career page URLs
    # ════════════════════════════════════════════════════════════════


    # Mass General Brigham — massgeneralbrigham.wd1.myworkdayjobs.com/MGBExternal
    {"name": "Mass General Brigham",
     "ats": "workday", "tenant": "massgeneralbrigham", "datacenter": "wd1",
     "career_site": "MGBExternal", "type": "hospital", "remote_ok": True},

    # Dana-Farber — danafarber.wd5.myworkdayjobs.com/dana-farbernonrecruit
    {"name": "Dana-Farber Cancer Institute",
     "ats": "workday", "tenant": "danafarber", "datacenter": "wd5",
     "career_site": "dana-farbernonrecruit", "type": "hospital", "remote_ok": False},

    # Boston University
    {"name": "Boston University",
     "ats": "workday", "tenant": "bu", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": True},

    # Tufts University
    {"name": "Tufts University",
     "ats": "workday", "tenant": "tufts", "datacenter": "wd1",
     "career_site": "Careers_External", "type": "university", "remote_ok": True},

    # Beth Israel Lahey Health (covers BIDMC, Lahey, etc.)
    {"name": "Beth Israel Lahey Health",
     "ats": "workday", "tenant": "bilh", "datacenter": "wd5",
     "career_site": "BILH", "type": "hospital", "remote_ok": False},

    # MITRE
    {"name": "MITRE Corporation",
     "ats": "workday", "tenant": "mitre", "datacenter": "wd5",
     "career_site": "MITRE", "type": "research", "remote_ok": True},

    # ICF International
    {"name": "ICF International",
     "ats": "workday", "tenant": "icf", "datacenter": "wd1",
     "career_site": "ICFExternal", "type": "research", "remote_ok": True},

    # RAND
    {"name": "RAND Corporation",
     "ats": "workday", "tenant": "rand", "datacenter": "wd1",
     "career_site": "External", "type": "research", "remote_ok": True},

    # Brandeis
    {"name": "Brandeis University",
     "ats": "workday", "tenant": "brandeis", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": False},

    # WPI
    {"name": "Worcester Polytechnic Institute",
     "ats": "workday", "tenant": "wpi", "datacenter": "wd1",
     "career_site": "WPI_External_Career_Site", "type": "university", "remote_ok": False},

    # Babson College
    {"name": "Babson College",
     "ats": "workday", "tenant": "babson", "datacenter": "wd1",
     "career_site": "Babson_Careers", "type": "university", "remote_ok": False},

    # ════════════════════════════════════════════════════════════════
    # GREENHOUSE — verified board tokens (boards.greenhouse.io/{token})
    # ════════════════════════════════════════════════════════════════

    {"name": "Broad Institute", "ats": "greenhouse",
     "tenant": "broadinstitute", "type": "research", "remote_ok": True},

    {"name": "Whitehead Institute", "ats": "greenhouse",
     "tenant": "whiteheadinstitute", "type": "research", "remote_ok": False},

    {"name": "Mathematica", "ats": "greenhouse",
     "tenant": "mathematicampr", "type": "research", "remote_ok": True},

    # ════════════════════════════════════════════════════════════════
    # CUSTOM scrapers (org-specific systems)
    # ════════════════════════════════════════════════════════════════

    # Harvard uses BrassRing / Kenexa
    {"name": "Harvard University", "ats": "custom_brassring",
     "tenant": "harvard",
     "partner_id": "25240", "site_id": "5341",
     "type": "university", "remote_ok": True},

    # MIT has its own system at sjobs.brassring.com
    {"name": "MIT", "ats": "custom_brassring",
     "tenant": "mit",
     "partner_id": "25240", "site_id": "5392",
     "type": "university", "remote_ok": True},

    # Boston Children's Hospital uses iCIMS
    {"name": "Boston Children's Hospital", "ats": "icims",
     "tenant": "bostonchildrens",
     "url": "https://jobs.childrenshospital.org/search-jobs/results?ActiveFacetID=0&CurrentPage=1&RecordsPerPage=15&Distance=50&RadiusUnitType=0&Keywords=program%20manager",
     "type": "hospital", "remote_ok": False},

    # Boston Medical Center uses iCIMS
    {"name": "Boston Medical Center", "ats": "icims",
     "tenant": "bmc",
     "url": "https://careers-bmc.icims.com/jobs/search?ss=1&searchKeyword=program+manager",
     "type": "hospital", "remote_ok": False},

    # ════════════════════════════════════════════════════════════════
    # ADDED IN THE CONTRACT PIVOT
    # Northeastern was missing entirely despite being the top target.
    # Universities post term appointments and grant-funded roles publicly.
    # Their temp pools do NOT appear here: Harvard routes contingent hiring
    # through Yoh and MIT through nextSource, both registration rather than
    # scraping. See sources_contract.scrape_yoh() for the Harvard-adjacent lane.
    #
    # Tenant/datacenter/career_site values below are best-guess defaults.
    # org_scraper.scrape_workday_org() already retries across wd1/wd5/wd3/wd2
    # and the standard site-name variants, then caches whichever combo works,
    # so a wrong guess self-corrects on first successful run. Any org that
    # stays at 0 listings for several days needs its real URL pulled from the
    # careers page Network tab.
    # ════════════════════════════════════════════════════════════════

    {"name": "Northeastern University",
     "ats": "workday", "tenant": "northeastern", "datacenter": "wd1",
     "career_site": "careers", "type": "university", "remote_ok": True},

    {"name": "University of Massachusetts",
     "ats": "workday", "tenant": "umass", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": True},

    {"name": "Emerson College",
     "ats": "workday", "tenant": "emerson", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": False},

    {"name": "Simmons University",
     "ats": "workday", "tenant": "simmons", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": False},

    {"name": "Suffolk University",
     "ats": "workday", "tenant": "suffolk", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": False},

    {"name": "Bentley University",
     "ats": "workday", "tenant": "bentley", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": False},

    {"name": "Lesley University",
     "ats": "workday", "tenant": "lesley", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": False},

    {"name": "Wellesley College",
     "ats": "workday", "tenant": "wellesley", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": False},

    {"name": "Berklee College of Music",
     "ats": "workday", "tenant": "berklee", "datacenter": "wd1",
     "career_site": "External", "type": "university", "remote_ok": False},

    {"name": "Tufts Medicine",
     "ats": "workday", "tenant": "tuftsmedicine", "datacenter": "wd1",
     "career_site": "External", "type": "hospital", "remote_ok": False},

    {"name": "Cambridge Health Alliance",
     "ats": "workday", "tenant": "challiance", "datacenter": "wd1",
     "career_site": "External", "type": "hospital", "remote_ok": False},
]


def get_workday_orgs():
    return [o for o in ORGS if o["ats"] == "workday"]

def get_greenhouse_orgs():
    return [o for o in ORGS if o["ats"] == "greenhouse"]

def get_custom_orgs():
    return [o for o in ORGS if o["ats"].startswith("custom") or o["ats"] == "icims"]

def get_all_orgs():
    return ORGS
