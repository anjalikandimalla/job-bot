# =============================================================================
# scorer.py — Eligibility gates + tiering + Gemini scoring
#
# ACCEPTANCE:
#   Contract / temp / term-limited, 1-12 months, duration confirmed   → ACCEPT
#   Contract signal present, duration not stated                      → ACCEPT (flagged)
#   Internship (paid)                                                 → ACCEPT
#   Full-time at a cap-exempt employer                                → ACCEPT (Tier 4)
#   Everything else                                                   → REJECT
#
# RANKING: strict tier sort, then fit score inside the tier.
#   Tier 1 higher ed > Tier 2 life sciences > Tier 3 other > Tier 4 full-time
# =============================================================================

import re
import os
import time
from google import genai
from dotenv import load_dotenv
load_dotenv()

from config import (
    DEALBREAKER_KEYWORDS, UNDERGRAD_ONLY_KEYWORDS, REJECT_SENIORITY_KEYWORDS,
    IN_RANGE_DURATION_PATTERNS, OUT_OF_RANGE_DURATION_PATTERNS,
    CONTRACT_SIGNAL_KEYWORDS, INTERNSHIP_KEYWORDS, FULLTIME_KEYWORDS,
    GREEN_FLAG_KEYWORDS, ANTI_PATTERNS,
    TIER1_HIGHER_ED_KEYWORDS, TIER2_LIFE_SCIENCES_KEYWORDS, TIER3_OTHER_KEYWORDS,
    TIER_LABELS, CAP_EXEMPT_EMPLOYER_KEYWORDS, VERIFIED_H1B_SPONSORS,
    CAPABILITY_CLUSTERS, DIFFERENTIATOR_CLUSTERS, ARCHETYPES,
    YOUR_SKILLS, YOUR_PROFILE,
    MATCH_THRESHOLD, CAP_EXEMPT_BONUS,
    GREEN_FLAG_BONUS, GREEN_FLAG_BONUS_CAP, UNCONFIRMED_DURATION_PENALTY,
    HOME_METRO, RELOCATION_TIERS,
)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DAILY_QUOTA_EXHAUSTED = False


def _text_of(job: dict) -> str:
    return " ".join([
        job.get("title", ""), job.get("description", ""),
        job.get("company", ""), job.get("location", ""),
    ]).lower()


# ─────────────────────────────────────────────────────────────
# FORMAT DETECTION
# Returns one of:
#   "contract_confirmed"    1-12 months, stated
#   "contract_unconfirmed"  contract signal, no duration stated
#   "internship"            paid internship or co-op
#   "fulltime"              full-time / permanent
#   "out_of_range"          13+ months stated
# ─────────────────────────────────────────────────────────────

def detect_format(job: dict) -> str:
    text = _text_of(job)
    title = job.get("title", "").lower()

    is_internship = any(kw in title for kw in INTERNSHIP_KEYWORDS) or \
                    any(kw in text for kw in INTERNSHIP_KEYWORDS[:3])

    # An explicit out-of-range duration wins over everything except internships,
    # since a 15-month "contract" is a full-time role wearing a contract label.
    for pattern in OUT_OF_RANGE_DURATION_PATTERNS:
        if pattern.search(text):
            return "internship" if is_internship else "out_of_range"

    for pattern in IN_RANGE_DURATION_PATTERNS:
        if pattern.search(text):
            return "internship" if is_internship else "contract_confirmed"

    if is_internship:
        return "internship"

    if any(kw in text for kw in CONTRACT_SIGNAL_KEYWORDS):
        return "contract_unconfirmed"

    if any(kw in text for kw in FULLTIME_KEYWORDS):
        return "fulltime"

    return "fulltime"   # no signal at all — treat conservatively


# ─────────────────────────────────────────────────────────────
# TIERING
# ─────────────────────────────────────────────────────────────

def assign_tier(job: dict, fmt: str) -> int:
    """Tier 4 is reserved for the full-time cap-exempt lane."""
    if fmt == "fulltime":
        return 4

    company = job.get("company", "").lower()
    desc_head = job.get("description", "").lower()[:1200]
    blob = f"{company} {desc_head}"

    if any(kw in blob for kw in TIER1_HIGHER_ED_KEYWORDS):
        return 1
    if any(kw in blob for kw in TIER2_LIFE_SCIENCES_KEYWORDS):
        return 2
    if any(kw in blob for kw in TIER3_OTHER_KEYWORDS):
        return 3
    return 3


