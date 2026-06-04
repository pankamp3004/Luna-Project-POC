"""
gmail_client.py — Read inbox via IMAP and send replies via SMTP.
Uses Python's built-in imaplib and smtplib. No third-party packages needed.
"""

import email
import email.header
import email.utils
import imaplib
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, field
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


@dataclass
class InboundEmail:
    uid: str
    message_id: str
    subject: str
    from_addr: str
    from_name: str
    to_addr: str
    body: str
    date: str
    in_reply_to: str = ""
    references: str = ""


def _decode_header(value: str) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded).strip()


def _extract_body(msg: email.message.Message) -> str:
    """Extract plain text body from email message."""
    if msg.is_multipart():
        plain = None
        html = None
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if ctype == "text/plain" and plain is None:
                plain = text
            elif ctype == "text/html" and html is None:
                import re
                text = re.sub(r"<[^>]+>", " ", text)
                html = text
        return (plain or html or "").strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace").strip()
        return ""


def fetch_unread_emails(max_count: int = 10) -> list[InboundEmail]:
    """Connect to Gmail via IMAP and fetch unread emails."""
    gmail_addr = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_addr or not app_password:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")

    result = []

    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
        imap.login(gmail_addr, app_password)
        imap.select("INBOX")

        status, data = imap.uid("search", None, "UNSEEN")
        if status != "OK" or not data[0]:
            print("No unread emails found.")
            return []

        uids = data[0].split()
        # Process newest first, limit count
        uids = uids[-max_count:]

        for uid in uids:
            uid_str = uid.decode("utf-8") if isinstance(uid, bytes) else str(uid)
            status, msg_data = imap.uid("fetch", uid_str, "(BODY.PEEK[])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            from_full = _decode_header(msg.get("From", ""))
            from_name, from_addr = email.utils.parseaddr(from_full)

            inbound = InboundEmail(
                uid=uid_str,
                message_id=msg.get("Message-ID", "").strip(),
                subject=_decode_header(msg.get("Subject", "")),
                from_addr=from_addr.lower().strip(),
                from_name=from_name.strip(),
                to_addr=_decode_header(msg.get("To", "")),
                body=_extract_body(msg),
                date=_decode_header(msg.get("Date", "")),
                in_reply_to=msg.get("In-Reply-To", "").strip(),
                references=msg.get("References", "").strip(),
            )
            result.append(inbound)
            print(f"  Fetched: [{uid_str}] {inbound.subject[:60]} | From: {inbound.from_addr}")

    return result


def send_reply(
    to_addr: str,
    subject: str,
    body: str,
    in_reply_to: str = "",
    references: str = "",
) -> bool:
    """Send an email reply via Gmail SMTP."""
    gmail_addr = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    from_name = os.getenv("REPLY_FROM_NAME", "Luna")

    if not gmail_addr or not app_password:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg["From"] = f"{from_name} <{gmail_addr}>"
    msg["To"] = to_addr

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    elif in_reply_to:
        msg["References"] = in_reply_to

    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(gmail_addr, app_password)
            server.sendmail(gmail_addr, to_addr, msg.as_string())
        print(f"  ✅ Reply sent to: {to_addr}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to send reply: {e}")
        return False


def mark_as_read(uid: str) -> None:
    """Mark an email as read in Gmail."""
    gmail_addr = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    try:
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
            imap.login(gmail_addr, app_password)
            imap.select("INBOX")
            imap.uid("store", uid, "+FLAGS", "\\Seen")
    except Exception as e:
        print(f"  Warning: could not mark email {uid} as read: {e}")
