# =============================================================================
# scorer.py — Uses Google Gemini API (FREE) to score each job.
#
# Free tier limits (more than enough):
#   - 1,500 requests/day
#   - 15 requests/minute
#   - 1 million tokens/day
#
# Flow for each job:
#   Step 1: Fast local filter (dealbreakers + seniority + short contracts)
#   Step 2: Gemini gives a 0-100 match score with reasoning
#   Step 3: Cap-exempt bonus applied if applicable
#   Step 4: Only jobs >= 80% are returned for logging
# =============================================================================

import re
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

from config import (
    DEALBREAKER_KEYWORDS,
    SHORT_CONTRACT_PATTERNS,
    REJECT_SENIORITY_KEYWORDS,
    YOUR_SKILLS,
    YOUR_PROFILE,
    CAP_EXEMPT_EMPLOYER_KEYWORDS,
    CAP_EXEMPT_BONUS,
    MATCH_THRESHOLD,
)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")  # Free tier model


# ─────────────────────────────────────────────────────────────
# STEP 1: LOCAL FILTER (fast — no API call)
# ─────────────────────────────────────────────────────────────

def passes_local_filter(job: dict) -> tuple[bool, str]:
    """
    Returns (True, "") if job passes all local filters.
    Returns (False, reason) if it should be rejected without API call.
    """
    text_to_check = (
        job.get("title", "") + " " +
        job.get("description", "") + " " +
        job.get("company", "")
    ).lower()

    # 1. Dealbreaker keywords
    for kw in DEALBREAKER_KEYWORDS:
        if kw.lower() in text_to_check:
            return False, f"Dealbreaker keyword: '{kw}'"

    # 2. Short contract patterns
    for pattern in SHORT_CONTRACT_PATTERNS:
        if pattern.search(text_to_check):
            return False, "Short contract (< 6 months) detected"

    # 3. Too-senior title
    title_lower = job.get("title", "").lower()
    for word in REJECT_SENIORITY_KEYWORDS:
        if word in title_lower:
            return False, f"Seniority too high: '{word}' in title"

    # 4. Empty description (can't score it)
    if len(job.get("description", "")) < 50:
        return False, "Description too short to score"

    return True, ""


# ─────────────────────────────────────────────────────────────
# STEP 2: CAP-EXEMPT CHECK (local — no API call)
# ─────────────────────────────────────────────────────────────

def is_cap_exempt(job: dict) -> bool:
    """Check if the employer is likely a cap-exempt H-1B sponsor."""
    company_lower = job.get("company", "").lower()
    desc_lower = job.get("description", "").lower()[:500]  # Check first 500 chars

    for keyword in CAP_EXEMPT_EMPLOYER_KEYWORDS:
        if keyword in company_lower or keyword in desc_lower:
            return True
    return False


# ─────────────────────────────────────────────────────────────
# STEP 3: CLAUDE API SCORER
# ─────────────────────────────────────────────────────────────

SCORING_PROMPT = """
You are a precise, objective job match evaluator. Your job is to score how well a candidate's
profile matches a job description. Be honest and rigorous — do NOT inflate scores.

---
CANDIDATE PROFILE:
{profile}

---
JOB POSTING:
Title: {title}
Company: {company}
Location: {location}
Description:
{description}

---
SCORING INSTRUCTIONS:
Score from 0–100 based on these weighted criteria:

1. ROLE FIT (30 pts): Does the job title/scope match the candidate's experience level and type?
   - Program/Project/Operations Manager/Coordinator → strong fit
   - Analyst, Specialist → moderate fit
   - Highly technical, legal, clinical → low fit unless explicitly operational

2. SKILL MATCH (35 pts): How many of the candidate's core skills appear in the JD?
   Strong skills to look for: {skills}
   - 7+ skills match → 30-35 pts
   - 4-6 skills match → 20-29 pts
   - 1-3 skills match → 10-19 pts
   - 0 match → 0-9 pts

3. EXPERIENCE LEVEL FIT (20 pts): Does the JD's required years of experience fit?
   - Requires 0-5 years → full points
   - Requires 5-7 years → partial points (candidate has ~6 years total)
   - Requires 8+ years → low points

4. INDUSTRY / ENVIRONMENT FIT (15 pts): Does the work environment match?
   - Higher ed, healthcare, research, consulting, nonprofits → high fit
   - Tech/SaaS operations → moderate fit
   - Highly specialized industries with no transferable signal → low fit

IMPORTANT NOTES:
- The candidate is on F-1 CPT. If the JD says "no sponsorship" or "must be US citizen", return score 0.
- If the role requires skills completely absent from the candidate's profile, cap score at 50.
- Give the REAL score, not a generous one. 80+ should mean genuinely strong fit.

---
RESPOND IN EXACTLY THIS FORMAT (no other text):
SCORE: [number 0-100]
ROLE_FIT: [number 0-30]
SKILL_MATCH: [number 0-35]
EXPERIENCE_FIT: [number 0-20]
INDUSTRY_FIT: [number 0-15]
TOP_MATCHING_SKILLS: [comma-separated list of skills from JD that match candidate]
MISSING_SKILLS: [comma-separated list of key JD requirements candidate lacks]
SUMMARY: [2-3 sentences explaining the score and why this role is or isn't a fit]
"""


