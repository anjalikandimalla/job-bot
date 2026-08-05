# =============================================================================
# config.py — JOB SEARCH SETTINGS
#
# TARGET: contract, temporary, term-limited and internship roles, 12 months
# or under. Full-time roles at cap-exempt employers are kept as a bottom tier
# only, never competing with contract results for attention.
#
# RANKING: strict tier sort (higher ed > life sciences > other > full-time
# cap-exempt), then fit score inside each tier.
# =============================================================================

import os
import re

# ─────────────────────────────────────────────
# 1. TITLES TO SEARCH
# ─────────────────────────────────────────────
JOB_TITLES = [
    "Program Manager", "Project Manager", "Operations Manager",
    "Program Coordinator", "Project Coordinator", "Operations Coordinator",
    "Research Program Coordinator", "Grants Coordinator",
    "Sponsored Programs Coordinator", "Special Projects Coordinator",
    "Program Associate", "Project Associate", "Operations Associate",
    "Program Specialist", "Project Specialist",
    "Program Management Intern", "Project Management Intern",
    "Operations Intern", "MBA Intern",
]

# ─────────────────────────────────────────────
# 2. GEOGRAPHY
# Relocation is allowed for Tier 1 and Tier 2 only. A Tier 3 role is not
# worth moving for on a sub-12-month engagement.
# ─────────────────────────────────────────────
HOME_METRO         = "Boston, MA"
LOCATIONS          = ["Boston, MA", "Cambridge, MA", "Remote"]
RELOCATION_TIERS   = (1, 2)   # tiers where non-Boston, non-remote is acceptable

# ─────────────────────────────────────────────
# 3. DURATION RULES
# Accept 1 to 12 months. Reject 13 months and over.
# ─────────────────────────────────────────────
MAX_CONTRACT_MONTHS = 12

_WORD_MONTHS_OK  = r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_WORD_MONTHS_BAD = r"(thirteen|fourteen|fifteen|eighteen|twenty|twenty-four)"

# Confirms an IN-RANGE contract (1-12 months) → accept, duration = "confirmed"
IN_RANGE_DURATION_PATTERNS = [
    re.compile(r'\b(1[0-2]|[1-9])[\s-]*month[s]?\b', re.IGNORECASE),
    re.compile(r'\bup to (1[0-2]|[1-9])\s*months?\b', re.IGNORECASE),
    re.compile(r'\b(duration|term|contract|assignment|appointment)[:\s(]*'
               r'(1[0-2]|[1-9])\s*months?\b', re.IGNORECASE),
    re.compile(r'\b(one|1)[\s-]*year\s*(contract|term|appointment|engagement|assignment)\b', re.IGNORECASE),
    re.compile(r'\b12[\s-]*month\s*(contract|term|appointment|engagement|assignment)\b', re.IGNORECASE),
    re.compile(rf'\b{_WORD_MONTHS_OK}[\s-]*month[s]?\b', re.IGNORECASE),
    re.compile(r'\bshort[\s.-]?term (contract|assignment|engagement|role|position)\b', re.IGNORECASE),
    re.compile(r'\b(academic|fall|spring|summer)\s*(semester|term)\b', re.IGNORECASE),
]

# Confirms an OUT-OF-RANGE contract (13+ months) → reject, logged separately
OUT_OF_RANGE_DURATION_PATTERNS = [
    re.compile(r'\b(1[3-9]|[2-9][0-9])[\s-]*month[s]?\b', re.IGNORECASE),
    re.compile(r'\b([2-9]|1[0-9])[\s-]*year[s]?\s*(contract|term|appointment|engagement|assignment|position|role)\b', re.IGNORECASE),
    re.compile(r'\b(two|three|four|five)[\s-]*year[s]?\s*(contract|term|appointment|engagement)\b', re.IGNORECASE),
    re.compile(rf'\b{_WORD_MONTHS_BAD}[\s-]*month[s]?\b', re.IGNORECASE),
    re.compile(r'\blong[\s.-]?term contract\b', re.IGNORECASE),
    re.compile(r'\bmulti[\s-]?year\b', re.IGNORECASE),
]

