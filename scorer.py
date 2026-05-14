# =============================================================================
# scorer.py — Filter + Gemini scorer
#
# ACCEPTANCE RULES:
#   CONTRACT ≤ 6 months  → ACCEPT (CPT-eligible, no H-1B needed)
#   FULL-TIME at cap-exempt H-1B org → ACCEPT
#   Everything else      → REJECT
#
# Hard dealbreakers (clearance, unpaid, etc.) reject ALL types.
# =============================================================================

import re
import os
import time
from google import genai
from dotenv import load_dotenv
load_dotenv()

from config import (
    DEALBREAKER_KEYWORDS,
    REJECT_SENIORITY_KEYWORDS,
    SHORT_CONTRACT_PATTERNS,
    LONG_CONTRACT_PATTERNS,
    GENERIC_CONTRACT_KEYWORDS,
    FULLTIME_KEYWORDS,
    YOUR_SKILLS, YOUR_PROFILE,
    CAP_EXEMPT_EMPLOYER_KEYWORDS,
    VERIFIED_H1B_SPONSORS,
    CAP_EXEMPT_BONUS, MATCH_THRESHOLD,
)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Stops all scoring if daily quota is confirmed exhausted this run
DAILY_QUOTA_EXHAUSTED = False


# ─────────────────────────────────────────────────────────────
# EMPLOYMENT TYPE DETECTION
# Returns: "short_contract", "long_contract", "full-time", "unknown"
# ─────────────────────────────────────────────────────────────

def detect_employment_type(job: dict) -> str:
    text = (job.get("title","") + " " + job.get("description","") + " " + job.get("company","")).lower()

    # Check for explicit short contract (≤ 6 months) first
    for pattern in SHORT_CONTRACT_PATTERNS:
        if pattern.search(text):
            return "short_contract"

    # Check for explicit long contract (> 6 months)
    for pattern in LONG_CONTRACT_PATTERNS:
        if pattern.search(text):
            return "long_contract"

    # Generic contract keywords (duration unknown — treat conservatively as long)
    for kw in GENERIC_CONTRACT_KEYWORDS:
        if kw in text:
            return "long_contract"   # Unknown duration = treat as full-time rules

    # Full-time signals
    for kw in FULLTIME_KEYWORDS:
        if kw in text:
            return "full-time"

    return "unknown"   # No signal — treat as full-time (conservative)


# ─────────────────────────────────────────────────────────────
# CAP-EXEMPT EMPLOYER CHECKS
# ─────────────────────────────────────────────────────────────

def check_cap_exempt(job: dict) -> tuple[bool, bool]:
    """Returns (is_cap_exempt, is_verified_h1b_sponsor)."""
    company_lower = job.get("company", "").lower()
    desc_lower    = job.get("description", "").lower()[:600]

    cap_exempt = any(
        kw in company_lower or kw in desc_lower
        for kw in CAP_EXEMPT_EMPLOYER_KEYWORDS
    )
    verified = any(
        sponsor in company_lower
        for sponsor in VERIFIED_H1B_SPONSORS
    )
    return cap_exempt, verified


# ─────────────────────────────────────────────────────────────
# LOCAL FILTER
# ─────────────────────────────────────────────────────────────

def passes_local_filter(job: dict) -> tuple[bool, str, str, bool, bool]:
    """
    Returns (passes, rejection_reason, emp_type, is_cap_exempt, is_verified).
    """
    text = (job.get("title","") + " " + job.get("description","") + " " + job.get("company","")).lower()

    # 1. Hard dealbreakers — apply to ALL roles
    for kw in DEALBREAKER_KEYWORDS:
        if kw.lower() in text:
            return False, f"Dealbreaker: '{kw}'", "unknown", False, False

    # 2. Seniority — whole-word match
    padded_title = f" {job.get('title','').lower()} "
    for word in REJECT_SENIORITY_KEYWORDS:
        if f" {word} " in padded_title:
            return False, f"Too senior: '{word}' in title", "unknown", False, False

    # 3. Description length — if too short, try fetching from the URL
    if len(job.get("description", "")) < 50:
        fetched = _try_fetch_description(job.get("url", ""))
        if fetched and len(fetched) > 50:
            job["description"] = fetched
        elif len(job.get("description", "")) < 20:
            # Still nothing usable — use title + company as minimal description
            job["description"] = f"Job at {job.get('company','')}: {job.get('title','')}. Full description at {job.get('url','')}."

    # 4. Detect employment type
    emp_type = detect_employment_type(job)

    # 5. Short contract (≤ 6 months) → ACCEPT regardless of H-1B
    if emp_type == "short_contract":
        cap_exempt, verified = check_cap_exempt(job)
        return True, "", emp_type, cap_exempt, verified

    # 6. Full-time / long contract / unknown → require cap-exempt employer
    cap_exempt, verified = check_cap_exempt(job)
    if cap_exempt:
        return True, "", emp_type, cap_exempt, verified
    else:
        return False, "Full-time at non-cap-exempt org — no H-1B pathway", emp_type, False, False


