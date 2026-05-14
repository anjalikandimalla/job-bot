# =============================================================================
# daily_log.py — Separate Google Sheets workbook: one tab per day
#
# Logs ALL relevant scraped jobs (title-filtered) to a dedicated sheet,
# regardless of whether Gemini scoring succeeds or fails.
#
# Sheet: "Job Bot — Daily Scrape Log"  (a DIFFERENT sheet from Job Bot Log)
# Tabs:  One tab per day, e.g. "2026-05-14"
#
# Columns:
#   Time | Title | Company | Location | Source | Employment Type
#   Cap-Exempt? | Score Status | Match % | AI Summary | Apply Link | Posted
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

SCRAPE_LOG_SHEET_ID = os.getenv("SCRAPE_LOG_SHEET_ID", "")
NOTIFY_EMAIL        = os.getenv("NOTIFY_EMAIL", "anjalikandimalla81@gmail.com")
GMAIL_PASSWORD      = os.getenv("GMAIL_APP_PASSWORD", "")
CREDS_FILE          = os.path.join(os.path.dirname(__file__), "google_creds.json")

HEADERS = [
    "Time Scraped", "Title", "Company", "Location", "Source",
    "Employment Type", "Cap-Exempt?", "Score Status",
    "Match %", "AI Summary", "Apply Link", "Posted Date",
]

_sheet_conn   = None   # gspread spreadsheet object
_tab_cache    = {}     # date string → worksheet object


def _connect():
    global _sheet_conn
    if _sheet_conn:
        return _sheet_conn
    if not GSPREAD_AVAILABLE:
        return None
    if not os.path.exists(CREDS_FILE):
        print("⚠️  [DailyLog] google_creds.json not found")
        return None
    if not SCRAPE_LOG_SHEET_ID:
        print("⚠️  [DailyLog] SCRAPE_LOG_SHEET_ID not set in .env / GitHub Secrets")
        return None
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
    gc = gspread.authorize(creds)
    _sheet_conn = gc.open_by_key(SCRAPE_LOG_SHEET_ID)
    return _sheet_conn


def _get_today_tab() -> "gspread.Worksheet | None":
    """Get or create today's tab (e.g. '2026-05-14')."""
    sh = _connect()
    if not sh:
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    if today in _tab_cache:
        return _tab_cache[today]

    # Find or create the tab
    try:
        ws = sh.worksheet(today)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=today, rows=2000, cols=len(HEADERS) + 1)
        ws.append_row(HEADERS)
        try:
            ws.format(f"A1:{chr(64+len(HEADERS))}1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.12, "green": 0.23, "blue": 0.37},
            })
            ws.freeze(rows=1)
        except Exception as fmt_err:
            print(f"  ⚠️  [DailyLog] Header formatting skipped: {fmt_err}")


    _tab_cache[today] = ws
    return ws


def log_scraped_job(job: dict, score_result: dict | None = None):
    """
    Log one job to today's tab.
    Call this for EVERY relevant job — scored or not.
    If score_result is None, the job appears as 'Pending score' or 'Quota exceeded'.
    """
    ws = _get_today_tab()
    if not ws:
        return

    now = datetime.now().strftime("%H:%M")

    # Employment type from scorer result or detect simply from job
    emp_type = "Unknown"
    if score_result:
        emp_type = score_result.get("employment_type", "Unknown")
    else:
        text = (job.get("title","") + " " + job.get("description","")).lower()
        if any(kw in text for kw in ["contract", "temporary", "temp ", "c2h", "c2c"]):
            emp_type = "Contract"
        elif any(kw in text for kw in ["full-time", "full time", "permanent"]):
            emp_type = "Full-time"

    # Score status
    if score_result:
        score_status = f"✅ Scored: {score_result.get('match_score',0)}%"
        match_pct    = score_result.get("match_score", "")
        summary      = score_result.get("summary", "")
    else:
        score_status = "⏸️ Quota exceeded — not scored"
        match_pct    = ""
        summary      = ""

    row = [
        now,
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("source", ""),
        emp_type,
        "✅ Yes" if job.get("cap_exempt") else "No",
        score_status,
        match_pct,
        summary,
        job.get("url", ""),
        job.get("posted_date", ""),
    ]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"  ⚠️  [DailyLog] Row error: {e}")


