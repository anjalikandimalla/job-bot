# =============================================================================
# logger.py — Logs every 80%+ match to Google Sheets AND emails you.
#
# Google Sheet columns (auto-created on first run):
#   Timestamp | Title | Company | Location | Source | Match % | Raw Score
#   Cap Exempt | Cap Bonus | Role Fit | Skill Match | Exp Fit | Industry Fit
#   Matching Skills | Missing Skills | Summary | Apply Link | Posted Date
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
    print("⚠️  gspread not installed. Google Sheets logging disabled.")

SHEET_ID        = os.getenv("GOOGLE_SHEET_ID", "")
NOTIFY_EMAIL    = os.getenv("NOTIFY_EMAIL", "anjalikandimalla81@gmail.com")
GMAIL_PASSWORD  = os.getenv("GMAIL_APP_PASSWORD", "")
CREDS_FILE      = os.path.join(os.path.dirname(__file__), "google_creds.json")

SHEET_HEADERS = [
    "Timestamp", "Title", "Company", "Location", "Source",
    "Match %", "Raw Score", "Cap Exempt?", "Cap Bonus",
    "Role Fit", "Skill Match", "Exp Fit", "Industry Fit",
    "Matching Skills", "Missing Skills", "Summary",
    "Apply Link", "Posted Date",
]


# ─────────────────────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────────────────────

_sheet_cache = None