# Contract signal present, duration not stated → accept, duration = "unconfirmed"
CONTRACT_SIGNAL_KEYWORDS = [
    "contract position", "contract role", "contract opportunity", "contract assignment",
    "contract employee", "contractor", "contract-to-hire", "contract to hire", "c2h",
    "temporary position", "temporary role", "temporary assignment", "temp role",
    "temp-to-perm", "temp to perm", "temporary employee", "temporary appointment",
    "fixed term", "fixed-term", "limited term", "limited-term", "term appointment",
    "term-limited", "interim", "backfill", "leave coverage", "leave replacement",
    "maternity leave", "parental leave", "sabbatical coverage", "medical leave coverage",
    "grant funded", "grant-funded", "grant funded through", "funded through",
    "project-based", "project based", "seasonal", "per diem", "casual",
    "w2 contract", "corp-to-corp", "c2c", "1099", "contingent", "consultant engagement",
]

# Internship signals
INTERNSHIP_KEYWORDS = [
    "intern", "internship", "co-op", "coop", "cooperative education",
    "summer associate", "graduate intern", "mba intern", "practicum",
]

# Full-time signals (Tier 4 lane only)
FULLTIME_KEYWORDS = [
    "full-time", "full time", "permanent", "direct hire", "regular employee",
    "regular full-time", "indefinite", "benefits eligible", "benefits-eligible",
]

# ─────────────────────────────────────────────
# 4. GREEN FLAGS
# Strongest predictors of a genuinely term-limited role, and of the
# build-from-nothing environments where this profile outperforms.
# ─────────────────────────────────────────────
GREEN_FLAG_KEYWORDS = [
    "newly created role", "newly created position", "new position", "first hire",
    "stand up", "stand-up", "build out", "build from the ground up",
    "establish processes", "no existing process", "new program", "pilot program",
    "backfill", "leave coverage", "parental leave", "maternity leave",
    "sabbatical coverage", "interim", "grant-funded", "grant funded",
    "term appointment", "fixed-term appointment", "limited term appointment",
    "reports to the director", "reports to the executive director",
    "small team", "lean team", "wearing many hats",
]

# ─────────────────────────────────────────────
# 5. HARD DEALBREAKERS — reject regardless of tier
# ─────────────────────────────────────────────
DEALBREAKER_KEYWORDS = [
    # Sponsorship / status
    "no visa sponsorship", "cannot sponsor", "not able to sponsor",
    "sponsorship not available", "unable to provide sponsorship",
    "must be a us citizen", "us citizens only", "citizenship required",
    "no cpt", "no opt", "no f-1", "no f1",
    # Clearance
    "active security clearance", "security clearance required",
    "top secret clearance", "secret clearance", "ts/sci", "dod clearance",
    "public trust clearance",
    # Compensation — unpaid is a hard reject with no exceptions
    "unpaid", "unpaid internship", "volunteer position", "no compensation",
    "this is an unpaid", "stipend only", "for course credit only",
    "academic credit only", "commission only", "100% commission",
    # Licenses this profile does not hold
    "cpa required", "active rn license", "licensed clinical",
    "jd required", "pe license", "md required",
]

# Postings written for undergraduates — reject in the internship lane
UNDERGRAD_ONLY_KEYWORDS = [
    "rising sophomore", "rising junior", "rising senior",
    "currently enrolled in a bachelor", "pursuing a bachelor",
    "undergraduate students only", "must be an undergraduate",
    "high school student", "sophomore or junior standing",
    "enrolled at a massachusetts", "massachusetts institution",
]

# ─────────────────────────────────────────────
# 6. SENIORITY — too senior → auto-reject (whole-word match)
# ─────────────────────────────────────────────
REJECT_SENIORITY_KEYWORDS = [
    "director", "vice president", "vp", "chief",
    "cto", "coo", "ceo", "head of", "executive director", "principal",
    "staff program", "staff project", "staff technical",
]