def check_cap_exempt(job: dict) -> tuple[bool, bool]:
    """Returns (is_cap_exempt, is_verified_h1b_sponsor)."""
    company_lower = job.get("company", "").lower()
    desc_lower = job.get("description", "").lower()[:600]
    cap_exempt = any(kw in company_lower or kw in desc_lower
                     for kw in CAP_EXEMPT_EMPLOYER_KEYWORDS)
    verified = any(s in company_lower for s in VERIFIED_H1B_SPONSORS)
    return cap_exempt, verified


def detect_anti_pattern(job: dict) -> str:
    """Returns the anti-pattern label if the posting trips one, else ''."""
    text = _text_of(job)
    for label, phrases in ANTI_PATTERNS.items():
        hits = sum(1 for p in phrases if p in text)
        # Two hits required so a single passing mention does not disqualify.
        if hits >= 2:
            return label
    return ""


def find_green_flags(job: dict) -> list:
    text = _text_of(job)
    return [kw for kw in GREEN_FLAG_KEYWORDS if kw in text]


def location_is_workable(job: dict, tier: int) -> tuple[bool, str]:
    loc = (job.get("location", "") + " " + job.get("description", "")[:300]).lower()
    if any(k in loc for k in ["remote", "work from home", "telecommute", "virtual", "anywhere"]):
        return True, "Remote"
    if any(k in loc for k in ["boston", "cambridge", "massachusetts", ", ma", "somerville",
                              "brookline", "medford", "waltham", "burlington", "watertown",
                              "quincy", "newton", "worcester", "chestnut hill"]):
        return True, "Boston metro"
    if tier in RELOCATION_TIERS:
        return True, "Relocation"
    return False, "Out of area (Tier 3+)"


# ─────────────────────────────────────────────────────────────
# LOCAL FILTER
# Signature kept as a 5-tuple for run_once.py compatibility.
# Extra metadata is written onto the job dict.
# ─────────────────────────────────────────────────────────────

def passes_local_filter(job: dict) -> tuple[bool, str, str, bool, bool]:
    text = _text_of(job)

    # 1. Hard dealbreakers, including unpaid
    for kw in DEALBREAKER_KEYWORDS:
        if kw in text:
            return False, f"Dealbreaker: '{kw}'", "unknown", False, False

    # 2. Seniority, whole-word match on the title
    padded_title = f" {job.get('title','').lower()} "
    for word in REJECT_SENIORITY_KEYWORDS:
        if f" {word} " in padded_title:
            return False, f"Too senior: '{word}' in title", "unknown", False, False

    # 3. Backfill a thin description from the posting URL
    if len(job.get("description", "")) < 50:
        fetched = _try_fetch_description(job.get("url", ""))
        if fetched and len(fetched) > 50:
            job["description"] = fetched
        elif len(job.get("description", "")) < 20:
            job["description"] = (f"Job at {job.get('company','')}: {job.get('title','')}. "
                                  f"Full description at {job.get('url','')}.")
        text = _text_of(job)

    # 4. Format and tier
    fmt = detect_format(job)
    tier = assign_tier(job, fmt)
    cap_exempt, verified = check_cap_exempt(job)

    job["format"] = fmt
    job["tier"] = tier
    job["tier_label"] = TIER_LABELS[tier]
    job["green_flags"] = find_green_flags(job)

    # 5. Duration out of range
    if fmt == "out_of_range":
        return False, "Contract longer than 12 months", fmt, cap_exempt, verified

    # 6. Undergraduate-only internships
    if fmt == "internship":
        for kw in UNDERGRAD_ONLY_KEYWORDS:
            if kw in text:
                return False, f"Undergraduate-only internship: '{kw}'", fmt, cap_exempt, verified

    # 7. Full-time lane requires a cap-exempt employer
    if fmt == "fulltime" and not cap_exempt:
        return False, "Full-time at non-cap-exempt org", fmt, cap_exempt, verified

    # 8. Anti-patterns
    anti = detect_anti_pattern(job)
    if anti:
        job["anti_pattern"] = anti
        return False, f"Anti-pattern: {anti}", fmt, cap_exempt, verified

    # 9. Geography
    workable, loc_note = location_is_workable(job, tier)
    job["location_note"] = loc_note
    if not workable:
        return False, f"Location not workable: {job.get('location','')}", fmt, cap_exempt, verified

    return True, "", fmt, cap_exempt, verified


# ─────────────────────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────────────────────

def _clusters_block() -> str:
    lines = []
    for num, c in CAPABILITY_CLUSTERS.items():
        star = " [DIFFERENTIATOR]" if c["differentiator"] else ""
        lines.append(f"{num}. {c['name']}{star}\n   Evidence: {c['evidence']}")
    return "\n".join(lines)


