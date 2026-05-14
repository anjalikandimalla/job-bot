# =============================================================================
# org_list.py — Cap-exempt H-1B organizations with verified ATS details
#
# Workday tenant IDs are verified by checking the actual careers URL:
#   https://{tenant}.wd1.myworkdayjobs.com  — if this 404s, tenant is wrong
#
# ATS types:
#   "workday"    — POST API, fastest and most reliable
#   "greenhouse" — GET API, good for nonprofits/research
#   "custom"     — org-specific scraper in org_scraper.py
#   "skip"       — listed for reference but not scraped (wrong ATS or no API)
# =============================================================================

ORGS = [

    # ══════════════════════════════════════════════════════════════
    # WORKDAY — VERIFIED TENANTS
    # These have been confirmed against real Workday career URLs
    # ══════════════════════════════════════════════════════════════

    # Universities
    {"name": "Northeastern University",       "ats": "workday", "tenant": "northeastern",          "career_site": "careers",              "type": "university", "remote_ok": True},
    {"name": "Boston University",             "ats": "workday", "tenant": "bu",                    "career_site": "External",             "type": "university", "remote_ok": True},
    {"name": "Tufts University",              "ats": "workday", "tenant": "tuftsu",                "career_site": "Tufts_External",       "type": "university", "remote_ok": True},
    {"name": "Brandeis University",           "ats": "workday", "tenant": "brandeis",              "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Wellesley College",             "ats": "workday", "tenant": "wellesley",             "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Worcester Polytechnic (WPI)",   "ats": "workday", "tenant": "wpi",                   "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Babson College",                "ats": "workday", "tenant": "babson",                "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Bentley University",            "ats": "workday", "tenant": "bentley",               "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "UMass Medical School",          "ats": "workday", "tenant": "umassmed",              "career_site": "External",             "type": "university", "remote_ok": True},
    {"name": "American Institutes Research",  "ats": "workday", "tenant": "air",                   "career_site": "External",             "type": "research",   "remote_ok": True},
    {"name": "RAND Corporation",              "ats": "workday", "tenant": "rand",                  "career_site": "External",             "type": "research",   "remote_ok": True},
    {"name": "Battelle",                      "ats": "workday", "tenant": "battelle",              "career_site": "BTL_External",         "type": "research",   "remote_ok": True},
    {"name": "RTI International",             "ats": "workday", "tenant": "rti",                   "career_site": "External",             "type": "research",   "remote_ok": True},
    {"name": "Westat",                        "ats": "workday", "tenant": "westat",                "career_site": "External",             "type": "research",   "remote_ok": True},
    {"name": "ICF International",             "ats": "workday", "tenant": "icf",                   "career_site": "ExternalCareerSite",   "type": "research",   "remote_ok": True},
    {"name": "Abt Associates",                "ats": "workday", "tenant": "abtassociates",         "career_site": "External",             "type": "research",   "remote_ok": True},
    {"name": "MITRE Corporation",             "ats": "workday", "tenant": "mitre",                 "career_site": "External",             "type": "research",   "remote_ok": True},
    {"name": "Draper Laboratory",             "ats": "workday", "tenant": "draper",                "career_site": "External",             "type": "research",   "remote_ok": False},

    # Hospitals — using iCIMS or other systems (not Workday), scraped via custom/RSS
    # Mass General Brigham → iCIMS (not Workday)
    # Beth Israel Lahey   → Workday, but tenant unverified
    # Dana-Farber         → Workday, tenant unverified

    # ══════════════════════════════════════════════════════════════
    # GREENHOUSE — VERIFIED BOARD TOKENS
    # ══════════════════════════════════════════════════════════════

    {"name": "Broad Institute",               "ats": "greenhouse", "tenant": "broadinstitute",      "career_site": "", "type": "research",  "remote_ok": True},
    {"name": "Whitehead Institute",           "ats": "greenhouse", "tenant": "whiteheadinstitute",  "career_site": "", "type": "research",  "remote_ok": False},
    {"name": "Education Development Center", "ats": "greenhouse", "tenant": "edc",                  "career_site": "", "type": "nonprofit", "remote_ok": True},
    {"name": "Mathematica",                   "ats": "greenhouse", "tenant": "mathematica",         "career_site": "", "type": "research",  "remote_ok": True},
    {"name": "Urban Institute",               "ats": "greenhouse", "tenant": "urbaninstitute",      "career_site": "", "type": "nonprofit", "remote_ok": True},
    {"name": "Forsyth Institute",             "ats": "greenhouse", "tenant": "forsythinstitute",    "career_site": "", "type": "research",  "remote_ok": False},
    {"name": "JSI Research & Training",       "ats": "greenhouse", "tenant": "jsires",              "career_site": "", "type": "nonprofit", "remote_ok": True},
    {"name": "Joslin Diabetes Center",        "ats": "greenhouse", "tenant": "joslindiabetescenter","career_site": "", "type": "hospital",  "remote_ok": False},

    # ══════════════════════════════════════════════════════════════
    # CUSTOM — Scraped via their own career systems
    # ══════════════════════════════════════════════════════════════

    {"name": "Harvard University",            "ats": "custom",     "tenant": "harvard",    "career_site": "",
     "url": "https://sjobs.brassring.com/TGnewUI/Search/Home/HomeWithPreLoad?partnerid=25240&siteid=5341",
     "type": "university", "remote_ok": True},

    {"name": "MIT",                           "ats": "custom",     "tenant": "mit",        "career_site": "",
     "url": "https://careers.mit.edu",
     "type": "university", "remote_ok": True},

    {"name": "VA Boston Healthcare",          "ats": "custom",     "tenant": "usajobs",    "career_site": "",
     "url": "https://www.usajobs.gov/Search/Results?l=Boston%2C+MA&a=VATA",
     "type": "hospital", "remote_ok": False},

    # ══════════════════════════════════════════════════════════════
    # LISTED FOR REFERENCE — ATS not confirmed, excluded from scraping
    # Add back once tenant ID is verified
    # ══════════════════════════════════════════════════════════════

    # Mass General Brigham → uses iCIMS, not Workday. Scraped via USAJobs/general boards.
    # Beth Israel Lahey Health → Workday tenant unclear
    # Dana-Farber Cancer Institute → Workday tenant unclear
    # Boston Children's Hospital → Workday tenant unclear
    # Boston Medical Center → Workday tenant unclear
    # Tufts Medical Center → Workday tenant unclear
    # Cambridge Health Alliance → Workday tenant unclear
]


def get_workday_orgs():
    return [o for o in ORGS if o["ats"] == "workday"]

def get_greenhouse_orgs():
    return [o for o in ORGS if o["ats"] == "greenhouse"]

def get_custom_orgs():
    return [o for o in ORGS if o["ats"] == "custom"]

def get_all_orgs():
    return [o for o in ORGS if o["ats"] != "skip"]
