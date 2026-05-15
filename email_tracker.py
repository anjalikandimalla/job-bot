# =============================================================================
# email_tracker.py — Job Application Tracker
#
# Scans ALL Gmail (inbox + sent + all mail) for job-related emails.
# Extracts company, role, status using Gemini.
# Writes to a separate "Job Application Tracker" Google Sheet.
# Runs every 6 hours via GitHub Actions — read-only on your inbox.
#
# No new secrets needed — uses existing GMAIL_APP_PASSWORD + GEMINI_API_KEY
# New secret needed: TRACKER_SHEET_ID (a new Google Sheet you create)
# =============================================================================

import imaplib
import email
import email.header
import os
import re
import json
import time
import hashlib
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

GMAIL_USER         = os.getenv("NOTIFY_EMAIL", "anjalikandimalla25@gmail.com")
GMAIL_PASSWORD     = os.getenv("GMAIL_APP_PASSWORD", "")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
TRACKER_SHEET_ID   = os.getenv("TRACKER_SHEET_ID", "")
CREDS_FILE         = os.path.join(os.path.dirname(__file__), "google_creds.json")

# How far back to scan on first run (days)
LOOKBACK_DAYS = 90

# Sheet tab name
SHEET_TAB = "Applications"

# ─────────────────────────────────────────────────────────────
# JOB EMAIL DETECTION — subject/sender keywords
# ─────────────────────────────────────────────────────────────

JOB_SUBJECT_KEYWORDS = [
    # Application confirmations
    "application received", "application confirmation", "thank you for applying",
    "thanks for applying", "we received your application", "successfully submitted",
    "your application to", "application for",
    # Interview
    "interview", "phone screen", "video interview", "zoom interview",
    "schedule a call", "schedule time", "availability for", "meet with",
    "hiring manager", "recruiter would like",
    # Assessment
    "assessment", "take-home", "coding challenge", "skills test",
    "next steps", "next step",
    # Offer
    "offer letter", "offer of employment", "pleased to offer", "job offer",
    "congratulations", "welcome to the team",
    # Rejection
    "unfortunately", "not moving forward", "other candidates", "not selected",
    "decided to move", "not a fit", "filled the position",
    # Recruiter outreach
    "exciting opportunity", "i came across your profile", "your background",
    "open to new opportunities", "looking for someone with your experience",
    "job opportunity", "career opportunity",
    # Generic job-related
    "position", "role at", "hiring for", "job at",
]

JOB_SENDER_DOMAINS = [
    "greenhouse.io", "lever.co", "workday.com", "myworkdayjobs.com",
    "icims.com", "taleo.net", "jobvite.com", "bamboohr.com",
    "smartrecruiters.com", "recruitee.com", "ashbyhq.com",
    "linkedin.com", "indeed.com", "ziprecruiter.com",
    "careers", "talent", "recruiting", "hr", "noreply",
    "no-reply", "jobs", "hiring",
]

REJECTION_SIGNALS = [
    "unfortunately", "not moving forward", "other candidates",
    "decided not to", "not selected", "not a match", "not the right fit",
    "filled the position", "position has been filled", "not proceed",
    "regret to inform", "will not be moving", "not be continuing",
]

OFFER_SIGNALS = [
    "offer letter", "offer of employment", "pleased to offer",
    "we would like to offer", "job offer", "congratulations on",
    "excited to offer", "formally offer",
]

INTERVIEW_SIGNALS = [
    "schedule", "interview", "phone screen", "video call", "zoom",
    "teams meeting", "google meet", "availability", "calendar invite",
    "meet with our", "speak with",
]

ASSESSMENT_SIGNALS = [
    "assessment", "take-home", "coding challenge", "skills test",
    "technical test", "assignment", "complete the following",
]

# ─────────────────────────────────────────────────────────────
# GEMINI SETUP
# ─────────────────────────────────────────────────────────────

try:
    from google import genai
    _client = genai.Client(api_key=GEMINI_API_KEY)
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

EXTRACTION_PROMPT = """
You are a job application email parser. Extract structured information from this email.

EMAIL:
From: {sender}
Subject: {subject}
Date: {date}
Body:
{body}

Extract the following. If you cannot determine a field, use "Unknown".

COMPANY: [company name — the employer, not a recruiter firm unless they are the employer]
ROLE: [job title being applied for or discussed]
STATUS: [one of: Applied / Phone Screen Scheduled / Interview Scheduled / Assessment Sent / Offer Received / Rejected / Recruiter Outreach / Unknown]
STATUS_REASON: [1 sentence explaining why you chose this status]
DESCRIPTION: [2-3 bullet points about the role if mentioned, or "Not provided"]
SKILLS_MATCH: [any skills mentioned in the email that match: program management, project management, operations, Smartsheet, SharePoint, stakeholder management, cross-functional, budget, vendor management, Excel, process improvement]
KEY_DATE: [any specific date mentioned — interview date, deadline, etc. — or "None"]
APPLY_LINK: [any application URL found in the email, or "None"]
NOTES: [anything notable — recruiter name, salary range, remote/hybrid, urgent timeline]
IS_JOB_EMAIL: [YES or NO — is this actually about a job application or opportunity?]

Respond in EXACTLY this format, one field per line:
COMPANY: ...
ROLE: ...
STATUS: ...
STATUS_REASON: ...
DESCRIPTION: ...
SKILLS_MATCH: ...
KEY_DATE: ...
APPLY_LINK: ...
NOTES: ...
IS_JOB_EMAIL: ...
"""

