# =============================================================================
# email_tracker.py — Job Application Tracker
#
# Scans ALL Gmail for job-related emails. Cross-references with the Job Bot
# Log sheet to pull description, skills match paragraph, and apply link when
# they aren't in the email. Applies color coding for rejected applications.
#
# Sheet columns (in order):
#   Company | Role | Apply / JD Link | Description | Why I'm a Fit
#   Date Applied | Date Last Updated | Current Status | Status History | Notes
#
# Color coding:
#   Rejected  → light red background
#   Offer     → light green background
#   Interview → light blue background
#   Applied   → white (default)
# =============================================================================

import imaplib
import email
import email.header
import os
import re
import time
import hashlib
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
load_dotenv()

GMAIL_USER       = os.getenv("NOTIFY_EMAIL", "anjalikandimalla25@gmail.com")
GMAIL_PASSWORD   = os.getenv("GMAIL_APP_PASSWORD", "")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
TRACKER_SHEET_ID = os.getenv("TRACKER_SHEET_ID", "")
JOB_LOG_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")   # existing Job Bot Log
CREDS_FILE       = os.path.join(os.path.dirname(__file__), "google_creds.json")

LOOKBACK_DAYS = 90
SHEET_TAB     = "Applications"

# ─────────────────────────────────────────────────────────────
# COLUMN DEFINITIONS
# ─────────────────────────────────────────────────────────────

HEADERS = [
    "Company",           # A
    "Role",              # B
    "Apply / JD Link",   # C
    "Description",       # D
    "Why I'm a Fit",     # E  ← AI summary paragraph from scorer
    "Date Applied",      # F
    "Last Updated",      # G
    "Status",            # H
    "Status History",    # I
    "Source",            # J
    "Notes",             # K
    "_email_id",         # L  ← hidden dedup key (last column)
]

# Column letters for formatting
COL = {h: chr(65 + i) for i, h in enumerate(HEADERS)}
LAST_COL = COL["_email_id"]

# Status → background color (RGB 0-1 scale)
STATUS_COLORS = {
    "Rejected":             {"red": 1.0,  "green": 0.85, "blue": 0.85},
    "Offer Received":       {"red": 0.85, "green": 1.0,  "blue": 0.85},
    "Interview Scheduled":  {"red": 0.85, "green": 0.93, "blue": 1.0},
    "Phone Screen Scheduled":{"red": 0.9, "green": 0.95, "blue": 1.0},
    "Assessment Sent":      {"red": 1.0,  "green": 0.95, "blue": 0.8},
    "Applied":              None,   # white / no fill
    "Recruiter Outreach":   {"red": 0.95, "green": 0.9,  "blue": 1.0},
    "Unknown":              None,
}

# ─────────────────────────────────────────────────────────────
# EMAIL DETECTION KEYWORDS
# ─────────────────────────────────────────────────────────────

JOB_SUBJECT_KEYWORDS = [
    "application received", "application confirmation", "thank you for applying",
    "thanks for applying", "we received your application", "successfully submitted",
    "your application to", "application for", "applied for",
    "interview", "phone screen", "video interview", "zoom interview",
    "schedule a call", "schedule time", "availability for", "meet with",
    "hiring manager", "assessment", "take-home", "skills test", "next steps",
    "offer letter", "offer of employment", "pleased to offer", "job offer",
    "congratulations", "unfortunately", "not moving forward", "other candidates",
    "not selected", "decided to move", "not a fit",
    "exciting opportunity", "i came across your profile", "your background",
    "open to new opportunities", "job opportunity", "career opportunity",
    "position", "role at", "hiring for",
]

JOB_SENDER_DOMAINS = [
    "greenhouse.io", "lever.co", "workday.com", "myworkdayjobs.com",
    "icims.com", "taleo.net", "jobvite.com", "bamboohr.com",
    "smartrecruiters.com", "recruitee.com", "ashbyhq.com",
    "linkedin.com", "indeed.com", "ziprecruiter.com",
    "careers", "talent", "recruiting", "hr", "noreply", "no-reply", "jobs", "hiring",
]

