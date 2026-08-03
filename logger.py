# =============================================================================
# logger.py — Google Sheets logger + email notifier
#
# Google Sheet columns:
#   Timestamp | Title | Company | Location | Source | Employment Type
#   H-1B Status | Cap-Exempt? | Verified Sponsor? | H-1B Check Link
#   Match % | Raw Score | Cap Bonus | Role Fit | Skill Match | Exp Fit
#   Environment Fit | Matching Skills | Missing Skills | Summary
#   Apply Link | Posted Date
# =============================================================================

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    print("⚠️  gspread not installed.")

SHEET_ID       = os.getenv("GOOGLE_SHEET_ID", "")
NOTIFY_EMAIL   = os.getenv("NOTIFY_EMAIL", "anjalikandimalla81@gmail.com")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
CREDS_FILE     = os.path.join(os.path.dirname(__file__), "google_creds.json")

SHEET_HEADERS = [
    "Timestamp", "Tier", "Title", "Company", "Location", "Source",
    "Format", "Duration", "Green Flags", "Location Note",
    "Match %", "Raw Score", "Green Bonus", "Unconfirmed Penalty",
    "Role Fit /35", "Evidence Match /35", "Level Fit /15", "Logistics Fit /15",
    "Clusters Matched", "Evidence Cited", "Missing Skills",
    "Gap Severity", "Overqualification Risk",
    "Suggested Resume", "Tailoring Notes",
    "AI Summary",
    "H-1B Status", "Verify H-1B Link",
    "Apply Link", "Posted Date",
]

_sheet_cache = None

def _get_sheet():
    global _sheet_cache
    if _sheet_cache:
        return _sheet_cache
    if not GSPREAD_AVAILABLE or not os.path.exists(CREDS_FILE) or not SHEET_ID:
        return None
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet("Job Matches")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Job Matches", rows=2000, cols=32)
        ws.append_row(SHEET_HEADERS)
        ws.format("A1:AD1", {"textFormat": {"bold": True}, "backgroundColor": {"red":0.12,"green":0.23,"blue":0.37}})
        ws.freeze(rows=1)
    _sheet_cache = ws
    return ws


def log_to_sheets(r: dict):
    ws = _get_sheet()
    if not ws:
        print("  📋 [Sheets] Not configured — skipping")
        return

    # Color-code the employment type cell
    row = [
        r.get("evaluated_at",""),
        r.get("tier_label",""),
        r.get("title",""),
        r.get("company",""),
        r.get("location",""),
        r.get("source",""),
        r.get("employment_type",""),
        r.get("duration_confidence",""),
        r.get("green_flags",""),
        r.get("location_note",""),
        r.get("match_score",""),
        r.get("raw_score",""),
        r.get("green_flag_bonus", 0),
        r.get("unconfirmed_penalty", 0),
        r.get("role_fit",""),
        r.get("evidence_match",""),
        r.get("level_fit",""),
        r.get("logistics_fit",""),
        r.get("clusters_matched",""),
        r.get("evidence_cited",""),
        r.get("missing_skills",""),
        r.get("gap_severity",""),
        r.get("overqualification_risk",""),
        r.get("resume_version",""),
        r.get("resume_tailoring",""),
        r.get("summary",""),
        r.get("h1b_status",""),
        r.get("h1b_verify_url",""),
        r.get("url",""),
        r.get("posted_date",""),
    ]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        print(f"  📊 [Sheets] Logged: {r['title']} @ {r['company']}")
    except Exception as e:
        print(f"  ⚠️  [Sheets] Error: {e}")