def _get_sheet():
    """Connect to Google Sheets and return the worksheet."""
    global _sheet_cache
    if _sheet_cache is not None:
        return _sheet_cache

    if not GSPREAD_AVAILABLE:
        return None
    if not os.path.exists(CREDS_FILE):
        print("⚠️  google_creds.json not found. Sheets logging disabled.")
        return None
    if not SHEET_ID:
        print("⚠️  GOOGLE_SHEET_ID not set in .env. Sheets logging disabled.")
        return None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    # Use first sheet or create one named "Job Matches"
    try:
        ws = sh.worksheet("Job Matches")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Job Matches", rows=1000, cols=20)
        ws.append_row(SHEET_HEADERS)
        # Format header row (bold, frozen)
        ws.format("A1:R1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)

    _sheet_cache = ws
    return ws


def log_to_sheets(result: dict):
    """Append one job match to the Google Sheet."""
    ws = _get_sheet()
    if ws is None:
        print("  📋 [Sheets] Logging skipped (not configured)")
        return

    row = [
        result.get("evaluated_at", ""),
        result.get("title", ""),
        result.get("company", ""),
        result.get("location", ""),
        result.get("source", ""),
        result.get("match_score", ""),
        result.get("raw_score", ""),
        "YES ⭐" if result.get("is_cap_exempt") else "No",
        result.get("cap_exempt_bonus", 0),
        result.get("role_fit", ""),
        result.get("skill_match", ""),
        result.get("experience_fit", ""),
        result.get("industry_fit", ""),
        result.get("top_matching_skills", ""),
        result.get("missing_skills", ""),
        result.get("summary", ""),
        result.get("url", ""),
        result.get("posted_date", ""),
    ]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        print(f"  📊 [Sheets] Logged: {result['title']} @ {result['company']}")
    except Exception as e:
        print(f"  ⚠️  [Sheets] Error logging: {e}")


# ─────────────────────────────────────────────────────────────
# EMAIL NOTIFICATIONS
# ─────────────────────────────────────────────────────────────

def _build_job_email_html(result: dict) -> str:
    """Build a clean HTML email for one job match."""
    score = result.get("match_score", 0)
    raw   = result.get("raw_score", 0)
    bonus = result.get("cap_exempt_bonus", 0)
    cap   = result.get("is_cap_exempt", False)

    cap_badge = (
        '<span style="background:#1a7f3c;color:white;padding:2px 8px;border-radius:12px;'
        'font-size:12px;margin-left:8px;">⭐ CAP-EXEMPT H-1B SPONSOR</span>'
        if cap else ""
    )

    score_color = "#1a7f3c" if score >= 90 else "#2563eb" if score >= 80 else "#d97706"

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
      <div style="background:#1e3a5f;padding:16px 20px;">
        <h2 style="color:white;margin:0;font-size:18px;">🎯 New Job Match Found</h2>
        <p style="color:#93c5fd;margin:4px 0 0;font-size:13px;">{result.get('evaluated_at','')}</p>
      </div>

      <div style="padding:20px;">
        <h3 style="margin:0 0 4px;font-size:20px;">{result.get('title','')}{cap_badge}</h3>
        <p style="margin:0 0 16px;color:#6b7280;font-size:15px;">
          {result.get('company','')} &bull; {result.get('location','')} &bull; via {result.get('source','')}
        </p>

        <!-- Match Score -->
        <div style="background:#f8fafc;border-radius:8px;padding:14px;margin-bottom:16px;">
          <div style="font-size:36px;font-weight:bold;color:{score_color};">{score}% Match</div>
          {"<div style='font-size:12px;color:#6b7280;'>Raw: " + str(raw) + "% + " + str(bonus) + " cap-exempt bonus</div>" if bonus else ""}
        </div>

        <!-- Score Breakdown -->
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px;">
          <tr style="background:#f1f5f9;">
            <th style="padding:6px 10px;text-align:left;">Category</th>
            <th style="padding:6px 10px;text-align:left;">Score</th>
            <th style="padding:6px 10px;text-align:left;">Max</th>
          </tr>
          <tr><td style="padding:6px 10px;">Role Fit</td><td>{result.get('role_fit','')}</td><td>30</td></tr>
          <tr style="background:#f8fafc;"><td style="padding:6px 10px;">Skill Match</td><td>{result.get('skill_match','')}</td><td>35</td></tr>
          <tr><td style="padding:6px 10px;">Experience Fit</td><td>{result.get('experience_fit','')}</td><td>20</td></tr>
          <tr style="background:#f8fafc;"><td style="padding:6px 10px;">Industry Fit</td><td>{result.get('industry_fit','')}</td><td>15</td></tr>
        </table>

        <!-- Skills -->
        <div style="margin-bottom:12px;">
          <strong style="font-size:13px;">✅ Matching Skills:</strong>
          <p style="margin:4px 0;color:#166534;font-size:13px;">{result.get('top_matching_skills','')}</p>
        </div>
        <div style="margin-bottom:12px;">
          <strong style="font-size:13px;">⚠️ Missing Skills:</strong>
          <p style="margin:4px 0;color:#92400e;font-size:13px;">{result.get('missing_skills','') or 'None identified'}</p>
        </div>

        <!-- Summary -->
        <div style="background:#eff6ff;border-left:4px solid #2563eb;padding:10px 14px;margin-bottom:16px;border-radius:0 6px 6px 0;">
          <p style="margin:0;font-size:13px;">{result.get('summary','')}</p>
        </div>

        <!-- CTA -->
        <a href="{result.get('url','#')}" style="display:inline-block;background:#1e3a5f;color:white;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">
          View & Apply →
        </a>
        <p style="margin-top:8px;font-size:11px;color:#9ca3af;">Posted: {result.get('posted_date','')}</p>
      </div>
    </div>
    """


def send_match_email(result: dict):
    """Send an instant email alert for one job match."""
    if not GMAIL_PASSWORD or not NOTIFY_EMAIL:
        print("  📧 [Email] Not configured — skipping")
        return

    score = result.get("match_score", 0)
    subject = f"🎯 {score}% Match: {result.get('title','')} @ {result.get('company','')}"
    if result.get("is_cap_exempt"):
        subject = "⭐ " + subject

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = NOTIFY_EMAIL
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(_build_job_email_html(result), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(NOTIFY_EMAIL, GMAIL_PASSWORD)
            server.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"  📧 [Email] Sent: {subject}")
    except Exception as e:
        print(f"  ⚠️  [Email] Error: {e}")


def send_daily_digest(results: list[dict]):
    """Send a summary of all matches found in the past 24 hours."""
    if not results:
        print("  📧 [Digest] No matches to send.")
        return
    if not GMAIL_PASSWORD or not NOTIFY_EMAIL:
        return

    date_str = datetime.now().strftime("%B %d, %Y")
    subject  = f"📋 Daily Job Digest — {len(results)} matches | {date_str}"

    rows = ""
    for r in sorted(results, key=lambda x: x.get("match_score", 0), reverse=True):
        cap = "⭐" if r.get("is_cap_exempt") else ""
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
            <a href="{r.get('url','#')}" style="color:#1e3a5f;font-weight:bold;">{r.get('title','')}</a>
            {cap}
          </td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{r.get('company','')}</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{r.get('location','')}</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;font-weight:bold;color:#1a7f3c;">{r.get('match_score','')}%</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{r.get('source','')}</td>
        </tr>
        """

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
      <h2 style="color:#1e3a5f;">📋 Daily Job Match Digest — {date_str}</h2>
      <p>{len(results)} jobs matched your profile (80%+ score). ⭐ = cap-exempt H-1B sponsor.</p>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <tr style="background:#1e3a5f;color:white;">
          <th style="padding:8px;text-align:left;">Job Title</th>
          <th style="padding:8px;text-align:left;">Company</th>
          <th style="padding:8px;text-align:left;">Location</th>
          <th style="padding:8px;text-align:left;">Match</th>
          <th style="padding:8px;text-align:left;">Source</th>
        </tr>
        {rows}
      </table>
      <p style="margin-top:16px;font-size:12px;color:#6b7280;">
        Full details with resume/cover letter links in your Google Sheet.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = NOTIFY_EMAIL
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(NOTIFY_EMAIL, GMAIL_PASSWORD)
            server.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"  📧 [Digest] Sent: {subject}")
    except Exception as e:
        print(f"  ⚠️  [Digest] Error: {e}")
