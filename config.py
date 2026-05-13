# =============================================================================
# config.py — YOUR JOB SEARCH SETTINGS
# =============================================================================

import os
import re

# ─────────────────────────────────────────────
# 1. JOB TITLES TO SEARCH
# ─────────────────────────────────────────────
JOB_TITLES = [
    "Program Manager", "Project Manager", "Operations Manager",
    "Program Coordinator", "Project Coordinator",
    "Senior Program Coordinator", "Senior Project Coordinator",
    "Operations Analyst", "Associate Program Manager", "Associate Project Manager",
]

# ─────────────────────────────────────────────
# 2. LOCATIONS
# ─────────────────────────────────────────────
LOCATIONS = ["Boston, MA", "Remote"]

# ─────────────────────────────────────────────
# 3. SENIORITY — Too-senior titles → auto-reject
# Whole-word match only (avoids 'coo' matching inside 'coordinator')
# ─────────────────────────────────────────────
REJECT_SENIORITY_KEYWORDS = [
    "director", "vice president", "vp", "chief",
    "cto", "coo", "ceo", "head of", "executive director", "principal",
]

# ─────────────────────────────────────────────
# 4. HARD DEALBREAKERS — Reject ALL role types
# ─────────────────────────────────────────────
DEALBREAKER_KEYWORDS = [
    "no visa sponsorship", "cannot sponsor", "not able to sponsor",
    "sponsorship not available",
    "must be authorized to work in the us without sponsorship",
    "must be a us citizen", "us citizens only",
    "active security clearance", "security clearance required",
    "top secret clearance", "secret clearance", "ts/sci", "dod clearance",
    "no cpt", "no opt", "no f-1", "no f1",
    "unpaid", "volunteer position", "no compensation",
    "commission only", "100% commission",
]

# ─────────────────────────────────────────────
# 5. CONTRACT DURATION DETECTION
# ─────────────────────────────────────────────
# We WANT contracts that are 6 months or less.
# Contracts longer than 6 months → treated as full-time (need cap-exempt H-1B).

# Patterns that confirm a SHORT contract (≤ 6 months) → ACCEPT
SHORT_CONTRACT_PATTERNS = [
    re.compile(r'\b([1-6])[- ]month[s]?\b', re.IGNORECASE),
    re.compile(r'\bup to [1-6] months?\b', re.IGNORECASE),
    re.compile(r'\bshort.?term contract\b', re.IGNORECASE),
    re.compile(r'\bcontract[:\s\(]*[1-6]\s*months?\b', re.IGNORECASE),
    re.compile(r'\bduration[:\s]*[1-6]\s*months?\b', re.IGNORECASE),
    re.compile(r'\bterm[:\s]*[1-6]\s*months?\b', re.IGNORECASE),
]

# Patterns that confirm a LONG contract (> 6 months) → treat as full-time
LONG_CONTRACT_PATTERNS = [
    re.compile(r'\b([7-9]|1[0-9]|2[0-4])[- ]month[s]?\b', re.IGNORECASE),
    re.compile(r'\b(1|2)\s*year[s]?\s*(contract|term|engagement)\b', re.IGNORECASE),
    re.compile(r'\blong.?term contract\b', re.IGNORECASE),
    re.compile(r'\bcontract[:\s\(]*(7|8|9|10|11|12)\s*months?\b', re.IGNORECASE),
]

# General contract keywords (no duration specified — duration unknown)
GENERIC_CONTRACT_KEYWORDS = [
    "contract position", "contract role", "contract employee",
    "contract-to-hire", "contract to hire", "c2h",
    "temporary position", "temp role", "temp-to-perm",
    "fixed term", "fixed-term", "limited term",
    "contingent", "w2 contract", "corp-to-corp", "c2c", "1099",
]

# Full-time signals
FULLTIME_KEYWORDS = [
    "full-time", "full time", "permanent", "direct hire",
    "regular employee", "regular full-time", "indefinite", "benefits eligible",
]