def _build_email_html(r: dict) -> str:
    score    = r.get("match_score", 0)
    emp_type = r.get("employment_type", "")
    h1b      = r.get("h1b_status", "")
    is_contract = r.get("is_short_contract", False)

    score_color = "#1a7f3c" if score >= 90 else "#2563eb" if score >= 80 else "#d97706"

    # Employment type badge
    if is_contract:
        type_badge = '<span style="background:#7c3aed;color:white;padding:2px 10px;border-radius:12px;font-size:12px;">📋 CONTRACT ≤6mo</span>'
    else:
        type_badge = '<span style="background:#1e3a5f;color:white;padding:2px 10px;border-radius:12px;font-size:12px;">💼 FULL-TIME</span>'

    # H-1B badge
    if is_contract:
        h1b_badge = '<span style="background:#6b7280;color:white;padding:2px 8px;border-radius:12px;font-size:11px;">CPT Eligible</span>'
    elif r.get("is_verified_h1b"):
        h1b_badge = '<span style="background:#1a7f3c;color:white;padding:2px 8px;border-radius:12px;font-size:11px;">✅ Verified H-1B Sponsor</span>'
    elif r.get("is_cap_exempt"):
        h1b_badge = '<span style="background:#d97706;color:white;padding:2px 8px;border-radius:12px;font-size:11px;">⭐ Cap-Exempt</span>'
    else:
        h1b_badge = ""

    bonus_row = ""
    if r.get("cap_exempt_bonus", 0) > 0:
        bonus_row = f"<div style='font-size:12px;color:#6b7280;'>Raw: {r.get('raw_score')}% + {r.get('cap_exempt_bonus')} cap-exempt bonus</div>"

    verify_link = ""
    if not is_contract:
        verify_link = f'<p style="font-size:12px;margin-top:8px;"><a href="{r.get("h1b_verify_url","#")}" style="color:#2563eb;">🔍 Verify H-1B sponsorship history on myvisajobs.com →</a></p>'

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
      <div style="background:#1e3a5f;padding:16px 20px;">
        <h2 style="color:white;margin:0;font-size:18px;">🎯 New Job Match</h2>
        <p style="color:#93c5fd;margin:4px 0 0;font-size:12px;">{r.get('evaluated_at','')}</p>
      </div>
      <div style="padding:20px;">
        <div style="margin-bottom:12px;">{type_badge}&nbsp;&nbsp;{h1b_badge}</div>
        <h3 style="margin:0 0 4px;font-size:20px;">{r.get('title','')}</h3>
        <p style="margin:0 0 16px;color:#6b7280;">{r.get('company','')} &bull; {r.get('location','')} &bull; via {r.get('source','')}</p>

        <div style="background:#f8fafc;border-radius:8px;padding:14px;margin-bottom:16px;">
          <div style="font-size:36px;font-weight:bold;color:{score_color};">{score}% Match</div>
          {bonus_row}
        </div>

        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px;">
          <tr style="background:#f1f5f9;">
            <th style="padding:6px 10px;text-align:left;">Category</th>
            <th style="padding:6px 10px;">Score</th>
            <th style="padding:6px 10px;">Max</th>
          </tr>
          <tr><td style="padding:6px 10px;">Role Fit</td><td style="text-align:center;">{r.get('role_fit')}</td><td style="text-align:center;">30</td></tr>
          <tr style="background:#f8fafc;"><td style="padding:6px 10px;">Skill Match</td><td style="text-align:center;">{r.get('skill_match')}</td><td style="text-align:center;">35</td></tr>
          <tr><td style="padding:6px 10px;">Experience Fit</td><td style="text-align:center;">{r.get('experience_fit')}</td><td style="text-align:center;">20</td></tr>
          <tr style="background:#f8fafc;"><td style="padding:6px 10px;">Environment Fit</td><td style="text-align:center;">{r.get('environment_fit')}</td><td style="text-align:center;">15</td></tr>
        </table>

        <div style="margin-bottom:10px;">
          <strong style="font-size:13px;">✅ Matching Skills:</strong>
          <p style="margin:4px 0;color:#166534;font-size:13px;">{r.get('top_matching_skills','')}</p>
        </div>
        <div style="margin-bottom:12px;">
          <strong style="font-size:13px;">⚠️ Missing Skills:</strong>
          <p style="margin:4px 0;color:#92400e;font-size:13px;">{r.get('missing_skills','') or 'None'}</p>
        </div>

        <div style="background:#eff6ff;border-left:4px solid #2563eb;padding:10px 14px;margin-bottom:4px;border-radius:0 6px 6px 0;">
          <p style="margin:0;font-size:13px;">{r.get('summary','')}</p>
        </div>
        {verify_link}

        <a href="{r.get('url','#')}" style="display:inline-block;margin-top:16px;background:#1e3a5f;color:white;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">
          View & Apply →
        </a>
        <p style="margin-top:8px;font-size:11px;color:#9ca3af;">Posted: {r.get('posted_date','')}</p>
      </div>
    </div>
    """


def send_match_email(r: dict):
    if not GMAIL_PASSWORD or not NOTIFY_EMAIL:
        return
    is_contract  = r.get("is_short_contract", False)
    is_verified  = r.get("is_verified_h1b", False)
    prefix = "📋" if is_contract else ("✅" if is_verified else "⭐")
    subject = f"{prefix} {r.get('match_score')}% Match: {r.get('title')} @ {r.get('company')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = NOTIFY_EMAIL
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(_build_email_html(r), "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(NOTIFY_EMAIL, GMAIL_PASSWORD)
            s.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"  📧 Sent: {subject}")
    except Exception as e:
        print(f"  ⚠️  Email error: {e}")


def send_digest_email(results: list):
    """
    Send a 3-hour digest of the top-N matches.
    results should already be sorted by score desc and sliced to top N.
    """
    if not results or not GMAIL_PASSWORD:
        return

    now_str  = datetime.now().strftime("%B %d, %Y %I:%M %p")
    contracts = [r for r in results if r.get("is_short_contract")]
    fulltime  = [r for r in results if not r.get("is_short_contract")]

    def score_color(s):
        if s >= 90: return "#1a7f3c"
        if s >= 85: return "#2563eb"
        return "#d97706"

    def h1b_badge(r):
        if r.get("is_short_contract"):
            return "<span style='background:#7c3aed;color:white;padding:1px 7px;border-radius:10px;font-size:10px;'>CPT</span>"
        if r.get("is_verified_h1b"):
            return "<span style='background:#1a7f3c;color:white;padding:1px 7px;border-radius:10px;font-size:10px;'>✅ H-1B</span>"
        if r.get("is_cap_exempt"):
            return "<span style='background:#d97706;color:white;padding:1px 7px;border-radius:10px;font-size:10px;'>⭐ Cap-Exempt</span>"
        return ""

    def make_card(r, rank):
        sc = r.get("match_score", 0)
        missing = r.get("missing_skills","") or "None"
        matching = r.get("top_matching_skills","") or ""
        resume = r.get("resume_version","Program Management")
        tailoring = r.get("resume_tailoring","")
        resume_color = "#7c3aed" if "Operations" in resume else "#1e3a5f"
        return f"""
        <tr>
          <td style="padding:14px;border-bottom:2px solid #e5e7eb;vertical-align:top;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
              <span style="font-size:18px;font-weight:bold;color:#6b7280;">#{rank}</span>
              <span style="font-size:22px;font-weight:bold;color:{score_color(sc)};">{sc}%</span>
              {h1b_badge(r)}
            </div>
            <div style="font-size:15px;font-weight:bold;margin-bottom:2px;">
              <a href="{r.get('url','#')}" style="color:#1e3a5f;text-decoration:none;">{r.get('title','')}</a>
            </div>
            <div style="color:#6b7280;font-size:13px;margin-bottom:6px;">
              {r.get('company','')} &bull; {r.get('location','')} &bull; {r.get('employment_type','')}
            </div>
            <div style="background:#f9fafb;border-left:3px solid {resume_color};padding:6px 10px;margin:6px 0;font-size:12px;">
              <strong style="color:{resume_color};">📄 Use: {resume} resume</strong>
              {f'<div style="color:#374151;margin-top:3px;">{tailoring}</div>' if tailoring else ""}
            </div>
            <div style="font-size:12px;color:#166534;margin-bottom:3px;">✅ Matching: {matching}</div>
            {f'<div style="font-size:12px;color:#92400e;">⚠️ Missing: {missing}</div>' if missing and missing != "None" else ""}
            <div style="font-size:12px;color:#374151;margin-top:6px;font-style:italic;">{r.get('summary','')}</div>
            <div style="margin-top:8px;">
              <a href="{r.get('url','#')}" style="background:#1e3a5f;color:white;padding:5px 14px;border-radius:5px;text-decoration:none;font-size:12px;">Apply →</a>
              &nbsp;<span style="font-size:11px;color:#9ca3af;">Posted: {r.get('posted_date','')}</span>
            </div>
          </td>
        </tr>"""

    all_cards = ""
    if fulltime:
        all_cards += f"<tr><td style='padding:10px;background:#eff6ff;font-weight:bold;color:#1e3a5f;font-size:14px;'>💼 Full-Time Cap-Exempt Roles ({len(fulltime)})</td></tr>"
        for i, r in enumerate(fulltime, 1):
            all_cards += make_card(r, i)
    if contracts:
        all_cards += f"<tr><td style='padding:10px;background:#f0fdf4;font-weight:bold;color:#166534;font-size:14px;'>📋 Contract Roles ≤6 months ({len(contracts)})</td></tr>"
        for i, r in enumerate(contracts, 1):
            all_cards += make_card(r, i)

    html = f"""<div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;">
      <div style="background:#1e3a5f;padding:16px 20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;font-size:20px;">🎯 Top {len(results)} Job Matches</h2>
        <p style="color:#93c5fd;margin:4px 0 0;font-size:13px;">{now_str} &bull; Sorted by match score</p>
      </div>
      <div style="background:#f8fafc;padding:10px 20px;border:1px solid #e2e8f0;border-top:0;">
        <p style="margin:0;font-size:13px;color:#374151;">
          {len(results)} matches from the past 3 hours &bull;
          {len(fulltime)} full-time cap-exempt &bull; {len(contracts)} contract &bull;
          All jobs scored ≥80% against your profile.
          Full details in your <a href="#" style="color:#2563eb;">Job Bot Log</a> Google Sheet.
        </p>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        {all_cards}
      </table>
      <div style="padding:12px 20px;background:#f8fafc;border:1px solid #e2e8f0;border-top:0;border-radius:0 0 8px 8px;font-size:11px;color:#9ca3af;">
        Next digest in ~3 hours. Only jobs posted in the last 24 hours are scored.
      </div>
    </div>"""

    subject = f"🎯 {len(results)} Job Matches | {datetime.now().strftime('%b %d %I:%M %p')}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = NOTIFY_EMAIL
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(NOTIFY_EMAIL, GMAIL_PASSWORD)
            s.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"  📧 Sent: {subject}")
    except Exception as e:
        print(f"  ⚠️  Digest email error: {e}")


# Keep old name as alias so nothing breaks if called from elsewhere
def send_daily_digest(results): send_digest_email(results)
