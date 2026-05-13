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
    "Timestamp", "Title", "Company", "Location", "Source",
    "Employment Type", "H-1B Status", "Cap-Exempt?", "Verified H-1B Sponsor?",
    "Verify H-1B Link",
    "Match %", "Raw Score", "Cap Bonus",
    "Role Fit /30", "Skill Match /35", "Exp Fit /20", "Env Fit /15",
    "Matching Skills", "Missing Skills", "AI Summary",
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
        ws = sh.add_worksheet(title="Job Matches", rows=2000, cols=25)
        ws.append_row(SHEET_HEADERS)
        ws.format("A1:V1", {"textFormat": {"bold": True}, "backgroundColor": {"red":0.12,"green":0.23,"blue":0.37}})
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
        r.get("title",""),
        r.get("company",""),
        r.get("location",""),
        r.get("source",""),
        r.get("employment_type",""),           # Employment Type
        r.get("h1b_status",""),                # H-1B Status
        "✅ Yes" if r.get("is_cap_exempt") else "No",
        "✅ Verified" if r.get("is_verified_h1b") else ("⭐ Likely" if r.get("is_cap_exempt") else "No"),
        r.get("h1b_verify_url",""),            # Verify link
        r.get("match_score",""),
        r.get("raw_score",""),
        r.get("cap_exempt_bonus", 0),
        r.get("role_fit",""),
        r.get("skill_match",""),
        r.get("experience_fit",""),
        r.get("environment_fit",""),
        r.get("top_matching_skills",""),
        r.get("missing_skills",""),
        r.get("summary",""),
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


def send_daily_digest(results: list):
    if not results or not GMAIL_PASSWORD:
        return
    date_str = datetime.now().strftime("%B %d, %Y")
    subject  = f"📋 Daily Job Digest — {len(results)} matches | {date_str}"

    contracts  = [r for r in results if r.get("is_short_contract")]
    fulltime   = [r for r in results if not r.get("is_short_contract")]

    def make_rows(items):
        rows = ""
        for r in sorted(items, key=lambda x: x.get("match_score",0), reverse=True):
            h1b = r.get("h1b_status","")
            rows += f"""<tr>
              <td style="padding:7px;border-bottom:1px solid #e5e7eb;">
                <a href="{r.get('url','#')}" style="color:#1e3a5f;font-weight:bold;">{r.get('title','')}</a>
              </td>
              <td style="padding:7px;border-bottom:1px solid #e5e7eb;">{r.get('company','')}</td>
              <td style="padding:7px;border-bottom:1px solid #e5e7eb;">{r.get('location','')}</td>
              <td style="padding:7px;border-bottom:1px solid #e5e7eb;font-weight:bold;color:#1a7f3c;">{r.get('match_score','')}%</td>
              <td style="padding:7px;border-bottom:1px solid #e5e7eb;font-size:11px;">{h1b}</td>
            </tr>"""
        return rows

    html = f"""<div style="font-family:Arial,sans-serif;max-width:750px;">
      <h2 style="color:#1e3a5f;">📋 Daily Job Digest — {date_str}</h2>
      <p>{len(results)} total matches (≥80%) — {len(contracts)} contract, {len(fulltime)} full-time.</p>
      <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px;">
        <tr style="background:#1e3a5f;color:white;">
          <th style="padding:8px;text-align:left;">Title</th>
          <th style="padding:8px;text-align:left;">Company</th>
          <th style="padding:8px;text-align:left;">Location</th>
          <th style="padding:8px;text-align:left;">Match</th>
          <th style="padding:8px;text-align:left;">H-1B Status</th>
        </tr>
        {"<tr><td colspan='5' style='padding:8px;background:#f0fdf4;font-weight:bold;color:#166534;'>📋 Contract Roles (≤6 months)</td></tr>" if contracts else ""}
        {make_rows(contracts)}
        {"<tr><td colspan='5' style='padding:8px;background:#eff6ff;font-weight:bold;color:#1e3a5f;'>💼 Full-Time Roles (Cap-Exempt H-1B)</td></tr>" if fulltime else ""}
        {make_rows(fulltime)}
      </table>
      <p style="font-size:12px;color:#6b7280;">Full details in your Google Sheet.</p>
    </div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = NOTIFY_EMAIL
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(NOTIFY_EMAIL, GMAIL_PASSWORD)
            s.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"  📧 Digest sent: {subject}")
    except Exception as e:
        print(f"  ⚠️  Digest error: {e}")