# ─────────────────────────────────────────────
# 6. CAP-EXEMPT H-1B EMPLOYERS
# Full-time roles MUST match one of these to be considered.
# ─────────────────────────────────────────────
CAP_EXEMPT_EMPLOYER_KEYWORDS = [
    # Universities & colleges
    "northeastern university", "northeastern",
    "harvard university", "harvard",
    "massachusetts institute of technology", "mit",
    "boston university",
    "tufts university", "tufts",
    "boston college",
    "university of massachusetts", "umass",
    "emerson college", "suffolk university",
    "brandeis university", "wellesley college",
    "simmons university", "wentworth institute",
    "babson college", "bentley university",
    "lesley university", "clark university",
    "worcester polytechnic", "wpi",
    "merrimack college", "wheaton college",
    "endicott college", "regis college",
    "cambridge college", "lasell university", "curry college",
    # Teaching hospitals & health systems
    "massachusetts general hospital", "mass general", "mgh",
    "brigham and women", "brigham & women",
    "beth israel deaconess", "bidmc",
    "dana-farber cancer institute", "dana farber", "dana-farber",
    "boston children's hospital", "boston childrens",
    "boston medical center", "bmc",
    "tufts medical center",
    "lahey hospital", "lahey clinic",
    "newton-wellesley hospital",
    "south shore hospital",
    "cambridge health alliance",
    "spaulding rehabilitation",
    "mclean hospital",
    "va boston", "va medical center", "veterans affairs",
    "mass eye and ear",
    "joslin diabetes center",
    "mass general brigham", "partners healthcare",
    "umass memorial", "baystate health",
    "shriners hospital", "new england baptist",
    "harrington hospital", "cooley dickinson",
    # Nonprofit research
    "broad institute", "whitehead institute",
    "jackson laboratory", "mitre corporation", "mitre",
    "education development center", "edc",
    "abt associates", "icf international",
    "draper laboratory", "draper lab", "charles stark draper",
    "lincoln laboratory", "mit lincoln",
    "the forsyth institute",
    "health effects institute",
    # Generic indicators
    "nonprofit", "non-profit", "not-for-profit",
    "foundation", "501(c)", "501c",
    "research institute", "research center", "research foundation",
    "teaching hospital", "academic medical center",
    "health system", "health alliance", "health network",
    "medical school", "school of medicine", "school of public health",
]

# ─────────────────────────────────────────────
# 7. VERIFIED H-1B SPONSORS (2024-2026)
# Used to add a "Verified" flag in the Google Sheet
# ─────────────────────────────────────────────
VERIFIED_H1B_SPONSORS = [
    "northeastern university", "harvard university", "mit",
    "massachusetts institute of technology", "boston university",
    "tufts university", "boston college", "umass",
    "massachusetts general hospital", "mass general", "mgh",
    "brigham and women", "beth israel deaconess",
    "dana-farber", "boston children's hospital", "boston medical center",
    "broad institute", "mitre", "draper laboratory", "lincoln laboratory",
    "abt associates", "icf", "education development center",
    "mass general brigham", "partners healthcare",
    "lahey clinic", "tufts medical center", "spaulding rehabilitation",
    "mclean hospital", "joslin diabetes", "whitehead institute",
]

# ─────────────────────────────────────────────
# 8. YOUR SKILLS
# ─────────────────────────────────────────────
YOUR_SKILLS = [
    "smartsheet", "sharepoint", "microsoft teams", "ms teams",
    "cross-functional", "cross functional", "stakeholder management",
    "stakeholder", "process improvement", "vba", "excel",
    "supply chain", "operations", "program operations", "program management",
    "project management", "data analysis", "reporting", "dashboard",
    "onboarding", "coordination", "curriculum", "lms", "canvas",
    "agile", "scrum", "waterfall", "pmp", "risk management",
    "vendor management", "budget", "kpi", "metrics",
]

# ─────────────────────────────────────────────
# 9. YOUR PROFILE
# ─────────────────────────────────────────────
YOUR_PROFILE = """
NAME: Anjali Kandimalla
WORK AUTHORIZATION: F-1 CPT student
- FULL-TIME roles: needs cap-exempt H-1B sponsor (university/hospital/nonprofit)
- CONTRACT ≤6 months: no sponsorship needed (CPT covers this)
TOTAL EXPERIENCE: ~6 years

CURRENT ROLE (Jan 2024 – Present):
Lead Teaching Assistant & Program Operations Lead — Northeastern University EDGE
- Manage grading workflows, rubric design, TA operations across two graduate courses
- Built Smartsheet and SharePoint infrastructure for course operations
- Coordinate with faculty, CEO mentors, and 100+ students
- End-to-end feedback cycles using Feedback Fruits and Microsoft Teams
- Canvas gradebook automation and Excel/VBA formula tools

PREVIOUS (2021–2024): R&D Program Operations — Esperion Therapeutics
- Coordinated SAB meetings, R&D Day events, cross-functional timelines
- Built Smartsheet tracking systems and SharePoint repositories
- Supported regulatory and clinical operations documentation

PREVIOUS (Jul 2019–Sep 2020): Consultant — Deloitte
- Process improvement and operational efficiency projects
- VBA automation tools in Excel; cross-functional coordination

EDUCATION:
- MS Engineering Management — Trine University (in progress, Dec 2027)
- MBA — Northeastern (May 2024), Supply Chain/Operations + Sustainability
- B.Tech Computer Science — GITAM University (May 2019)

KEY TOOLS: Smartsheet, SharePoint, Microsoft Teams, Excel/VBA, Canvas LMS,
Feedback Fruits, PowerPoint, Python (beginner), SQL (beginner)
"""

# ─────────────────────────────────────────────
# 10. SCORING & NOTIFICATION SETTINGS
# ─────────────────────────────────────────────
MATCH_THRESHOLD        = 80
CAP_EXEMPT_BONUS       = 10
POLL_INTERVAL_MINUTES  = 30
NOTIFY_EMAIL           = os.getenv("NOTIFY_EMAIL", "anjalikandimalla81@gmail.com")
SEND_INSTANT_EMAIL     = True
SEND_DAILY_DIGEST      = True