BODY_SIGNALS = [
    "your application", "applied for", "position of", "role of",
    "interview", "offer letter", "hiring manager", "recruiter", "talent acquisition",
]

def status_from_email(subject: str, body: str) -> str:
    s = (subject + " " + body).lower()
    if any(x in s for x in ["offer letter", "pleased to offer", "we would like to offer", "job offer", "formal offer"]):
        return "Offer Received"
    if any(x in s for x in ["unfortunately", "not moving forward", "not selected", "not a fit", "other candidates", "decided not to", "regret to inform", "will not be moving", "not proceed"]):
        return "Rejected"
    if any(x in s for x in ["phone screen", "phone call", "introductory call", "initial call"]):
        return "Phone Screen Scheduled"
    if any(x in s for x in ["interview", "zoom", "teams meeting", "google meet", "schedule a time", "availability"]):
        return "Interview Scheduled"
    if any(x in s for x in ["assessment", "take-home", "coding challenge", "skills test", "technical test", "assignment"]):
        return "Assessment Sent"
    if any(x in s for x in ["application received", "thank you for applying", "successfully submitted", "we received your application"]):
        return "Applied"
    if any(x in s for x in ["exciting opportunity", "came across your profile", "your background", "open to new opportunities"]):
        return "Recruiter Outreach"
    return "Unknown"

def is_job_related(subject: str, sender: str, body_preview: str) -> bool:
    sl = subject.lower()
    snl = sender.lower()
    bl = body_preview.lower()
    if any(kw in sl for kw in JOB_SUBJECT_KEYWORDS):
        return True
    if any(d in snl for d in JOB_SENDER_DOMAINS):
        return True
    if any(sig in bl for sig in BODY_SIGNALS):
        return True
    return False

# ─────────────────────────────────────────────────────────────
# GEMINI
# ─────────────────────────────────────────────────────────────

try:
    from google import genai
    _client = genai.Client(api_key=GEMINI_API_KEY)
    GEMINI_OK = True
except Exception:
    GEMINI_OK = False

EXTRACT_PROMPT = """
Parse this job-related email and extract structured information.

FROM: {sender}
SUBJECT: {subject}
DATE: {date}
BODY:
{body}

Extract:
COMPANY: [employer name — not a recruiter firm unless they ARE the employer]
ROLE: [exact job title]
APPLY_LINK: [any URL in the email linking to the job posting or application, or "None"]
NOTES: [recruiter name, salary, remote/hybrid, deadline, or any other key detail — or "None"]
IS_JOB_EMAIL: [YES or NO]

Respond in exactly this format, one field per line. If unknown, write "Unknown".
COMPANY: ...
ROLE: ...
APPLY_LINK: ...
NOTES: ...
IS_JOB_EMAIL: ...
"""

def extract_with_gemini(sender, subject, date, body) -> dict:
    if not GEMINI_OK:
        return {}
    try:
        resp = _client.models.generate_content(
            model="gemini-2.5-flash",
            contents=EXTRACT_PROMPT.format(
                sender=sender, subject=subject, date=date, body=body[:2500]
            ),
        )
        result = {}
        for line in resp.text.strip().split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                result[k.strip()] = v.strip()
        return result
    except Exception as e:
        print(f"  ⚠️  Gemini: {e}")
        return {}

# ─────────────────────────────────────────────────────────────
# JOB BOT LOG CROSS-REFERENCE
# Loads the existing Job Bot Log sheet to pull description,
# "why I'm a fit" paragraph, and apply link by company + role.
# ─────────────────────────────────────────────────────────────

_job_log_cache = None   # list of row dicts

def load_job_log() -> list:
    global _job_log_cache
    if _job_log_cache is not None:
        return _job_log_cache

    if not JOB_LOG_SHEET_ID:
        _job_log_cache = []
        return []
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        creds  = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
        gc     = gspread.authorize(creds)
        sh     = gc.open_by_key(JOB_LOG_SHEET_ID)
        ws     = sh.sheet1
        rows   = ws.get_all_records()
        _job_log_cache = rows
        print(f"  📊 Loaded {len(rows)} rows from Job Bot Log for cross-reference")
        return rows
    except Exception as e:
        print(f"  ⚠️  Could not load Job Bot Log: {e}")
        _job_log_cache = []
        return []


