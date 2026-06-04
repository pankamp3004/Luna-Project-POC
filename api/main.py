"""
api/main.py — FastAPI backend for the Luna Admin Panel.

Serves data from POC_LUNA/data/email_log.json and exposes endpoints
for the React dashboard.

Endpoints:
    GET  /api/emails           — paginated list of log entries
    GET  /api/emails/{id}      — single log entry by id
    GET  /api/stats            — dashboard statistics
    GET  /api/emails/{id}/reply — full reply text for an email
    POST /api/pipeline/run     — trigger poc_pipeline.py

Run with:
    uvicorn main:app --reload --port 8000
or from the POC_LUNA root:
    uvicorn api.main:app --reload --port 8000
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Path setup — works whether run from /api or /POC_LUNA
# ---------------------------------------------------------------------------
THIS_DIR = Path(__file__).parent
POC_LUNA_DIR = THIS_DIR.parent

# Add POC_LUNA directory to sys.path so we can import email_log
if str(POC_LUNA_DIR) not in sys.path:
    sys.path.insert(0, str(POC_LUNA_DIR))

from email_log import load_all_logs, get_stats  # noqa: E402

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Luna Admin Panel API",
    description="Backend API for the Luna email automation admin dashboard",
    version="1.0.1",  # Bumped to force reload
)

# CORS — allow requests from the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for POC/development
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _filter_by_status(records: list, status: str) -> list:
    """Filter records by status/decision bucket."""
    if not status or status == "all":
        return records

    status_lower = status.lower()
    if status_lower == "sent":
        return [r for r in records if r.get("status") == "sent"]
    elif status_lower == "draft":
        return [r for r in records if r.get("decision") == "DRAFT"]
    elif status_lower == "hold" or status_lower == "skipped":
        return [r for r in records if r.get("status") == "skipped"]
    elif status_lower == "escalated":
        return [r for r in records if r.get("status") == "escalated"]
    elif status_lower == "error":
        return [r for r in records if r.get("status") == "error"]
    else:
        return records


def _filter_by_search(records: list, search: str) -> list:
    """Filter records by a search string (searches from, subject, scenario)."""
    if not search or not search.strip():
        return records

    search_lower = search.lower().strip()
    filtered = []
    for r in records:
        haystack = " ".join([
            r.get("from_addr", ""),
            r.get("from_name", ""),
            r.get("subject", ""),
            r.get("scenario", ""),
            r.get("body_preview", ""),
        ]).lower()
        if search_lower in haystack:
            filtered.append(r)
    return filtered


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "Luna Admin Panel API"}


@app.get("/api/emails")
def list_emails(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page"),
    status: str = Query(default="all", description="Filter by status: all, sent, draft, hold, escalated"),
    search: str = Query(default="", description="Search by from, subject, or scenario"),
):
    """
    Return a paginated list of email log entries.

    Query params:
        page    — page number, 1-based (default: 1)
        limit   — items per page (default: 10, max: 100)
        status  — filter bucket: all | sent | draft | hold | escalated
        search  — search string across from, subject, scenario
    """
    records = load_all_logs()

    # Apply filters
    records = _filter_by_status(records, status)
    records = _filter_by_search(records, search)

    total = len(records)
    pages = max(1, (total + limit - 1) // limit)
    page = min(page, pages)

    start = (page - 1) * limit
    end = start + limit
    page_records = records[start:end]

    return {
        "emails": page_records,
        "total": total,
        "page": page,
        "pages": pages,
        "limit": limit,
    }


@app.get("/api/emails/{email_id}")
def get_email(email_id: str):
    """Return a single log entry by its UUID."""
    records = load_all_logs()
    for record in records:
        if record.get("id") == email_id:
            return record
    raise HTTPException(status_code=404, detail=f"Email with id '{email_id}' not found")


@app.get("/api/emails/{email_id}/reply")
def get_email_reply(email_id: str):
    """Return the full reply text for a single email."""
    records = load_all_logs()
    for record in records:
        if record.get("id") == email_id:
            return {
                "id": email_id,
                "full_reply": record.get("full_reply", ""),
                "reply_preview": record.get("reply_preview", ""),
                "status": record.get("status", ""),
                "decision": record.get("decision", ""),
            }
    raise HTTPException(status_code=404, detail=f"Email with id '{email_id}' not found")


class SendReplyRequest(BaseModel):
    body: str


@app.post("/api/emails/{email_id}/send")
def send_email_reply(email_id: str, req: SendReplyRequest):
    """
    Send a reply for a specific email using direct Gmail SMTP.
    Reads credentials from .env in POC_LUNA directory.
    """
    records = load_all_logs()
    record = None
    for r in records:
        if r.get("id") == email_id:
            record = r
            break
    if not record:
        raise HTTPException(status_code=404, detail=f"Email with id '{email_id}' not found")

    to_addr = record.get("from_addr", "")
    subject = record.get("subject", "")
    if not to_addr:
        raise HTTPException(status_code=400, detail="No recipient email address on record")

    # Load credentials from .env
    import smtplib
    import ssl
    import os as _os
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from dotenv import load_dotenv as _load_env

    env_path = POC_LUNA_DIR / ".env"
    _load_env(dotenv_path=str(env_path))

    gmail_addr = _os.getenv("GMAIL_ADDRESS", "").strip()
    app_password = _os.getenv("GMAIL_APP_PASSWORD", "").strip()
    from_name = _os.getenv("REPLY_FROM_NAME", "Luna").strip()

    if not gmail_addr or not app_password:
        raise HTTPException(
            status_code=500,
            detail="GMAIL_ADDRESS or GMAIL_APP_PASSWORD not configured in .env"
        )

    # Build MIME message
    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = reply_subject
    msg["From"] = f"{from_name} <{gmail_addr}>"
    msg["To"] = to_addr
    msg.attach(MIMEText(req.body, "plain", "utf-8"))

    # Send via Gmail SMTP
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(gmail_addr, app_password)
            server.sendmail(gmail_addr, to_addr, msg.as_string())
        return {"success": True, "to": to_addr, "subject": reply_subject}
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=401, detail="Gmail authentication failed. Check your App Password in .env")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SMTP error: {str(e)}")


@app.get("/api/inbox/unread-count")
def get_unread_count():
    """
    Check Gmail IMAP and return the count of unread emails.
    Uses credentials from .env file.
    """
    import imaplib
    import os as _os
    from dotenv import load_dotenv as _load_env

    env_path = POC_LUNA_DIR / ".env"
    _load_env(dotenv_path=str(env_path))

    gmail_addr = _os.getenv("GMAIL_ADDRESS", "").strip()
    app_password = _os.getenv("GMAIL_APP_PASSWORD", "").strip()

    if not gmail_addr or not app_password:
        return {"unread_count": 0, "error": "Gmail credentials not configured"}

    try:
        with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
            imap.login(gmail_addr, app_password)
            imap.select("INBOX")
            status, data = imap.uid("search", None, "UNSEEN")
            if status == "OK" and data and data[0]:
                uids = data[0].split()
                count = len(uids)
            else:
                count = 0
        return {"unread_count": count, "email": gmail_addr}
    except Exception as e:
        return {"unread_count": 0, "error": str(e)}

@app.get("/api/stats")
def stats():
    """
    Return aggregate dashboard statistics.

    Response:
        total_emails    — total emails processed
        auto_sent       — emails where status == "sent"
        drafts          — emails where decision == "DRAFT"
        on_hold         — emails where status == "skipped"
        escalations     — emails where status == "escalated"
        total_cost_usd  — sum of all ai_cost_usd values
        llm_calls       — count of emails classified by LLM
        template_calls  — count of emails classified by Template
    """
    return get_stats()


@app.post("/api/pipeline/run")
def run_pipeline(
    dry_run: bool = Query(default=False, description="If true, process but don't send"),
    max_emails: int = Query(default=5, ge=1, le=50, description="Max emails to process"),
):
    """
    Trigger the POC pipeline to process unread emails.

    This runs poc_pipeline.py as a subprocess. Results will appear in
    the email log and can be fetched via GET /api/emails.
    """
    pipeline_path = POC_LUNA_DIR / "poc_pipeline.py"

    if not pipeline_path.exists():
        raise HTTPException(status_code=500, detail="poc_pipeline.py not found")

    cmd = [sys.executable, "-W", "ignore", str(pipeline_path), "--max", str(max_emails)]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,  # 5-minute timeout
            cwd=str(POC_LUNA_DIR),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        # Consider success if returncode is 0 OR if stdout contains the Summary block
        # (deprecation warnings cause returncode=1 even on success)
        is_success = (
            result.returncode == 0
            or "Summary" in (result.stdout or "")
            or "Luna POC Pipeline" in (result.stdout or "")
        )
        return {
            "success": is_success,
            "returncode": result.returncode,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
            "dry_run": dry_run,
            "max_emails": max_emails,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Pipeline timed out after 5 minutes")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run pipeline: {str(e)}")