# ─────────────────────────────────────────────
# 7. ANTI-PATTERNS
# Roles that score well on keywords and are wrong for this profile.
# Each entry: (label, [phrases]). A match forces ROLE_FIT to 0.
# ─────────────────────────────────────────────
ANTI_PATTERNS = {
    "Site-based clinical research coordinator": [
        "informed consent", "patient consent", "consenting patients",
        "study visits", "specimen collection", "phlebotomy", "venipuncture",
        "source documentation", "patient recruitment", "subject enrollment",
        "vital signs", "ecg", "clinic visits", "investigational product administration",
    ],
    "Technical program manager": [
        "technical program manager", "engineering roadmap", "sprint planning",
        "api design", "system architecture", "ci/cd", "software development lifecycle",
        "kubernetes", "microservices",
    ],
    "Product manager": [
        "product manager", "product owner", "product roadmap",
        "user stories", "backlog grooming", "go-to-market strategy",
    ],
    "Construction or facilities PM": [
        "construction", "general contractor", "punch list", "submittals",
        "building systems", "hvac", "capital projects construction", "site superintendent",
    ],
    "Agency marketing PM": [
        "creative brief", "campaign trafficking", "account executive",
        "media buying", "brand campaign", "agency of record",
    ],
    "Executive assistant labeled coordinator": [
        "calendar management", "manage complex calendars", "travel arrangements",
        "expense reports", "gatekeeper", "answer phones", "greet visitors",
    ],
    "Federal grants compliance specialist": [
        "a-133", "uniform guidance audit", "single audit", "effort certification audit",
        "cost accounting standards", "federal audit response",
    ],
    "Agile delivery role": [
        "scrum master", "certified scrum", "safe certification", "agile ceremonies",
        "daily standups", "sprint retrospectives", "csm certification",
    ],
    "Dedicated event planner": [
        "event planner", "meeting planner", "cmp certification",
        "banquet event orders", "venue sourcing", "conference services manager",
    ],
}

# ─────────────────────────────────────────────
# 8. TIER DEFINITIONS
# Tier 1 higher ed > Tier 2 life sciences > Tier 3 other > Tier 4 full-time.
# ─────────────────────────────────────────────
TIER1_HIGHER_ED_KEYWORDS = [
    "university", "college", "institute of technology", "school of medicine",
    "school of public health", "graduate school", "academy",
    "northeastern", "harvard", "mit", "massachusetts institute of technology",
    "boston university", "tufts", "boston college", "umass",
    "university of massachusetts", "emerson", "suffolk university", "brandeis",
    "wellesley", "simmons", "wentworth", "babson", "bentley", "lesley",
    "clark university", "worcester polytechnic", "wpi", "merrimack",
    "wheaton", "endicott", "regis college", "curry college", "berklee",
    "olin college", "smith college", "amherst college", "williams college",
    "dartmouth", "brown university", "yale", "princeton", "columbia university",
    "stanford", "duke university", "johns hopkins", "georgetown",
    "sponsored programs", "office of research", "research administration",
    "provost", "dean of", "academic affairs", "faculty affairs",
    "center for", "institute for", "higher education",
]

TIER2_LIFE_SCIENCES_KEYWORDS = [
    "pharmaceutical", "pharma", "biotech", "biotechnology", "biopharma",
    "therapeutics", "biosciences", "life sciences", "life science",
    "clinical research organization", "contract research organization", "cro",
    "medical device", "medtech", "diagnostics", "genomics", "oncology",
    "rare disease", "drug development", "clinical development",
    "hospital", "medical center", "health system", "cancer institute",
    "mass general", "mgh", "brigham", "beth israel", "bidmc", "bilh",
    "dana-farber", "dana farber", "boston children", "boston medical center",
    "tufts medical", "lahey", "mclean hospital", "spaulding",
    "mass general brigham", "joslin", "mass eye and ear",
    "broad institute", "whitehead institute", "jackson laboratory",
    "forsyth institute", "research institute", "research foundation",
    "academic medical center", "teaching hospital",
]

TIER3_OTHER_KEYWORDS = [
    "nonprofit", "non-profit", "not-for-profit", "foundation", "501(c)", "501c",
    "consulting", "advisory", "association", "coalition", "trust",
]

TIER_LABELS = {
    1: "Tier 1 — Higher Education",
    2: "Tier 2 — Life Sciences",
    3: "Tier 3 — Other",
    4: "Tier 4 — Full-time (cap-exempt)",
}

