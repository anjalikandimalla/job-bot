# =============================================================================
# config.py — YOUR JOB SEARCH SETTINGS
# This is the "brain" of the bot. Edit anything in this file to change
# what jobs get picked up, scored, and logged.
# =============================================================================

import os

# ─────────────────────────────────────────────
# 1. JOB TITLES TO SEARCH
# ─────────────────────────────────────────────
JOB_TITLES = [
    "Program Manager",
    "Project Manager",
    "Operations Manager",
    "Program Coordinator",
    "Project Coordinator",
    "Senior Program Coordinator",
    "Senior Project Coordinator",
    "Operations Analyst",
    "Associate Program Manager",
    "Associate Project Manager",
]

# ─────────────────────────────────────────────
# 2. LOCATIONS
# ─────────────────────────────────────────────
LOCATIONS = [
    "Boston, MA",   # Catches hybrid/on-site Boston roles
    "Remote",        # Catches fully remote US roles
]

# ─────────────────────────────────────────────
# 3. SENIORITY — Levels to accept
# ─────────────────────────────────────────────
# These words in a title → accepted. All others still get scored normally.
ACCEPTABLE_SENIORITY_KEYWORDS = [
    "associate", "coordinator", "analyst", "specialist",
    "manager", "lead", "senior coordinator", "program manager",
    "project manager", "operations manager",
]

# These words in a title → auto-reject (too senior)
REJECT_SENIORITY_KEYWORDS = [
    "director", "vice president", "vp ", "chief", "cto", "coo", "ceo",
    "head of", "executive director", "principal",
]

# ─────────────────────────────────────────────
# 4. DEALBREAKER KEYWORDS — Auto-reject if found in job description
# ─────────────────────────────────────────────
DEALBREAKER_KEYWORDS = [
    # Visa / authorization blockers
    "no visa sponsorship",
    "cannot sponsor",
    "not able to sponsor",
    "sponsorship not available",
    "must be authorized to work",
    "must be a us citizen",
    "us citizens only",
    "active security clearance",
    "security clearance required",
    "top secret clearance",
    "secret clearance",
    "ts/sci",
    # CPT / student work restrictions
    "no cpt",
    "no opt",
    "no f-1",
    # Pay
    "unpaid",
    "volunteer",
    "no compensation",
    # Sales-heavy roles
    "sales quota",
    "commission-based",
    "commission only",
    "base + commission",
    # Short contracts (< 6 months) — handled separately too
    "1-month contract",
    "2-month contract",
    "3-month contract",
    "4-month contract",
    "5-month contract",
    "1 month contract",
    "2 month contract",
    "3 month contract",
    "4 month contract",
    "5 month contract",
]

# ─────────────────────────────────────────────
# 5. SHORT CONTRACT DETECTION (< 6 months)
# ─────────────────────────────────────────────
# If a posting mentions a contract shorter than 6 months → reject
import re
SHORT_CONTRACT_PATTERNS = [
    re.compile(r'\b[1-5][\-\s]month\s*(contract|term|position|role|engagement)', re.IGNORECASE),
    re.compile(r'contract[:\s\(]*[1-5]\s*month', re.IGNORECASE),
    re.compile(r'duration[:\s]*[1-5]\s*month', re.IGNORECASE),
]

# ─────────────────────────────────────────────
# 6. SKILLS THAT BOOST YOUR MATCH SCORE
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
# 7. CAP-EXEMPT H-1B EMPLOYERS — Highest match score boost
# ─────────────────────────────────────────────
# These organizations can sponsor H-1B visas outside the lottery cap.
# Any job from these employers gets a +10 bonus on the match score.

CAP_EXEMPT_EMPLOYER_KEYWORDS = [
    # Universities & colleges
    "university", "college", "institute of technology", "northeastern",
    "harvard", "mit", "boston university", "tufts", "boston college",
    "umass", "umb", "emerson", "suffolk", "brandeis", "wellesley",
    "simmons", "wentworth", "babson", "bentley", "lesley",
    # Teaching hospitals
    "hospital", "health system", "medical center", "clinics",
    "mass general", "mgh", "brigham", "beth israel", "dana-farber",
    "dana farber", "boston children", "boston medical", "tufts medical",
    "lahey", "newton-wellesley", "south shore", "cambridge health",
    "spaulding", "mclean", "va medical",
    # Nonprofit research
    "broad institute", "whitehead institute", "jackson laboratory",
    "joslin", "jimmy fund", "research institute", "research center",
    # Generic indicators
    "nonprofit", "non-profit", "foundation", "501(c)",
]

# ─────────────────────────────────────────────
# 8. YOUR PROFILE — Used by Claude to score each job
# ─────────────────────────────────────────────
# This is your professional summary that Claude reads before scoring every job.
# Keep it updated as your experience grows.

YOUR_PROFILE = """
NAME: Anjali Kandimalla
WORK AUTHORIZATION: F-1 CPT student — requires roles that explicitly allow CPT/OPT,
OR roles at CPT-eligible employers, OR roles that sponsor H-1B (especially cap-exempt sponsors).
TOTAL EXPERIENCE: ~6 years

CURRENT ROLE (Jan 2024 – Present):
Lead Teaching Assistant & Program Operations Lead — Northeastern University EDGE Program
- Manage grading workflows, rubric design, and TA operations across two graduate courses
- Built Smartsheet and SharePoint infrastructure for course operations
- Coordinate with faculty (Prof. Dockser, Prof. Nyaga), CEO mentors, and 100+ students
- Run end-to-end feedback cycles using Feedback Fruits and Microsoft Teams
- Designed Canvas gradebook automation and Excel/VBA formula tools

PREVIOUS ROLE (2021–2024):
R&D Program Operations — Esperion Therapeutics
- Coordinated Scientific Advisory Board (SAB) meetings and R&D Day events
- Managed cross-functional timelines, deliverables, and stakeholder communications
- Built Smartsheet tracking systems and SharePoint repositories for R&D programs
- Supported regulatory and clinical operations documentation

PREVIOUS ROLE (Jul 2019 – Sept 2020):
Consultant — Deloitte
- Process improvement and operational efficiency projects
- Built VBA automation tools in Excel for client deliverables
- Cross-functional coordination across client and internal teams

EDUCATION:
- MS Engineering Management — Trine University (Aug 2025 – Dec 2027, in progress)
- MBA — Northeastern University (May 2024), concentrations: Sustainability + Supply Chain/Operations
- B.Tech Computer Science — GITAM University (May 2019)

KEY TOOLS: Smartsheet, SharePoint, Microsoft Teams, Excel/VBA, Canvas LMS, Feedback Fruits,
PowerPoint, Python (beginner), SQL (beginner)

STRENGTHS: Cross-functional coordination, program operations, process improvement,
stakeholder management, supply chain operations, higher ed program management,
data reporting, infrastructure building
"""

# ─────────────────────────────────────────────
# 9. SCORING SETTINGS
# ─────────────────────────────────────────────
MATCH_THRESHOLD = 80          # Only log/alert jobs with score >= this
CAP_EXEMPT_BONUS = 10         # Extra points added for cap-exempt employers
POLL_INTERVAL_MINUTES = 25    # How often to check for new jobs

# ─────────────────────────────────────────────
# 10. NOTIFICATION SETTINGS
# ─────────────────────────────────────────────
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "anjalikandimalla81@gmail.com")
SEND_INSTANT_EMAIL = True     # Email you every time a 80%+ match is found
SEND_DAILY_DIGEST = True      # Also send a daily summary at 8am