def batch_log_unscored(jobs: list[dict]):
    """
    Batch-log a list of unscored jobs efficiently (one API call).
    Used when quota is exhausted mid-run.
    """
    ws = _get_today_tab()
    if not ws or not jobs:
        return

    now = datetime.now().strftime("%H:%M")
    rows = []
    for job in jobs:
        text = (job.get("title","") + " " + job.get("description","")).lower()
        if any(kw in text for kw in ["contract", "temporary", "temp ", "c2h", "c2c"]):
            emp_type = "Contract"
        elif any(kw in text for kw in ["full-time", "full time", "permanent"]):
            emp_type = "Full-time"
        else:
            emp_type = "Unknown"

        rows.append([
            now,
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("source", ""),
            emp_type,
            "✅ Yes" if job.get("cap_exempt") else "No",
            "⏸️ Quota exceeded — not scored",
            "",   # match %
            "",   # summary
            job.get("url", ""),
            job.get("posted_date", ""),
        ])

    try:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"  📊 [DailyLog] Logged {len(rows)} unscored jobs to today's tab")
    except Exception as e:
        print(f"  ⚠️  [DailyLog] Batch log error: {e}")


def send_unscored_digest(jobs: list[dict], scored_count: int):
    """
    Email a digest of all relevant jobs when quota is exhausted.
    Shows how many were scored before quota ran out, and lists the rest.
    """
    if not GMAIL_PASSWORD or not NOTIFY_EMAIL or not jobs:
        return

    date_str   = datetime.now().strftime("%B %d, %Y")
    total      = scored_count + len(jobs)
    cap_jobs   = [j for j in jobs if j.get("cap_exempt")]
    other_jobs = [j for j in jobs if not j.get("cap_exempt")]

    def make_rows(items, bg="#ffffff"):
        rows = ""
        for j in items:
            cap_badge = "⭐ " if j.get("cap_exempt") else ""
            rows += f"""<tr style="background:{bg};">
              <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
                <a href="{j.get('url','#')}" style="color:#1e3a5f;font-weight:bold;text-decoration:none;">
                  {cap_badge}{j.get('title','')}
                </a>
              </td>
              <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{j.get('company','')}</td>
              <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{j.get('location','')}</td>
              <td style="padding:8px;border-bottom:1px solid #e5e7eb;font-size:11px;color:#6b7280;">{j.get('source','')}</td>
            </tr>"""
        return rows

    cap_section = ""
    if cap_jobs:
        cap_section = f"""
        <tr><td colspan="4" style="padding:8px;background:#eff6ff;font-weight:bold;color:#1e3a5f;">
          🏛️ Cap-Exempt H-1B Orgs ({len(cap_jobs)} jobs) — priority review
        </td></tr>
        {make_rows(cap_jobs, '#f8fafc')}"""

    other_section = ""
    if other_jobs:
        other_section = f"""
        <tr><td colspan="4" style="padding:8px;background:#f9fafb;font-weight:bold;color:#374151;">
          📋 Other Relevant Jobs ({len(other_jobs)} jobs)
        </td></tr>
        {make_rows(other_jobs)}"""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:750px;margin:0 auto;">
      <div style="background:#92400e;padding:16px 20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;font-size:18px;">⏸️ API Quota Reached — Unscored Job List</h2>
        <p style="color:#fde68a;margin:4px 0 0;font-size:13px;">{date_str}</p>
      </div>
      <div style="padding:16px 20px;background:#fffbeb;border:1px solid #fde68a;">
        <p style="margin:0;font-size:14px;">
          The Gemini API daily quota was reached after scoring <strong>{scored_count} of {total}</strong> relevant jobs.
          The <strong>{len(jobs)} unscored jobs</strong> below passed the title filter and are worth reviewing manually.
          Full details are in your <strong>Daily Scrape Log</strong> Google Sheet (today's tab).
        </p>
        <p style="margin:8px 0 0;font-size:12px;color:#92400e;">
          ⭐ = Cap-exempt H-1B org (university, hospital, nonprofit) — these are highest priority.
          Quota resets at midnight UTC (8 PM Eastern).
        </p>
      </div>

      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <tr style="background:#1e3a5f;color:white;">
          <th style="padding:8px;text-align:left;">Job Title</th>
          <th style="padding:8px;text-align:left;">Company</th>
          <th style="padding:8px;text-align:left;">Location</th>
          <th style="padding:8px;text-align:left;">Source</th>
        </tr>
        {cap_section}
        {other_section}
      </table>

      <p style="margin-top:16px;font-size:12px;color:#6b7280;">
        All jobs are also saved to your Daily Scrape Log sheet.
        Scored matches (≥80%) are in your main Job Bot Log sheet.
      </p>
    </div>
    """

    subject = f"⏸️ Quota reached — {len(jobs)} unscored jobs | {date_str}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = NOTIFY_EMAIL
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(NOTIFY_EMAIL, GMAIL_PASSWORD)
            s.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"  📧 [DailyLog] Unscored digest sent: {len(jobs)} jobs")
    except Exception as e:
        print(f"  ⚠️  [DailyLog] Email error: {e}")