# ─────────────────────────────────────────────────────────────
# GEMINI SCORING
# ─────────────────────────────────────────────────────────────

SCORING_PROMPT = """
You are a precise job match evaluator. Score honestly — 80+ means genuinely strong fit.

CANDIDATE PROFILE:
{profile}

JOB POSTING:
Title: {title}
Company: {company}
Location: {location}
Employment Type: {emp_type}
Description:
{description}

SCORING CRITERIA (0-100 total):

1. ROLE FIT (30 pts): Does title/scope match candidate experience level?
   Program/Project/Operations Manager or Coordinator → 25-30
   Analyst, Specialist, operational adjacent → 15-24
   Highly technical, clinical, legal → 0-14

2. SKILL MATCH (35 pts): How many candidate skills appear in JD?
   Skills to check: {skills}
   7+ match → 30-35 | 4-6 → 20-29 | 1-3 → 10-19 | 0 → 0-9

3. EXPERIENCE FIT (20 pts): Does required experience match ~6 years?
   0-5 yrs required → full | 5-7 yrs → partial | 8+ yrs → low

4. ENVIRONMENT FIT (15 pts):
   Higher ed, healthcare, research, consulting, nonprofits → 12-15
   Tech/SaaS operations → 8-11
   Highly specialized, no transferable context → 0-7

RULES:
- "No sponsorship" or "must be US citizen" → score 0
- Role requires skills completely absent from profile → cap at 50
- For short contract roles: do not penalize for no H-1B sponsorship

RESPOND IN EXACTLY THIS FORMAT, nothing else:
SCORE: [0-100]
ROLE_FIT: [0-30]
SKILL_MATCH: [0-35]
EXPERIENCE_FIT: [0-20]
ENVIRONMENT_FIT: [0-15]
TOP_MATCHING_SKILLS: [comma-separated]
MISSING_SKILLS: [comma-separated or "None"]
SUMMARY: [2-3 sentences]
"""

