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
    "staff program", "staff project", "staff technical",  # too senior at tech cos
    "sr. program", "sr. project", "sr. operations",       # abbreviation for Senior
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
    "northwell health", "northwell",
    "montefiore", "mount sinai", "nyu langone",   # NY hospital systems that hire remote
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
    # Program/Project Management — primary
    "program management", "project management", "program coordination",
    "project coordination", "program operations", "operations",
    "stakeholder management", "cross-functional coordination",
    "cross-functional", "milestone tracking", "deliverable management",
    "multi-project management", "concurrent workstreams",
    "scheduling", "timeline management",
    "risk management", "risk escalation", "escalation",
    # Operations & process
    "process improvement", "workflow design", "process standardization",
    "SLA management", "cycle time reduction", "operational infrastructure",
    "systems design",
    # Vendor / external partner
    "vendor management", "vendor coordination",
    "CRO management", "CRO coordination", "contract research organization",
    "NDA", "MSA", "contract lifecycle", "vendor invoicing",
    "external stakeholder", "partner coordination",
    # Budget / financial
    "budget tracking", "budget forecasting", "cost tracking",
    "financial tracking", "budget management",
    # Documentation / systems
    "SharePoint", "Smartsheet", "MS Teams", "Microsoft Teams",
    "knowledge management", "documentation",
    "Canvas LMS", "LMS",
    # Technical
    "Excel", "Excel VBA", "VBA", "advanced Excel", "Excel formulas",
    "PowerPoint", "dashboard design", "data cleaning",
    # Communication
    "executive communication", "executive presentations",
    "business writing", "reporting",
    # Event / meeting coordination
    "event coordination", "event planning",
    "scientific advisory board", "SAB", "KOL management",
    # Industry experience
    "higher education", "pharmaceutical R&D", "rare disease",
    "R&D operations", "supply chain", "consulting",
    # Cross-cutting
    "onboarding", "student operations", "learner support",
    "problem solving", "self-directed", "initiative",
]

# ─────────────────────────────────────────────
# 9. YOUR PROFILE
# ─────────────────────────────────────────────
YOUR_PROFILE = """
NAME: Anjali Kandimalla
LOCATION: Boston, MA
WORK AUTHORIZATION: F-1 student with CPT
- FULL-TIME roles: requires cap-exempt H-1B sponsor (university/teaching hospital/nonprofit research)
- CONTRACT ≤6 months: no sponsorship needed (CPT covers this)
TOTAL RELEVANT EXPERIENCE: ~4+ years across pharma R&D, higher ed, and consulting

EXPERIENCE:

1) Northeastern University EDGE (Jan 2024 – Apr 2026)
   Lead Teaching Assistant & Program Coordinator, Online MBA
   - Coordinated 20+ MBA courses; 2-3 concurrent per term; classes 30-100 students
   - Worked across 8+ faculty, course managers, instructional design, ed-tech
   - Inherited and improved Smartsheet/SharePoint setup: milestone tracking, communication logs, content repos
   - <24h response SLA on student/faculty inquiries; designed escalation routing
   - Built Canvas-ready grading workflows; Excel gradebooks from Canvas CSV exports

2) Esperion Therapeutics (Jun 2022 – Aug 2023)
   R&D Program Fellow (PM-level work)
   - Two-person R&D team; managed 3-6 external CRO relationships
   - Cross-functional with Legal, Finance, Contracting, Scientific Affairs for NDAs/MSAs/budgets
   - Built SharePoint documentation + MS Teams workflows FROM SCRATCH (no prior infrastructure)
   - Reduced contract approval cycle time ~30% by standardizing handoffs
   - Owned R&D budget tracking + FY24 forecast
   - Coordinated quarterly Scientific Advisory Board meetings with 15+ KOLs
   - Created exec presentations for C-suite, board, R&D Day investor event, partnership discussions

3) Northeastern MWIN (Sep 2021 – May 2022)
   Project Manager
   - Internship operations for 25+ high school students with industry partners
   - Built centralized tracking systems; risk registers; stakeholder logs

4) Deloitte (Jul 2019 – Sep 2020)
   Advisory Analyst (Audit & Advisory)
   - Self-taught VBA; automated reporting workflows (~40% turnaround reduction, ~400 hrs/year saved)
   - Built reusable Excel dashboards/templates adopted team-wide

EDUCATION:
- MS Engineering Management — Trine University (in progress, expected Dec 2027)
- MBA — Northeastern (May 2024), Sustainability & Operations and Supply Chain Management
- B.Tech Computer Science — GITAM University (May 2019)

TOOLS (proficiency-rated):
- Strong (daily/professional use): Excel (advanced + formulas), PowerPoint, Canvas LMS
- Competent (regular use): Smartsheet, SharePoint, MS Teams, VBA
- Familiar (limited/self-learning only): Tableau, Power BI, Jira, Confluence, Monday.com, Asana, Python, SQL

KEY DIFFERENTIATORS:
- Builds operational infrastructure FROM NOTHING (Esperion SharePoint, EDGE rebuild)
- Thrives with limited resources (two-person team at Esperion, no PM tools)
- Cross-level coordination: C-suite, board, KOLs, faculty, students
- Self-directed learner (VBA at Deloitte, strategic portfolio contributions at Esperion)
- CS degree + MBA combination — technical AND business literate
"""

# ─────────────────────────────────────────────
# 10. SCORING & NOTIFICATION SETTINGS
# ─────────────────────────────────────────────
MATCH_THRESHOLD        = 80
CAP_EXEMPT_BONUS       = 2
POLL_INTERVAL_MINUTES  = 180
NOTIFY_EMAIL           = os.getenv("NOTIFY_EMAIL", "anjalikandimalla25@gmail.com")
SEND_INSTANT_EMAIL     = False
SEND_DAILY_DIGEST      = True