def _archetypes_block(tier: int) -> str:
    arche = ARCHETYPES.get(tier if tier in ARCHETYPES else 3, [])
    return "\n".join(
        f"- {name} (clusters {', '.join(str(c) for c in clusters)})"
        for name, clusters in arche
    )


SCORING_PROMPT = """
You are a strict, honest job match evaluator for Anjali Kandimalla. Score conservatively.
Do not inflate. An inflated score costs her a wasted application.

CANDIDATE PROFILE:
{profile}

════════════════════════════════════════
CAPABILITY CLUSTERS
Role fit is judged on how many of these the job actually REQUIRES, not on whether
the job title resembles hers. Clusters marked DIFFERENTIATOR are rare in the
candidate pool and should be weighted heavily when the job requires them.
════════════════════════════════════════
{clusters}

════════════════════════════════════════
STRONG-FIT ARCHETYPES FOR THIS TIER ({tier_label})
════════════════════════════════════════
{archetypes}

════════════════════════════════════════
JOB POSTING
════════════════════════════════════════
Title: {title}
Company: {company}
Location: {location}
Format: {fmt}
Tier: {tier_label}
Green flags detected: {green_flags}
Description:
{description}

════════════════════════════════════════
HARD DISQUALIFIERS — score 0 immediately
════════════════════════════════════════
- Requires US citizenship or an active security clearance
- Explicitly refuses visa sponsorship or requires authorization without sponsorship
- Unpaid, stipend-only, or for academic credit only
- Requires 8+ years of experience (candidate has ~5)
- Requires a license she lacks: CPA, JD, MD, RN, PE. PMP and CAPM are fine.
- Director-level or above in scope even if the title says otherwise
- Primary skill is one she has no background in: software engineering, licensed
  clinical care, legal practice, accounting, quota-carrying sales
- The role is a site-based clinical research coordinator doing patient consent,
  study visits, specimen collection or source documentation. Sponsor-side and
  administrative study coordination is a GOOD fit; patient-facing is not.

════════════════════════════════════════
SCORE CAPS — apply before totalling
════════════════════════════════════════
- Requires 6-7 years experience → cap LEVEL_FIT at 6
- 3+ core required skills entirely absent from her profile → cap EVIDENCE_MATCH at 12
- Role is primarily technical (software, data engineering, DevOps) → cap ROLE_FIT at 8
- Job requires Jira, Tableau, Power BI, Asana, Monday.com, SQL or Python as a
  CORE DAILY tool → cap EVIDENCE_MATCH at 20. Her exposure is coursework and
  self-learning only. Do not credit these as professional strengths.
- Job is primarily dedicated event planning → cap ROLE_FIT at 12

════════════════════════════════════════
SCORING (0-100)
════════════════════════════════════════

1. ROLE_FIT (0-35) — cluster coverage, not title matching
   5+ clusters required including 2+ DIFFERENTIATOR clusters → 30-35
   4-5 clusters including 1 DIFFERENTIATOR                   → 24-29
   3-4 clusters, all non-differentiator                      → 15-23
   1-2 clusters                                              → 5-14
   Anti-pattern role                                         → 0

2. EVIDENCE_MATCH (0-35) — you MUST cite specific evidence
   For every capability you credit, name the concrete item from her profile that
   backs it (for example "3-6 CROs at Esperion", "SharePoint built from scratch",
   "SAB with 15+ KOLs", "sub-24h SLA at EDGE", "VBA automation at Deloitte").
   If you cannot name a specific backing item, the match DOES NOT COUNT.
   6+ credited capabilities with named evidence → 30-35
   4-5 with named evidence                      → 22-29
   2-3 with named evidence                      → 12-21
   0-1                                          → 0-11

3. LEVEL_FIT (0-15)
   Requires 0-5 yrs, coordinator to manager level → 12-15
   Requires 5-6 yrs                               → 8-11
   Requires 6-7 yrs                               → 3-6
   Requires 8+ yrs                                → 0 (disqualifier above)

4. LOGISTICS_FIT (0-15)
   Duration stated and 12 months or under, location workable, direct employer → 12-15
   Duration stated, location workable, staffing agency intermediary           → 9-11
   Duration not stated but contract signal present                            → 6-8
   Location or start date awkward                                             → 0-5

════════════════════════════════════════
RESPOND IN EXACTLY THIS FORMAT — nothing else
════════════════════════════════════════
SCORE: [0-100]
ROLE_FIT: [0-35]
EVIDENCE_MATCH: [0-35]
LEVEL_FIT: [0-15]
LOGISTICS_FIT: [0-15]
CLUSTERS_MATCHED: [comma-separated cluster numbers the job requires, e.g. 1, 2, 5]
EVIDENCE_CITED: [for each credited capability, "capability — backing item from profile"; semicolon separated]
MISSING_SKILLS: [core requirements she lacks, or "None"]
GAP_SEVERITY: [Blocking / Significant / Minor / None — Blocking means do not apply]
OVERQUALIFICATION_RISK: [High / Medium / Low / N-A — N-A for non-internship roles]
RESUME_VERSION: [Program Management OR Operations]
RESUME_TAILORING: [1-2 sentences naming which specific bullets to lead with for this
role, and whether to add the Aadrika Exports supply chain experience or Trine MS coursework]
SUMMARY: [2 sentences: what makes this a fit, and the single biggest gap]
"""


