# =============================================================================
# org_list.py — Master list of Massachusetts cap-exempt H-1B organizations
#
# Each org has:
#   name       — display name
#   ats        — ATS system: "workday", "greenhouse", "icims", "rss", "custom"
#   tenant     — ATS tenant/board ID
#   career_site— Workday career site name (Workday only)
#   url        — fallback career page URL
#   type       — "university", "hospital", "research", "nonprofit"
#   remote_ok  — whether org is known to hire remotely
#
# TO ADD A NEW ORG: copy any entry and fill in the fields.
# Find Workday tenant: go to org's careers page, look at the URL subdomain.
# Find Greenhouse board: go to org's careers page, find "greenhouse.io" in links.
# =============================================================================

ORGS = [

    # ══════════════════════════════════════════════════════════
    # UNIVERSITIES — Massachusetts
    # ══════════════════════════════════════════════════════════

    {"name": "Northeastern University",          "ats": "workday",    "tenant": "northeastern",           "career_site": "careers",              "type": "university", "remote_ok": True},
    {"name": "Boston University",                "ats": "workday",    "tenant": "bu",                     "career_site": "External",             "type": "university", "remote_ok": True},
    {"name": "Tufts University",                 "ats": "workday",    "tenant": "tuftsu",                 "career_site": "Tufts_External",        "type": "university", "remote_ok": True},
    {"name": "Brandeis University",              "ats": "workday",    "tenant": "brandeis",               "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Wellesley College",                "ats": "workday",    "tenant": "wellesley",              "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Clark University",                 "ats": "workday",    "tenant": "clarku",                 "career_site": "CU_External",          "type": "university", "remote_ok": False},
    {"name": "Worcester Polytechnic Institute",  "ats": "workday",    "tenant": "wpi",                    "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Emerson College",                  "ats": "workday",    "tenant": "emerson",                "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Simmons University",               "ats": "workday",    "tenant": "simmons",                "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Babson College",                   "ats": "workday",    "tenant": "babson",                 "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Bentley University",               "ats": "workday",    "tenant": "bentley",                "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Lesley University",                "ats": "workday",    "tenant": "lesley",                 "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Suffolk University",               "ats": "workday",    "tenant": "suffolk",                "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Endicott College",                 "ats": "workday",    "tenant": "endicott",               "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Merrimack College",                "ats": "workday",    "tenant": "merrimack",              "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Regis College",                    "ats": "workday",    "tenant": "regiscollege",           "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Lasell University",                "ats": "workday",    "tenant": "lasell",                 "career_site": "External",             "type": "university", "remote_ok": False},

    # Harvard and MIT use custom systems (scraped via their own APIs)
    {"name": "Harvard University",               "ats": "custom",     "tenant": "harvard",                "career_site": "",
     "url": "https://hr.harvard.edu/working-harvard/find-job",
     "api_url": "https://sjobs.brassring.com/TGnewUI/Search/Home/Home?partnerid=25240&siteid=5341#home",
     "type": "university", "remote_ok": True},

    {"name": "MIT",                              "ats": "custom",     "tenant": "mit",                    "career_site": "",
     "url": "https://careers.mit.edu",
     "api_url": "https://careers.mit.edu/search-jobs",
     "type": "university", "remote_ok": True},

    {"name": "Boston College",                   "ats": "custom",     "tenant": "bc",                     "career_site": "",
     "url": "https://www.bc.edu/bc-web/offices/human-resources/careers.html",
     "type": "university", "remote_ok": False},

    {"name": "UMass Boston",                     "ats": "custom",     "tenant": "umassboston",             "career_site": "",
     "url": "https://careers.umass.edu",
     "type": "university", "remote_ok": False},

    {"name": "UMass Lowell",                     "ats": "custom",     "tenant": "umasslowell",             "career_site": "",
     "url": "https://careers.umass.edu",
     "type": "university", "remote_ok": False},

    {"name": "UMass Medical School",             "ats": "workday",    "tenant": "umassmed",               "career_site": "External",             "type": "university", "remote_ok": True},
    {"name": "Wentworth Institute",              "ats": "workday",    "tenant": "wit",                    "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Gordon College",                   "ats": "workday",    "tenant": "gordon",                 "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Wheaton College MA",               "ats": "workday",    "tenant": "wheatonma",              "career_site": "External",             "type": "university", "remote_ok": False},
    {"name": "Stonehill College",                "ats": "workday",    "tenant": "stonehill",              "career_site": "External",             "type": "university", "remote_ok": False},

    # ══════════════════════════════════════════════════════════
    # TEACHING HOSPITALS & HEALTH SYSTEMS — Massachusetts
    # ══════════════════════════════════════════════════════════

    # Mass General Brigham system (one Workday tenant covers MGH, BWH, McLean,
    # Spaulding, Mass Eye and Ear, Cooley Dickinson, and more)
    {"name": "Mass General Brigham",             "ats": "workday",    "tenant": "massgeneralbrigham",     "career_site": "External",             "type": "hospital", "remote_ok": True},

    # Beth Israel Lahey Health system
    {"name": "Beth Israel Lahey Health",         "ats": "workday",    "tenant": "bilh",                   "career_site": "External_Career_Site", "type": "hospital", "remote_ok": True},

    {"name": "Dana-Farber Cancer Institute",     "ats": "workday",    "tenant": "danafarbercancerinstitute","career_site": "External",            "type": "hospital", "remote_ok": True},
    {"name": "Boston Children's Hospital",       "ats": "workday",    "tenant": "childrenshospital",       "career_site": "External",            "type": "hospital", "remote_ok": False},
    {"name": "Boston Medical Center",            "ats": "workday",    "tenant": "bmc",                    "career_site": "External",             "type": "hospital", "remote_ok": False},
    {"name": "Tufts Medical Center",             "ats": "workday",    "tenant": "tuftsmedicalcenter",     "career_site": "External",             "type": "hospital", "remote_ok": False},
    {"name": "UMass Memorial Health",            "ats": "workday",    "tenant": "umassmemorial",           "career_site": "External",            "type": "hospital", "remote_ok": False},
    {"name": "Baystate Health",                  "ats": "workday",    "tenant": "baystatehealth",          "career_site": "External",            "type": "hospital", "remote_ok": False},
    {"name": "South Shore Health",               "ats": "workday",    "tenant": "southshorehealth",        "career_site": "External",            "type": "hospital", "remote_ok": False},
    {"name": "Cambridge Health Alliance",        "ats": "workday",    "tenant": "challiance",              "career_site": "External",            "type": "hospital", "remote_ok": False},
    {"name": "Steward Health Care",              "ats": "workday",    "tenant": "steward",                 "career_site": "External",            "type": "hospital", "remote_ok": False},
    {"name": "Hallmark Health / Tufts",          "ats": "workday",    "tenant": "tuftsmedicalcenter",      "career_site": "External",            "type": "hospital", "remote_ok": False},
    {"name": "Joslin Diabetes Center",           "ats": "greenhouse", "tenant": "joslindiabetescenter",    "career_site": "",                    "type": "hospital", "remote_ok": False},
    {"name": "Shriners Hospital Boston",         "ats": "workday",    "tenant": "shrinerschildrens",       "career_site": "External",            "type": "hospital", "remote_ok": False},
    {"name": "VA Boston Healthcare",             "ats": "custom",     "tenant": "usajobs",                 "career_site": "",
     "url": "https://www.usajobs.gov/Search/Results?l=Boston%2C+MA&a=VATA",
     "type": "hospital", "remote_ok": False},

    # ══════════════════════════════════════════════════════════
    # RESEARCH ORGANIZATIONS & NONPROFITS
    # ══════════════════════════════════════════════════════════

    {"name": "Broad Institute",                  "ats": "greenhouse", "tenant": "broadinstitute",         "career_site": "",                     "type": "research", "remote_ok": True},
    {"name": "Whitehead Institute",              "ats": "greenhouse", "tenant": "whiteheadinstitute",      "career_site": "",                    "type": "research", "remote_ok": False},
    {"name": "MITRE Corporation",                "ats": "workday",    "tenant": "mitre",                  "career_site": "External",             "type": "research", "remote_ok": True},
    {"name": "Draper Laboratory",                "ats": "workday",    "tenant": "draper",                 "career_site": "External",             "type": "research", "remote_ok": True},
    {"name": "MIT Lincoln Laboratory",           "ats": "custom",     "tenant": "mitll",                  "career_site": "",
     "url": "https://www.ll.mit.edu/careers",
     "type": "research", "remote_ok": False},
    {"name": "Education Development Center",     "ats": "greenhouse", "tenant": "edc",                    "career_site": "",                     "type": "nonprofit", "remote_ok": True},
    {"name": "Abt Associates",                   "ats": "workday",    "tenant": "abtassociates",          "career_site": "External",             "type": "research", "remote_ok": True},
    {"name": "ICF International",                "ats": "workday",    "tenant": "icf",                    "career_site": "ExternalCareerSite",   "type": "research", "remote_ok": True},
    {"name": "JSI Research & Training",          "ats": "greenhouse", "tenant": "jsires",                 "career_site": "",                     "type": "nonprofit", "remote_ok": True},
    {"name": "Health Effects Institute",         "ats": "custom",     "tenant": "healtheffects",          "career_site": "",
     "url": "https://www.healtheffects.org/about/employment",
     "type": "research", "remote_ok": True},
    {"name": "Forsyth Institute",                "ats": "greenhouse", "tenant": "forsythinstitute",       "career_site": "",                     "type": "research", "remote_ok": False},
    {"name": "American Institutes for Research", "ats": "workday",    "tenant": "air",                    "career_site": "External",             "type": "research", "remote_ok": True},
    {"name": "Mathematica",                      "ats": "greenhouse", "tenant": "mathematica",            "career_site": "",                     "type": "research", "remote_ok": True},
    {"name": "Urban Institute",                  "ats": "greenhouse", "tenant": "urbaninstitute",         "career_site": "",                     "type": "nonprofit", "remote_ok": True},
    {"name": "RAND Corporation",                 "ats": "workday",    "tenant": "rand",                   "career_site": "External",             "type": "research", "remote_ok": True},
    {"name": "Battelle",                         "ats": "workday",    "tenant": "battelle",               "career_site": "BTL_External",         "type": "research", "remote_ok": True},
    {"name": "RTI International",                "ats": "workday",    "tenant": "rti",                    "career_site": "External",             "type": "research", "remote_ok": True},
    {"name": "Westat",                           "ats": "workday",    "tenant": "westat",                 "career_site": "External",             "type": "research", "remote_ok": True},
    {"name": "Social Policy Research Associates","ats": "greenhouse", "tenant": "spra",                   "career_site": "",                     "type": "nonprofit", "remote_ok": True},
    {"name": "Center for Health Information",    "ats": "custom",     "tenant": "chil",                   "career_site": "",
     "url": "https://www.chiamass.gov/career-opportunities/",
     "type": "nonprofit", "remote_ok": False},
]

# ─────────────────────────────────────────────────────────────
# HELPER: get orgs filtered by type or remote
# ─────────────────────────────────────────────────────────────

def get_workday_orgs():
    return [o for o in ORGS if o["ats"] == "workday"]

def get_greenhouse_orgs():
    return [o for o in ORGS if o["ats"] == "greenhouse"]

def get_custom_orgs():
    return [o for o in ORGS if o["ats"] == "custom"]

def get_all_orgs():
    return ORGS