def score_with_gemini(job: dict) -> dict:
    """
    Call Gemini API (free) to score a job. Returns a scoring result dict.
    Respects the 15 requests/minute free tier limit automatically.
    """
    prompt = SCORING_PROMPT.format(
        profile=YOUR_PROFILE,
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        description=job.get("description", "")[:3000],
        skills=", ".join(YOUR_SKILLS),
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        return parse_score_response(raw)

    except Exception as e:
        error_str = str(e)
        # If we hit the rate limit (15 req/min), wait and retry once
        if "429" in error_str or "quota" in error_str.lower():
            print(f"    ⏳ Gemini rate limit hit — waiting 65 seconds...")
            time.sleep(65)
            try:
                response = model.generate_content(prompt)
                return parse_score_response(response.text.strip())
            except Exception as e2:
                print(f"    ⚠️  Gemini retry failed: {e2}")
                return None
        print(f"    ⚠️  Gemini API error: {e}")
        return None


def parse_score_response(raw: str) -> dict:
    """Parse Claude's structured response into a dict."""
    result = {
        "score": 0,
        "role_fit": 0,
        "skill_match": 0,
        "experience_fit": 0,
        "industry_fit": 0,
        "top_matching_skills": "",
        "missing_skills": "",
        "summary": "",
    }

    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                result["score"] = int(re.search(r'\d+', line).group())
            except:
                pass
        elif line.startswith("ROLE_FIT:"):
            try:
                result["role_fit"] = int(re.search(r'\d+', line).group())
            except:
                pass
        elif line.startswith("SKILL_MATCH:"):
            try:
                result["skill_match"] = int(re.search(r'\d+', line).group())
            except:
                pass
        elif line.startswith("EXPERIENCE_FIT:"):
            try:
                result["experience_fit"] = int(re.search(r'\d+', line).group())
            except:
                pass
        elif line.startswith("INDUSTRY_FIT:"):
            try:
                result["industry_fit"] = int(re.search(r'\d+', line).group())
            except:
                pass
        elif line.startswith("TOP_MATCHING_SKILLS:"):
            result["top_matching_skills"] = line.replace("TOP_MATCHING_SKILLS:", "").strip()
        elif line.startswith("MISSING_SKILLS:"):
            result["missing_skills"] = line.replace("MISSING_SKILLS:", "").strip()
        elif line.startswith("SUMMARY:"):
            result["summary"] = line.replace("SUMMARY:", "").strip()

    return result


# ─────────────────────────────────────────────────────────────
# MASTER SCORER — runs all steps on a single job
# ─────────────────────────────────────────────────────────────

def evaluate_job(job: dict) -> dict | None:
    """
    Run the full evaluation pipeline on one job.
    Returns a result dict if score >= threshold, else None.
    
    Result dict includes all job fields + scoring fields.
    """
    # Step 1: Local filter
    passes, reason = passes_local_filter(job)
    if not passes:
        print(f"    ❌ REJECTED ({reason}): {job.get('title')} @ {job.get('company')}")
        return None

    # Step 2: Cap-exempt check
    cap_exempt = is_cap_exempt(job)

    # Step 3: Score with Gemini
    print(f"    🤖 Scoring: {job.get('title')} @ {job.get('company')}...")
    scoring = score_with_gemini(job)
    if scoring is None:
        return None

    # Step 4: Apply cap-exempt bonus
    raw_score = scoring["score"]
    final_score = min(100, raw_score + CAP_EXEMPT_BONUS) if cap_exempt else raw_score

    if cap_exempt:
        print(f"    ⭐ Cap-exempt employer! +{CAP_EXEMPT_BONUS} bonus applied")

    # Step 5: Threshold check
    if final_score < MATCH_THRESHOLD:
        print(f"    📉 Below threshold ({final_score}%): {job.get('title')} @ {job.get('company')}")
        return None

    print(f"    ✅ MATCH ({final_score}%): {job.get('title')} @ {job.get('company')}")

    # Build full result
    return {
        # Job info
        "id":                 job["id"],
        "title":              job["title"],
        "company":            job["company"],
        "location":           job["location"],
        "url":                job["url"],
        "source":             job["source"],
        "posted_date":        job["posted_date"],
        "description":        job["description"][:500] + "..." if len(job["description"]) > 500 else job["description"],
        # Scores
        "match_score":        final_score,
        "raw_score":          raw_score,
        "cap_exempt_bonus":   CAP_EXEMPT_BONUS if cap_exempt else 0,
        "is_cap_exempt":      cap_exempt,
        "role_fit":           scoring["role_fit"],
        "skill_match":        scoring["skill_match"],
        "experience_fit":     scoring["experience_fit"],
        "industry_fit":       scoring["industry_fit"],
        "top_matching_skills": scoring["top_matching_skills"],
        "missing_skills":     scoring["missing_skills"],
        "summary":            scoring["summary"],
        # Metadata
        "evaluated_at":       __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