def extract_with_gemini(sender: str, subject: str, date: str, body: str) -> dict:
    """Use Gemini to extract structured info from a job email."""
    if not GEMINI_AVAILABLE:
        return {}

    prompt = EXTRACTION_PROMPT.format(
        sender=sender,
        subject=subject,
        date=date,
        body=body[:3000],  # Truncate long emails
    )

    try:
        response = _client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        result = {}
        for line in raw.split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                result[key.strip()] = val.strip()
        return result
    except Exception as e:
        print(f"  ⚠️  Gemini error: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# GOOGLE SHEETS SETUP
# ─────────────────────────────────────────────────────────────

SHEET_HEADERS = [
    "Email ID",           # Hidden dedup key
    "Company",
    "Role",
    "Description",
    "Applied Date",
    "Current Status",
    "Status Date",
    "Status History",
    "Skills Match",
    "Key Dates",
    "Apply Link",
    "Source",
    "Notes",
    "Last Updated",
]

_sheet_conn = None
_worksheet  = None


def _get_sheet():
    global _sheet_conn, _worksheet
    if _worksheet:
        return _worksheet
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
            ws = sh.add_worksheet(title=SHEET_TAB, rows=2000, cols=len(SHEET_HEADERS) + 1)
            ws.append_row(SHEET_HEADERS)
            try:
                ws.format(f"A1:{chr(64+len(SHEET_HEADERS))}1", {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.12, "green": 0.23, "blue": 0.37},
                })
                ws.freeze(rows=1)
            except Exception:
                pass

        _worksheet = ws
        return ws
    except Exception as e:
        print(f"  ⚠️  Sheet error: {e}")
        return None


def get_existing_email_ids() -> dict:
    """Return {email_id: row_number} for all rows already in the sheet."""
    ws = _get_sheet()
    if not ws:
        return {}
    try:
        rows = ws.get_all_values()
        result = {}
        for i, row in enumerate(rows[1:], start=2):  # Skip header
            if row and row[0]:
                result[row[0]] = i
        return result
    except Exception:
        return {}


def upsert_application(email_id: str, data: dict, existing: dict):
    """Insert a new application or update status if email_id already exists."""
    ws = _get_sheet()
    if not ws:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if email_id in existing:
        row_num = existing[email_id]
        # Update status + history + last updated
        try:
            current_row = ws.row_values(row_num)
            old_status   = current_row[5] if len(current_row) > 5 else ""
            old_history  = current_row[7] if len(current_row) > 7 else ""
            new_status   = data.get("STATUS", "Unknown")

            if old_status != new_status and new_status != "Unknown":
                history_entry = f"{now}: {old_status} → {new_status}"
                new_history   = (old_history + "\n" + history_entry).strip()
                ws.update_cell(row_num, 6,  new_status)   # Current Status
                ws.update_cell(row_num, 7,  now)          # Status Date
                ws.update_cell(row_num, 8,  new_history)  # History
                ws.update_cell(row_num, 14, now)          # Last Updated
                print(f"    ↑ Updated: {data.get('COMPANY')} — {old_status} → {new_status}")
        except Exception as e:
            print(f"  ⚠️  Update error: {e}")
    else:
        # New application — insert row
        row = [
            email_id,
            data.get("COMPANY", "Unknown"),
            data.get("ROLE", "Unknown"),
            data.get("DESCRIPTION", ""),
            data.get("date", ""),           # Applied Date (email date)
            data.get("STATUS", "Unknown"),
            now,                            # Status Date
            "",                             # History (empty on first entry)
            data.get("SKILLS_MATCH", ""),
            data.get("KEY_DATE", ""),
            data.get("APPLY_LINK", ""),
            data.get("source", ""),         # Inbox / Sent
            data.get("NOTES", ""),
            now,                            # Last Updated
        ]
        try:
            ws.append_row(row, value_input_option="USER_ENTERED")
            print(f"    + Added: {data.get('COMPANY')} — {data.get('ROLE')} ({data.get('STATUS')})")
        except Exception as e:
            print(f"  ⚠️  Insert error: {e}")


# ─────────────────────────────────────────────────────────────
# GMAIL IMAP SCANNER
# ─────────────────────────────────────────────────────────────