# ─────────────────────────────────────────────
# 9. CAP-EXEMPT EMPLOYERS — Tier 4 lane only
# ─────────────────────────────────────────────
CAP_EXEMPT_EMPLOYER_KEYWORDS = [
    "northeastern university", "northeastern", "harvard university", "harvard",
    "massachusetts institute of technology", "mit", "boston university",
    "tufts university", "tufts", "boston college", "university of massachusetts",
    "umass", "emerson college", "suffolk university", "brandeis university",
    "wellesley college", "simmons university", "wentworth institute",
    "babson college", "bentley university", "lesley university", "clark university",
    "worcester polytechnic", "wpi", "merrimack college", "wheaton college",
    "endicott college", "regis college", "cambridge college", "lasell university",
    "curry college", "berklee college",
    "massachusetts general hospital", "mass general", "mgh",
    "brigham and women", "brigham & women", "beth israel deaconess", "bidmc",
    "beth israel lahey", "bilh", "dana-farber cancer institute", "dana farber",
    "dana-farber", "boston children's hospital", "boston childrens",
    "boston medical center", "bmc", "tufts medical center", "lahey hospital",
    "lahey clinic", "newton-wellesley hospital", "south shore hospital",
    "cambridge health alliance", "spaulding rehabilitation", "mclean hospital",
    "va boston", "va medical center", "veterans affairs", "mass eye and ear",
    "joslin diabetes center", "mass general brigham", "partners healthcare",
    "umass memorial", "baystate health", "shriners hospital",
    "new england baptist", "northwell health", "northwell", "montefiore",
    "mount sinai", "nyu langone", "harrington hospital", "cooley dickinson",
    "broad institute", "whitehead institute", "jackson laboratory",
    "mitre corporation", "mitre", "education development center", "edc",
    "abt associates", "icf international", "draper laboratory", "draper lab",
    "charles stark draper", "lincoln laboratory", "mit lincoln",
    "the forsyth institute", "health effects institute",
    "nonprofit", "non-profit", "not-for-profit", "foundation", "501(c)", "501c",
    "research institute", "research center", "research foundation",
    "teaching hospital", "academic medical center", "health system",
    "health alliance", "health network", "medical school", "school of medicine",
    "school of public health",
]

VERIFIED_H1B_SPONSORS = [
    "northeastern university", "harvard university", "mit",
    "massachusetts institute of technology", "boston university",
    "tufts university", "boston college", "umass",
    "massachusetts general hospital", "mass general", "mgh",
    "brigham and women", "beth israel deaconess", "beth israel lahey health",
    "bilh", "dana-farber", "boston children's hospital", "boston medical center",
    "broad institute", "mitre", "draper laboratory", "lincoln laboratory",
    "abt associates", "icf", "education development center",
    "mass general brigham", "partners healthcare", "lahey clinic",
    "tufts medical center", "spaulding rehabilitation", "mclean hospital",
    "joslin diabetes", "whitehead institute",
]