def score_with_gemini(job: dict, fmt: str, tier: int) -> dict | None:
    global DAILY_QUOTA_EXHAUSTED
    if DAILY_QUOTA_EXHAUSTED:
        return None

    prompt = SCORING_PROMPT.format(
        profile=YOUR_PROFILE,
        clusters=_clusters_block(),
        archetypes=_archetypes_block(tier),
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        fmt=fmt,
        tier_label=TIER_LABELS.get(tier, ""),
        green_flags=", ".join(job.get("green_flags", [])) or "none",
        description=job.get("description", "")[:3500],
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt,
        )
        return parse_score(response.text.strip())
    except Exception as e:
        err = str(e)
        is_quota = "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower()
        if not is_quota:
            print(f"    ⚠️  Gemini error: {e}")
            return None
        if "PerDayPer" in err or "GenerateRequestsPerDay" in err:
            DAILY_QUOTA_EXHAUSTED = True
            print("    🚫 Daily quota exhausted — skipping remaining scoring this cycle.")
            print("       Resets at midnight UTC (8 PM Eastern).")
            return None
        print("    ⏳ Per-minute rate limit — waiting 65s...")
        time.sleep(65)
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=prompt,
            )
            return parse_score(response.text.strip())
        except Exception as e2:
            if "PerDayPer" in str(e2) or "GenerateRequestsPerDay" in str(e2):
                DAILY_QUOTA_EXHAUSTED = True
                print("    🚫 Daily quota exhausted — skipping remaining scoring.")
            else:
                print(f"    ⚠️  Gemini retry failed: {e2}")
            return None


# Every text field the model returns, parsed. The previous version silently
# dropped RESUME_VERSION and RESUME_TAILORING, so the sheet always said
# "Program Management" with an empty tailoring column.
_INT_FIELDS = {
    "SCORE:": "score",
    "ROLE_FIT:": "role_fit",
    "EVIDENCE_MATCH:": "evidence_match",
    "LEVEL_FIT:": "level_fit",
    "LOGISTICS_FIT:": "logistics_fit",
}
_TEXT_FIELDS = {
    "CLUSTERS_MATCHED:": "clusters_matched",
    "EVIDENCE_CITED:": "evidence_cited",
    "MISSING_SKILLS:": "missing_skills",
    "GAP_SEVERITY:": "gap_severity",
    "OVERQUALIFICATION_RISK:": "overqualification_risk",
    "RESUME_VERSION:": "resume_version",
    "RESUME_TAILORING:": "resume_tailoring",
    "SUMMARY:": "summary",
}


def parse_score(raw: str) -> dict:
    r = {v: 0 for v in _INT_FIELDS.values()}
    r.update({v: "" for v in _TEXT_FIELDS.values()})
    for line in raw.split("\n"):
        line = line.strip()
        for prefix, key in _INT_FIELDS.items():
            if line.upper().startswith(prefix):
                m = re.search(r"\d+", line)
                r[key] = int(m.group()) if m else 0
                break
        else:
            for prefix, key in _TEXT_FIELDS.items():
                if line.upper().startswith(prefix):
                    r[key] = line.split(":", 1)[1].strip().strip("[]")
                    break
    if not r["resume_version"]:
        r["resume_version"] = "Program Management"
    return r


# ─────────────────────────────────────────────────────────────
# MASTER EVALUATOR
# ─────────────────────────────────────────────────────────────

FORMAT_LABELS = {
    "contract_confirmed":   "Contract (duration confirmed, ≤12mo)",
    "contract_unconfirmed": "Contract (duration NOT stated)",
    "internship":           "Internship / Co-op",
    "fulltime":             "Full-time (cap-exempt)",
}