def score_with_gemini(job: dict, emp_type: str) -> dict | None:
    global DAILY_QUOTA_EXHAUSTED

    # If daily quota already confirmed exhausted, skip immediately
    if DAILY_QUOTA_EXHAUSTED:
        return None

    prompt = SCORING_PROMPT.format(
        profile=YOUR_PROFILE,
        title=job.get("title",""),
        company=job.get("company",""),
        location=job.get("location",""),
        emp_type=emp_type,
        description=job.get("description","")[:3000],
        skills=", ".join(YOUR_SKILLS),
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return parse_score(response.text.strip())

    except Exception as e:
        err = str(e)
        is_quota = "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower()

        if not is_quota:
            print(f"    ⚠️  Gemini error: {e}")
            return None

        # Distinguish daily limit vs per-minute limit
        is_daily = "PerDayPer" in err or "GenerateRequestsPerDay" in err

        if is_daily:
            # Daily quota gone — no point retrying ANY jobs this run
            DAILY_QUOTA_EXHAUSTED = True
            print(f"    🚫 Daily quota exhausted — skipping all remaining scoring this cycle.")
            print(f"       Quota resets at midnight UTC (8 PM Eastern).")
            print(f"       Or create a new API key at aistudio.google.com for fresh quota.")
            return None
        else:
            # Per-minute limit — wait and retry once
            print(f"    ⏳ Per-minute rate limit — waiting 65s...")
            time.sleep(65)
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                return parse_score(response.text.strip())
            except Exception as e2:
                err2 = str(e2)
                if "PerDayPer" in err2 or "GenerateRequestsPerDay" in err2:
                    DAILY_QUOTA_EXHAUSTED = True
                    print(f"    🚫 Daily quota exhausted — skipping remaining scoring.")
                else:
                    print(f"    ⚠️  Gemini retry failed: {e2}")
                return None

def parse_score(raw: str) -> dict:
    r = {"score":0,"role_fit":0,"skill_match":0,"experience_fit":0,
         "environment_fit":0,"top_matching_skills":"","missing_skills":"","summary":""}
    for line in raw.split("\n"):
        line = line.strip()
        def grab_int(key):
            try: return int(re.search(r'\d+', line).group())
            except: return 0
        if line.startswith("SCORE:"): r["score"] = grab_int("score")
        elif line.startswith("ROLE_FIT:"): r["role_fit"] = grab_int("role_fit")
        elif line.startswith("SKILL_MATCH:"): r["skill_match"] = grab_int("skill_match")
        elif line.startswith("EXPERIENCE_FIT:"): r["experience_fit"] = grab_int("experience_fit")
        elif line.startswith("ENVIRONMENT_FIT:"): r["environment_fit"] = grab_int("environment_fit")
        elif line.startswith("TOP_MATCHING_SKILLS:"): r["top_matching_skills"] = line.split(":",1)[1].strip()
        elif line.startswith("MISSING_SKILLS:"): r["missing_skills"] = line.split(":",1)[1].strip()
        elif line.startswith("SUMMARY:"): r["summary"] = line.split(":",1)[1].strip()
    return r


# ─────────────────────────────────────────────────────────────
# MASTER EVALUATOR
# ─────────────────────────────────────────────────────────────

def evaluate_job(job: dict) -> dict | None:
    passes, reason, emp_type, cap_exempt, verified = passes_local_filter(job)

    if not passes:
        print(f"    ❌ REJECTED ({reason}): {job.get('title')} @ {job.get('company')}")
        return None

    print(f"    🤖 Scoring [{emp_type}]: {job.get('title')} @ {job.get('company')}...")
    scoring = score_with_gemini(job, emp_type)
    if not scoring:
        return None

    raw_score   = scoring["score"]
    bonus       = CAP_EXEMPT_BONUS if cap_exempt and emp_type != "short_contract" else 0
    final_score = min(100, raw_score + bonus)

    if final_score < MATCH_THRESHOLD:
        print(f"    📉 Below threshold ({final_score}%): {job.get('title')} @ {job.get('company')}")
        return None

    # Build employment type label for display
    type_labels = {
        "short_contract": "Contract (≤6 months)",
        "long_contract":  "Full-time / Long Contract",
        "full-time":      "Full-time",
        "unknown":        "Full-time",
    }
    type_display = type_labels.get(emp_type, emp_type)

    # H-1B status label
    if emp_type == "short_contract":
        h1b_status = "N/A (Contract — CPT eligible)"
    elif verified:
        h1b_status = "✅ Verified Sponsor (2024-2026)"
    elif cap_exempt:
        h1b_status = "⭐ Cap-Exempt (verify on myvisajobs.com)"
    else:
        h1b_status = "❌ Not cap-exempt"

    print(f"    ✅ MATCH ({final_score}%) [{type_display}]: {job.get('title')} @ {job.get('company')}")

    return {
        # Job info
        "id":                   job["id"],
        "title":                job["title"],
        "company":              job["company"],
        "location":             job["location"],
        "url":                  job["url"],
        "source":               job["source"],
        "posted_date":          job["posted_date"],
        "description_snippet":  job["description"][:400] + "..." if len(job["description"]) > 400 else job["description"],
        # Employment type
        "employment_type":      type_display,
        "is_short_contract":    emp_type == "short_contract",
        # H-1B / cap-exempt
        "is_cap_exempt":        cap_exempt,
        "is_verified_h1b":      verified,
        "h1b_status":           h1b_status,
        "h1b_verify_url":       f"https://www.myvisajobs.com/Search/?cname={job.get('company','').replace(' ','+')}",
        # Scores
        "match_score":          final_score,
        "raw_score":            raw_score,
        "cap_exempt_bonus":     bonus,
        "role_fit":             scoring["role_fit"],
        "skill_match":          scoring["skill_match"],
        "experience_fit":       scoring["experience_fit"],
        "environment_fit":      scoring["environment_fit"],
        "top_matching_skills":  scoring["top_matching_skills"],
        "missing_skills":       scoring["missing_skills"],
        "summary":              scoring["summary"],
        "evaluated_at":         __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