# ─────────────────────────────────────────────
# 10. CAPABILITY CLUSTERS
# Role fit is scored on how many of these the job actually requires,
# not on whether the title matches.
# ─────────────────────────────────────────────
CAPABILITY_CLUSTERS = {
    1: {
        "name": "Multi-workstream coordination at scale",
        "differentiator": False,
        "evidence": "20+ MBA courses, 2-3 concurrent per term, sections of 30-100; "
                    "3-6 concurrent CRO studies at Esperion",
        "signals": [
            "multiple concurrent", "competing deadlines", "several projects",
            "portfolio of projects", "coordinate across teams", "multiple stakeholders",
            "concurrent workstreams", "juggle", "simultaneous projects",
            "cross-functional coordination", "project timelines", "milestone tracking",
        ],
    },
    2: {
        "name": "External partner and vendor lifecycle",
        "differentiator": True,
        "evidence": "Primary liaison to 3-6 CROs; NDAs, MSAs and study budgets across "
                    "Legal, Finance, Contracting and Scientific Affairs; KOL contracting "
                    "and invoicing",
        "signals": [
            "vendor management", "vendor coordination", "supplier", "subaward",
            "subcontract", "consultant agreement", "sponsor agreement", "cro",
            "contract research organization", "nda", "msa", "statement of work",
            "procurement", "invoicing", "purchase order", "external partners",
            "third-party", "contract lifecycle", "contract negotiation support",
        ],
    },
    3: {
        "name": "Building tracking infrastructure from nothing",
        "differentiator": True,
        "evidence": "SharePoint and Teams built from scratch at Esperion with no prior "
                    "infrastructure; Smartsheet and SharePoint rebuild at EDGE; risk "
                    "registers and stakeholder logs at MWIN",
        "signals": [
            "build out", "stand up", "establish", "create processes", "from scratch",
            "no existing", "newly created", "new program", "implement systems",
            "develop tracking", "design workflows", "sharepoint", "smartsheet",
            "knowledge management", "documentation systems", "process infrastructure",
        ],
    },
    4: {
        "name": "Convening senior external people",
        "differentiator": True,
        "evidence": "Quarterly Scientific Advisory Board with 15+ KOLs; first company "
                    "R&D Day investor event; onboarded three CEO mentors for a capstone",
        "signals": [
            "advisory board", "advisory committee", "steering committee",
            "board meetings", "convening", "symposium", "speaker series",
            "external advisory", "key opinion leader", "kol", "faculty committee",
            "guest speakers", "external experts", "investor event", "donor events",
        ],
    },
    5: {
        "name": "Budget tracking and forecasting",
        "differentiator": False,
        "evidence": "Owned R&D budget tracking and produced FY2024 forecast; study cost "
                    "and vendor payment records with no dedicated finance support",
        "signals": [
            "budget tracking", "budget management", "expense reconciliation",
            "grant budget", "financial reporting", "forecast", "cost tracking",
            "monitor spending", "invoice reconciliation", "financial oversight",
            "budget monitoring", "expenditures",
        ],
    },
    6: {
        "name": "Participant and learner operations",
        "differentiator": False,
        "evidence": "EDGE onboarding, advising, escalation routing, sub-24h response; "
                    "MWIN internship placements for 25+ students with industry partners",
        "signals": [
            "cohort", "fellows", "participants", "student support", "onboarding",
            "program experience", "learner", "scholars", "trainees", "mentees",
            "advising", "orientation", "recruitment of participants", "canvas", "lms",
        ],
    },
    7: {
        "name": "Process standardization and SLA design",
        "differentiator": False,
        "evidence": "Escalation routing design and sub-24h SLA at EDGE; communication "
                    "template redesign; standardized handoffs cutting contract approval "
                    "cycle time roughly 30% at Esperion",
        "signals": [
            "sop", "standard operating procedure", "process documentation",
            "workflow design", "standardize", "service level", "turnaround time",
            "process improvement", "streamline", "escalation", "continuous improvement",
            "efficiency", "cycle time",
        ],
    },
    8: {
        "name": "Executive-facing communication",
        "differentiator": False,
        "evidence": "C-suite and board decks at Esperion; divestiture coordination across "
                    "manager, C-suite and board; investor and partnership materials",
        "signals": [
            "board materials", "executive reporting", "leadership briefings",
            "presentations to senior", "executive summaries", "c-suite",
            "senior leadership", "board of directors", "stakeholder reporting",
            "prepare presentations", "communications to leadership",
        ],
    },
    9: {
        "name": "Technical and data literacy",
        "differentiator": False,
        "evidence": "CS degree; self-taught VBA at Deloitte cutting reporting turnaround "
                    "roughly 40%; advanced Excel; Canvas CSV wrangling and gradebook "
                    "formulas; regression coursework at Trine; built this job bot",
        "signals": [
            "data analysis", "reporting", "automation", "excel", "pivot tables",
            "dashboards", "data cleaning", "vba", "macros", "database",
            "systems administration", "data entry quality", "metrics",
        ],
    },
}

DIFFERENTIATOR_CLUSTERS = [k for k, v in CAPABILITY_CLUSTERS.items() if v["differentiator"]]