def lookup_from_job_log(company: str, role: str) -> dict:
    """
    Find a matching row in the Job Bot Log by company + role (fuzzy match).
    Returns dict with apply_link, description, fit_paragraph, or empty strings.
    """
    rows = load_job_log()
    if not rows:
        return {}

    company_l = company.lower().strip()
    role_l    = role.lower().strip()

    best = None
    for row in rows:
        row_company = str(row.get("Company", "")).lower()
        row_title   = str(row.get("Title", "")).lower()

        # Match if company and role both partially overlap
        company_match = company_l in row_company or row_company in company_l
        role_match    = (role_l in row_title or row_title in role_l or
                         _word_overlap(role_l, row_title) >= 2)

        if company_match and role_match:
            best = row
            break   # Take first match

    if not best:
        return {}

    # Build description from matching + missing skills
    matching = best.get("Matching Skills", "")
    missing  = best.get("Missing Skills", "")
    summary  = best.get("AI Summary", "")
    tailoring = best.get("Tailoring Notes", "")

    # "Why I'm a fit" paragraph: AI Summary + tailoring notes
    fit_parts = []
    if summary:
        fit_parts.append(summary)
    if tailoring:
        fit_parts.append(tailoring)
    fit_paragraph = " ".join(fit_parts) if fit_parts else ""

    # Description: matching skills as a sentence
    desc = ""
    if matching:
        desc = f"Key matching skills: {matching}."
        if missing and missing.lower() not in ("none", "n/a", ""):
            desc += f" Gaps to address: {missing}."

    return {
        "apply_link":    best.get("Apply Link", ""),
        "description":   desc,
        "fit_paragraph": fit_paragraph,
        "match_score":   best.get("Match %", ""),
    }


def _word_overlap(a: str, b: str) -> int:
    """Count shared words between two strings (ignoring short words)."""
    stop = {"the", "a", "an", "of", "in", "at", "for", "and", "or", "to", "is"}
    wa = set(a.split()) - stop
    wb = set(b.split()) - stop
    return len(wa & wb)

# ─────────────────────────────────────────────────────────────
# GOOGLE SHEETS — TRACKER
# ─────────────────────────────────────────────────────────────

_ws = None

def _get_ws():
    global _ws
    if _ws:
        return _ws
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        creds  = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
        gc     = gspread.authorize(creds)
        sh     = gc.open_by_key(TRACKER_SHEET_ID)
        try:
            ws = sh.worksheet(SHEET_TAB)
        except Exception:
            ws = sh.add_worksheet(title=SHEET_TAB, rows=2000, cols=len(HEADERS) + 1)
            ws.append_row(HEADERS)
            _format_header(sh, ws)
        _ws = ws
        return ws
    except Exception as e:
        print(f"  ⚠️  Sheet connect error: {e}")
        return None


def _format_header(sh, ws):
    """Bold navy header, freeze row 1, hide the _email_id column."""
    try:
        ws.format(f"A1:{LAST_COL}1", {
            "textFormat": {"bold": True, "foregroundColor": {"red":1,"green":1,"blue":1}},
            "backgroundColor": {"red": 0.12, "green": 0.23, "blue": 0.37},
        })
        ws.freeze(rows=1)
        # Hide the last column (_email_id) — it's just a dedup key
        col_idx = len(HEADERS) - 1   # 0-indexed
        sh.batch_update({"requests": [{
            "updateDimensionProperties": {
                "range": {"sheetId": ws.id, "dimension": "COLUMNS",
                          "startIndex": col_idx, "endIndex": col_idx + 1},
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser"
            }
        }]})
    except Exception as e:
        print(f"  ⚠️  Header format skipped: {e}")