def evaluate_job(job: dict) -> dict | None:
    passes, reason, fmt, cap_exempt, verified = passes_local_filter(job)
    if not passes:
        print(f"    ❌ REJECTED ({reason}): {job.get('title')} @ {job.get('company')}")
        return None

    tier = job.get("tier", 3)
    print(f"    🤖 Scoring [T{tier} | {fmt}]: {job.get('title')} @ {job.get('company')}...")
    scoring = score_with_gemini(job, fmt, tier)
    if not scoring:
        return None

    raw_score = scoring["score"]

    green_flags = job.get("green_flags", [])
    green_bonus = min(len(green_flags) * GREEN_FLAG_BONUS, GREEN_FLAG_BONUS_CAP)
    unconfirmed_penalty = UNCONFIRMED_DURATION_PENALTY if fmt == "contract_unconfirmed" else 0
    cap_bonus = CAP_EXEMPT_BONUS if (fmt == "fulltime" and cap_exempt) else 0

    final_score = max(0, min(100, raw_score + green_bonus + cap_bonus - unconfirmed_penalty))

    if scoring.get("gap_severity", "").lower().startswith("blocking"):
        print(f"    🚫 Blocking gap: {job.get('title')} @ {job.get('company')}")
        return None

    if final_score < MATCH_THRESHOLD:
        print(f"    📉 Below threshold ({final_score}%): {job.get('title')} @ {job.get('company')}")
        return None

    if fmt == "fulltime":
        h1b_status = ("✅ Verified Sponsor" if verified
                      else "⭐ Cap-Exempt (verify on myvisajobs.com)")
    else:
        h1b_status = "N/A (contract or internship)"

    print(f"    ✅ MATCH ({final_score}%) [T{tier}]: {job.get('title')} @ {job.get('company')}")

    return {
        "id":                    job["id"],
        "title":                 job["title"],
        "company":               job["company"],
        "location":              job["location"],
        "url":                   job["url"],
        "source":                job["source"],
        "posted_date":           job["posted_date"],
        "description_snippet":   (job["description"][:400] + "..."
                                  if len(job["description"]) > 400 else job["description"]),
        # Tier and format
        "tier":                  tier,
        "tier_label":            TIER_LABELS.get(tier, ""),
        "format":                fmt,
        "employment_type":       FORMAT_LABELS.get(fmt, fmt),
        "duration_confidence":   ("confirmed" if fmt == "contract_confirmed"
                                  else "unconfirmed" if fmt == "contract_unconfirmed"
                                  else "n/a"),
        "is_short_contract":     fmt in ("contract_confirmed", "contract_unconfirmed", "internship"),
        "location_note":         job.get("location_note", ""),
        "green_flags":           ", ".join(green_flags),
        # H-1B (Tier 4 only)
        "is_cap_exempt":         cap_exempt,
        "is_verified_h1b":       verified,
        "h1b_status":            h1b_status,
        "h1b_verify_url":        f"https://www.myvisajobs.com/Search/?cname={job.get('company','').replace(' ','+')}",
        # Scores
        "match_score":           final_score,
        "raw_score":             raw_score,
        "green_flag_bonus":      green_bonus,
        "unconfirmed_penalty":   unconfirmed_penalty,
        "cap_exempt_bonus":      cap_bonus,
        "role_fit":              scoring["role_fit"],
        "evidence_match":        scoring["evidence_match"],
        "level_fit":             scoring["level_fit"],
        "logistics_fit":         scoring["logistics_fit"],
        # Back-compat aliases for logger.py's existing columns
        "skill_match":           scoring["evidence_match"],
        "experience_fit":        scoring["level_fit"],
        "environment_fit":       scoring["logistics_fit"],
        "top_matching_skills":   scoring.get("evidence_cited", ""),
        # Detail
        "clusters_matched":      scoring.get("clusters_matched", ""),
        "evidence_cited":        scoring.get("evidence_cited", ""),
        "missing_skills":        scoring.get("missing_skills", ""),
        "gap_severity":          scoring.get("gap_severity", ""),
        "overqualification_risk": scoring.get("overqualification_risk", ""),
        "resume_version":        scoring.get("resume_version", "Program Management"),
        "resume_tailoring":      scoring.get("resume_tailoring", ""),
        "summary":               scoring.get("summary", ""),
        "evaluated_at":          __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def sort_matches(matches: list) -> list:
    """Strict tier sort, then fit score inside the tier."""
    return sorted(matches, key=lambda m: (m.get("tier", 9), -m.get("match_score", 0)))


def _try_fetch_description(url: str) -> str:
    if not url or not url.startswith("http"):
        return ""
    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=8)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:4000]
    except Exception:
        return ""