def decode_header_value(val) -> str:
    """Safely decode an email header value."""
    if val is None:
        return ""
    parts = email.header.decode_header(val)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def get_email_body(msg) -> str:
    """Extract plain text body from an email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
                except Exception:
                    continue
            elif content_type == "text/html" and not body:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html = part.get_payload(decode=True).decode(charset, errors="replace")
                    # Strip HTML tags
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


def is_job_related(subject: str, sender: str, body_preview: str) -> bool:
    """Quick local check before spending a Gemini call."""
    subject_lower = subject.lower()
    sender_lower  = sender.lower()
    body_lower    = body_preview.lower()

    # Check subject keywords
    if any(kw in subject_lower for kw in JOB_SUBJECT_KEYWORDS):
        return True

    # Check sender domain patterns
    if any(domain in sender_lower for domain in JOB_SENDER_DOMAINS):
        return True

    # Check body for strong signals
    strong_body_signals = [
        "your application", "applied for", "position of", "role of",
        "interview", "offer letter", "hiring manager",
        "recruiter", "talent acquisition",
    ]
    if any(sig in body_lower for sig in strong_body_signals):
        return True

    return False


def make_email_id(msg_id: str, subject: str, sender: str) -> str:
    """Create a stable dedup ID for an email."""
    raw = f"{msg_id}|{sender}|{subject}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def scan_folder(imap: imaplib.IMAP4_SSL, folder: str,
                since_date: str, existing: dict, processed: set) -> int:
    """Scan one IMAP folder. Returns count of job emails found."""
    found = 0
    try:
        status, _ = imap.select(folder, readonly=True)
        if status != "OK":
            print(f"  ⚠️  Could not open folder: {folder}")
            return 0
    except Exception as e:
        print(f"  ⚠️  Folder error {folder}: {e}")
        return 0

    try:
        _, msg_ids = imap.search(None, f'(SINCE "{since_date}")')
    except Exception as e:
        print(f"  ⚠️  Search error in {folder}: {e}")
        return 0

    id_list = msg_ids[0].split() if msg_ids[0] else []
    print(f"  {folder}: {len(id_list)} emails since {since_date}")

    for uid in id_list:
        try:
            _, data = imap.fetch(uid, "(RFC822)")
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = decode_header_value(msg.get("Subject", ""))
            sender  = decode_header_value(msg.get("From", ""))
            date_str = decode_header_value(msg.get("Date", ""))
            msg_id  = decode_header_value(msg.get("Message-ID", uid.decode()))

            body = get_email_body(msg)

            # Quick filter before using Gemini
            if not is_job_related(subject, sender, body[:500]):
                continue

            # Dedup
            email_id = make_email_id(msg_id, subject, sender)
            if email_id in processed:
                continue
            processed.add(email_id)

            # Parse date
            try:
                parsed_date = parsedate_to_datetime(date_str)
                formatted_date = parsed_date.strftime("%Y-%m-%d")
            except Exception:
                formatted_date = datetime.now().strftime("%Y-%m-%d")

            print(f"    📧 {subject[:60]} | {sender[:40]}")

            # Use Gemini to extract structured info
            extracted = extract_with_gemini(sender, subject, formatted_date, body)

            # Skip if Gemini says it's not a job email
            if extracted.get("IS_JOB_EMAIL", "YES").upper() == "NO":
                continue

            extracted["date"]   = formatted_date
            extracted["source"] = "Sent" if "Sent" in folder else "Inbox"

            found += 1
            upsert_application(email_id, extracted, existing)

            time.sleep(2)  # Be polite to Gemini rate limits

        except Exception as e:
            print(f"  ⚠️  Error processing email: {e}")
            continue

    return found


def run():
    print("\n" + "="*60)
    print(f"📧 Job Application Tracker: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    if not GMAIL_PASSWORD:
        print("❌ GMAIL_APP_PASSWORD not set")
        return
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not set")
        return
    if not TRACKER_SHEET_ID:
        print("❌ TRACKER_SHEET_ID not set")
        return

    # Load existing sheet entries for dedup
    print("\nLoading existing tracker entries...")
    existing = get_existing_email_ids()
    print(f"  {len(existing)} applications already tracked")

    # Calculate lookback date
    since = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    print(f"  Scanning emails since: {since}\n")

    # Connect to Gmail
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(GMAIL_USER, GMAIL_PASSWORD)
        print(f"✅ Connected to Gmail as {GMAIL_USER}\n")
    except Exception as e:
        print(f"❌ Gmail login failed: {e}")
        print("   Make sure IMAP is enabled in Gmail Settings → See all settings → Forwarding and POP/IMAP")
        return

    # Scan folders
    processed = set()
    total_found = 0

    folders = [
        '"[Gmail]/All Mail"',   # Everything — inbox + sent + archived
        '"[Gmail]/Sent Mail"',  # Sent separately to catch application emails you sent
    ]

    for folder in folders:
        print(f"📁 Scanning {folder}...")
        found = scan_folder(imap, folder, since, existing, processed)
        total_found += found
        print(f"  → {found} job emails found\n")

    imap.logout()

    print("─"*60)
    print(f"✅ Done | {total_found} job emails processed")
    print(f"   Sheet: https://docs.google.com/spreadsheets/d/{TRACKER_SHEET_ID}")
    print("─"*60)


if __name__ == "__main__":
    run()