# ─────────────────────────────────────────────
# 11. PERFECT-FIT ARCHETYPES (used as scoring guidance)
# ─────────────────────────────────────────────
ARCHETYPES = {
    1: [
        ("Research Program Coordinator / Manager at a center or institute", [1, 2, 4, 5, 6]),
        ("Sponsored Programs / Research Administration Coordinator", [2, 5, 7]),
        ("Academic or Executive Education Program Coordinator", [1, 6, 7]),
        ("Special Projects Coordinator to a dean, provost or center director", [3, 8]),
        ("Grants Coordinator / Grants Manager (non-CPA)", [2, 5, 7]),
        ("Center or Institute Operations Coordinator", [3, 4, 5]),
        ("Faculty Affairs Coordinator", [7, 8]),
    ],
    2: [
        ("Clinical Trial / Study Start-Up Coordinator (sponsor or admin side)", [2, 5, 7]),
        ("Alliance Management / Clinical Outsourcing Associate", [2, 5]),
        ("Medical Affairs or Advisory Board Coordinator", [4, 8]),
        ("R&D Operations / Program Operations Associate", [1, 3, 5]),
        ("Clinical Contracts and Budgets Specialist", [2, 5]),
        ("PMO Analyst at a biotech", [1, 8]),
    ],
    3: [
        ("Interim program manager covering a leave at a nonprofit", [1, 3, 7]),
        ("Foundation operations coordinator running grantee programs", [2, 5, 6]),
        ("Implementation or onboarding coordinator", [6, 7]),
        ("PMO analyst on a defined corporate project", [1, 8]),
    ],
}

# ─────────────────────────────────────────────
# 12. SKILLS (kept for prompt context)
# ─────────────────────────────────────────────
YOUR_SKILLS = [
    "program coordination", "project coordination", "program operations",
    "cross-functional coordination", "stakeholder management",
    "milestone tracking", "deliverable management", "concurrent workstreams",
    "vendor management", "CRO coordination", "NDA", "MSA", "contract lifecycle",
    "vendor invoicing", "subaward coordination", "external stakeholder management",
    "budget tracking", "budget forecasting", "cost tracking",
    "SharePoint", "Smartsheet", "MS Teams", "Canvas LMS", "knowledge management",
    "process improvement", "workflow design", "SLA management", "escalation design",
    "operational infrastructure", "systems design from scratch",
    "Excel", "advanced Excel", "Excel VBA", "VBA", "data cleaning",
    "dashboard design", "PowerPoint", "executive presentations", "business writing",
    "event coordination", "scientific advisory board", "SAB", "KOL management",
    "risk registers", "risk escalation", "onboarding", "student operations",
    "higher education", "pharmaceutical R&D", "rare disease", "R&D operations",
    "supply chain", "procurement", "consulting", "market research",
    "business case development",
]