def _color_row(sh, ws, row_num: int, status: str):
    """Apply background color to an entire row based on status."""
    color = STATUS_COLORS.get(status)
    if color is None:
        return   # No color for Applied / Unknown
    try:
        sh.batch_update({"requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": row_num - 1,
                    "endRowIndex": row_num,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(HEADERS),
                },
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }]})
    except Exception as e:
        print(f"  ⚠️  Row color skipped: {e}")


def get_existing(ws) -> dict:
    """Return {email_id: row_number} for all existing rows."""
    try:
        rows = ws.get_all_values()
        result = {}
        email_id_col = len(HEADERS) - 1   # last column
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > email_id_col and row[email_id_col]:
                result[row[email_id_col]] = i
        return result
    except Exception:
        return {}


def upsert_row(ws, sh, email_id: str, data: dict, existing: dict):
    """Insert new row or update status on existing row."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status = data.get("status", "Unknown")

    if email_id in existing:
        row_num = existing[email_id]
        try:
            current = ws.row_values(row_num)
            old_status = current[7] if len(current) > 7 else ""   # column H
            old_history = current[8] if len(current) > 8 else ""  # column I

            if old_status != status and status != "Unknown":
                history_entry = f"{now}: {old_status} → {status}"
                new_history = (old_history + "\n" + history_entry).strip()
                ws.update_cell(row_num, 8, status)      # H: Status
                ws.update_cell(row_num, 9, new_history) # I: History
                ws.update_cell(row_num, 7, now)         # G: Last Updated
                _color_row(sh, ws, row_num, status)
                print(f"    ↑ Updated: {data.get('company')} — {old_status} → {status}")
        except Exception as e:
            print(f"  ⚠️  Update error: {e}")
    else:
        row = [
            data.get("company", "Unknown"),          # A: Company
            data.get("role", "Unknown"),             # B: Role
            data.get("apply_link", ""),              # C: Apply / JD Link
            data.get("description", ""),             # D: Description
            data.get("fit_paragraph", ""),           # E: Why I'm a Fit
            data.get("date_applied", ""),            # F: Date Applied
            now,                                     # G: Last Updated
            status,                                  # H: Status
            "",                                      # I: Status History (empty on first entry)
            data.get("source", ""),                  # J: Source
            data.get("notes", ""),                   # K: Notes
            email_id,                                # L: _email_id (hidden)
        ]
        try:
            ws.append_row(row, value_input_option="USER_ENTERED")
            # Get the row number we just added
            new_row_num = len(ws.get_all_values())
            _color_row(sh, ws, new_row_num, status)
            print(f"    + Added: {data.get('company')} — {data.get('role')} ({status})")
        except Exception as e:
            print(f"  ⚠️  Insert error: {e}")

# ─────────────────────────────────────────────────────────────
# GMAIL IMAP SCANNER
# ─────────────────────────────────────────────────────────────

def decode_header(val) -> str:
    if val is None:
        return ""
    parts = email.header.decode_header(val)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def get_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
                except Exception:
                    continue
            elif ct == "text/html" and not body:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html = part.get_payload(decode=True).decode(charset, errors="replace")
                    body = re.sub(r"<[^>]+>", " ", html)
                    body = re.sub(r"\s+", " ", body).strip()
                except Exception:
                    continue
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            body = ""
    return body[:4000]


def make_id(msg_id: str, subject: str, sender: str) -> str:
    return hashlib.md5(f"{msg_id}|{sender}|{subject}".encode()).hexdigest()[:16]


def scan_folder(imap, folder: str, since: str, ws, sh,
                existing: dict, processed: set) -> int:
    count = 0
    try:
        status, _ = imap.select(folder, readonly=True)
        if status != "OK":
            return 0
    except Exception as e:
        print(f"  ⚠️  {folder}: {e}")
        return 0

    try:
        _, msg_ids = imap.search(None, f'(SINCE "{since}")')
    except Exception as e:
        print(f"  ⚠️  Search error: {e}")
        return 0

    id_list = msg_ids[0].split() if msg_ids[0] else []
    print(f"  {folder}: {len(id_list)} emails to scan")

    for uid in id_list:
        try:
            _, data = imap.fetch(uid, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            subject  = decode_header(msg.get("Subject", ""))
            sender   = decode_header(msg.get("From", ""))
            date_str = decode_header(msg.get("Date", ""))
            msg_id   = decode_header(msg.get("Message-ID", uid.decode()))
            body     = get_body(msg)

            if not is_job_related(subject, sender, body[:500]):
                continue

            email_id = make_id(msg_id, subject, sender)
            if email_id in processed:
                continue
            processed.add(email_id)

            try:
                date_applied = parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
            except Exception:
                date_applied = datetime.now().strftime("%Y-%m-%d")

            print(f"    📧 {subject[:55]:55s} | {sender[:35]}")

            # Determine status from email content
            status = status_from_email(subject, body)

            # Use Gemini to extract company/role/link
            extracted = extract_with_gemini(sender, subject, date_applied, body)
            if extracted.get("IS_JOB_EMAIL", "YES").upper() == "NO":
                continue

            company    = extracted.get("COMPANY", "Unknown")
            role       = extracted.get("ROLE", "Unknown")
            apply_link = extracted.get("APPLY_LINK", "")
            if apply_link in ("None", "none", ""):
                apply_link = ""
            notes = extracted.get("NOTES", "")
            if notes in ("None", "none"):
                notes = ""

            # Cross-reference Job Bot Log for richer data
            log_data = lookup_from_job_log(company, role)
            if not apply_link and log_data.get("apply_link"):
                apply_link = log_data["apply_link"]
            description   = log_data.get("description", "")
            fit_paragraph = log_data.get("fit_paragraph", "")

            source = "Sent" if "Sent" in str(folder) else "Inbox/All Mail"

            row_data = {
                "company":       company,
                "role":          role,
                "apply_link":    apply_link,
                "description":   description,
                "fit_paragraph": fit_paragraph,
                "date_applied":  date_applied,
                "status":        status,
                "source":        source,
                "notes":         notes,
            }

            count += 1
            upsert_row(ws, sh, email_id, row_data, existing)
            time.sleep(2)   # Rate limit Gemini + Sheets

        except Exception as e:
            print(f"  ⚠️  Error on email: {e}")
            continue

    return count


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run():
    print("\n" + "="*60)
    print(f"📧 Job Application Tracker — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    if not GMAIL_PASSWORD:
        print("❌ GMAIL_APP_PASSWORD not set"); return
    if not TRACKER_SHEET_ID:
        print("❌ TRACKER_SHEET_ID not set"); return

    # Connect to Sheets
    ws = _get_ws()
    if not ws:
        print("❌ Could not connect to tracker sheet"); return

    # Get the spreadsheet object for formatting
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds  = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
    gc     = gspread.authorize(creds)
    sh     = gc.open_by_key(TRACKER_SHEET_ID)

    existing  = get_existing(ws)
    processed = set(existing.keys())
    print(f"\n  {len(existing)} applications already tracked\n")

    since = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    print(f"  Scanning emails since {since}\n")

    # Pre-load Job Bot Log for cross-referencing
    load_job_log()

    # Connect to Gmail
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(GMAIL_USER, GMAIL_PASSWORD)
        print(f"✅ Gmail connected ({GMAIL_USER})\n")
    except Exception as e:
        print(f"❌ Gmail login failed: {e}")
        print("   Enable IMAP: Gmail → Settings → Forwarding & POP/IMAP → Enable IMAP")
        return

    total = 0
    for folder in ['"[Gmail]/All Mail"', '"[Gmail]/Sent Mail"']:
        print(f"📁 {folder}")
        total += scan_folder(imap, folder, since, ws, sh, existing, processed)
        print()

    imap.logout()

    print("─"*60)
    print(f"✅ Done — {total} job emails processed")
    print(f"   Tracker: https://docs.google.com/spreadsheets/d/{TRACKER_SHEET_ID}")
    print("─"*60)


if __name__ == "__main__":
    run()