# ─────────────────────────────────────────────
# 13. PROFILE
# ─────────────────────────────────────────────
YOUR_PROFILE = """
NAME: Anjali Kandimalla
LOCATION: Boston, MA (open to remote, and to relocation for higher ed or life sciences)
TARGET: contract, temporary, term-limited and internship roles, 12 months or under
TOTAL RELEVANT EXPERIENCE: ~5 years across pharma R&D, higher education and consulting

EXPERIENCE

1) Northeastern University, EDGE — Lead Teaching Assistant & Program Coordinator,
   Online MBA (Jan 2024 - Apr 2026, Boston MA)
   - Coordinated delivery of 20+ MBA courses, 2-3 concurrent per term, sections of
     30-100 students, across 8+ faculty, course managers, instructional designers
     and ed-tech staff
   - Rebuilt an inherited Smartsheet and SharePoint setup into a single source for
     course status: milestone tracking, communications logs, content repositories
   - Redesigned the student communication set (welcome, late-submission reminders,
     engagement nudges) to reach students before deadlines slipped
   - Held response time under 24 hours on all student and faculty inquiries by
     designing escalation routing that sent each issue to the right owner first time
   - Managed mid-semester drops and team restructuring while keeping group projects intact
   - Onboarded three CEO mentors for a capstone simulation (access, scheduling, setup)
   - Built formula-driven gradebooks from Canvas CSV exports; solved Canvas encoding issues
   - 100% faculty re-invitation rate; commended by three professors

2) Esperion Therapeutics — R&D Program Fellow (Jun 2022 - Aug 2023, Ann Arbor MI)
   Two-person R&D team on rare disease assets, PM-level work under a Fellow title
   - Primary liaison to 3-6 external CROs; established NDAs, MSAs and study budgets
     by coordinating Legal, Finance, Contracting and Scientific Affairs on each
   - Cut contract approval cycle time roughly 30% by mapping the approval path,
     standardizing handoffs and driving daily follow-ups
   - Built the team's first project tracking infrastructure: SharePoint documentation
     and MS Teams workflows, designed from scratch where nothing existed
   - Owned R&D budget tracking and produced the FY2024 forecast with no finance support
   - Delivered quarterly Scientific Advisory Board meetings with 15+ KOLs, owning
     scheduling, materials, KOL contracting and invoicing, and next-step conversion
   - Coordinated divestiture discussions for a non-core asset across manager, C-suite
     and board; the asset was later divested
   - Developed rare disease business cases: ran market research, split work across
     Regulatory, Clinical and Business Development, tracked each to completion
   - Launched the company's first R&D Day investor and analyst event with Marketing
     and Investor Relations

3) Northeastern University, MWIN — Project Manager (Sep 2021 - May 2022, Boston MA)
   - Managed internship placements for 25+ high school students with industry partners
   - Built centralized tracking for sponsor communications, deliverables and progress
   - Maintained risk registers, stakeholder logs and program metrics for leadership

4) Deloitte — Advisory Analyst, Audit & Advisory (Jul 2019 - Sep 2020, Hyderabad India)
   - Self-taught VBA to automate reporting and approval tracking; cut turnaround
     roughly 40%, returned about 10 hours a week
   - Replaced fragmented data entry with centralized Excel tools
   - Built reusable dashboards and templates adopted across the wider team

5) Aadrika Exports — Founder & Proprietor (Mar 2017 - Jul 2019, Visakhapatnam India)
   Family business, off the resume but real experience. Use as supporting evidence for
   supply chain, procurement, vendor networks and cross-border logistics only.
   - Ran a global supply chain end to end: vendor networks, procurement cycles,
     scope/cost/delivery alignment across international markets
   - Managed a cross-functional team across sourcing, logistics and finance
     (the only role with direct people management)

EDUCATION
- MS Engineering Management, Trine University (in progress, expected Dec 2027).
  Completed BA 6933 Statistics: regression analysis on supply chain data, hypothesis
  testing, ANOVA, chi-square, correlation and regression.
- MBA, Northeastern University (May 2024). Sustainability & Business; Operations and
  Supply Chain Management.
- B.Tech Computer Science, GITAM University (May 2019).

TOOLS (honest proficiency — do not credit unearned strength)
- Strong, daily professional use: Excel (advanced formulas, data cleaning),
  PowerPoint, Canvas LMS
- Competent, regular use: Smartsheet, SharePoint, MS Teams, VBA
- Familiar only, coursework or self-learning, NOT professional use:
  Tableau, Power BI, Jira, Confluence, Monday.com, Asana, Python, SQL

DIFFERENTIATORS
- Builds operational infrastructure from nothing (Esperion SharePoint and Teams,
  EDGE rebuild, MWIN tracking systems)
- Performs well with limited resources (two-person team, no PM tooling, no finance support)
- Coordinates across levels: C-suite, board, KOLs, faculty, students, vendors
- Self-directed (taught herself VBA; raised her hand for portfolio strategy work;
  built an automated job search pipeline on GitHub Actions)
- CS degree plus MBA: technical enough to automate, business-trained enough for board decks
"""

# ─────────────────────────────────────────────
# 14. SCORING & NOTIFICATION SETTINGS
# ─────────────────────────────────────────────
MATCH_THRESHOLD        = 65     # lowered from 80; tier sort handles prioritisation
GREEN_FLAG_BONUS       = 3      # per green flag, capped below
GREEN_FLAG_BONUS_CAP   = 6
UNCONFIRMED_DURATION_PENALTY = 5
CAP_EXEMPT_BONUS       = 2      # Tier 4 lane only
POLL_INTERVAL_MINUTES  = 360    # main.py local loop only; GitHub Actions uses the workflow cron
NOTIFY_EMAIL           = os.getenv("NOTIFY_EMAIL", "anjalikandimalla25@gmail.com")
SEND_INSTANT_EMAIL     = False
SEND_DAILY_DIGEST      = True
