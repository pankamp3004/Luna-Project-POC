"""
poc_pipeline.py -- Main entry point for Luna POC.

Run this script to process unread emails from your Gmail inbox.

Flow:
  1. Fetch unread emails via IMAP
  2. For each email -> call luna_agent.py (single Claude API call with tools)
  3. Claude classifies, extracts prospect info, calls tools, drafts reply
  4. Check business hours - if outside hours, mark as HOLD (saved for later)
  5. Check for DRAFT prefix - if unverified data, save as DRAFT (no send)
  6. Send reply via Gmail SMTP (if not HOLD or DRAFT)
  7. Mark original email as read
  8. Log every processed email to data/email_log.json

Usage:
    python poc_pipeline.py              # Process up to 5 unread emails
    python poc_pipeline.py --dry-run    # Process but don't send (preview only)
    python poc_pipeline.py --max 10     # Process up to 10 emails
"""

import argparse
import sys
import os
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(override=True)  # override=True ensures .env takes priority over system env vars

from gmail_client import fetch_unread_emails, send_reply, mark_as_read, InboundEmail
from luna_agent import process_email
from email_log import log_email_processing, calculate_cost


SKIP_SENDERS = {
    "noreply@",
    "no-reply@",
    "donotreply@",
    "mailer-daemon@",
    "postmaster@",
    "notifications@",
    "accounts.google.com",
}


def should_skip(email: InboundEmail) -> bool:
    """Return True for system/automated emails that should never get a reply."""
    from_lower = email.from_addr.lower()
    own_addr = os.getenv("GMAIL_ADDRESS", "").lower()
    if from_lower == own_addr:
        return True
    for pattern in SKIP_SENDERS:
        if pattern in from_lower:
            return True
    if not email.body.strip():
        return True
    return False


def is_within_business_hours() -> bool:
    """
    Check if current time is within business hours.
    Business hours are configured in .env: SENDING_HOUR_START, SENDING_HOUR_END, TIMEZONE
    Default: 8 AM - 8 PM in the configured timezone (default: Asia/Kolkata for India)
    """
    try:
        # Get business hours from .env
        start_hour = int(os.getenv("SENDING_HOUR_START", "8"))
        end_hour = int(os.getenv("SENDING_HOUR_END", "20"))
        timezone = os.getenv("TIMEZONE", "Asia/Kolkata")  # Default to India timezone
        
        # Get current time in configured timezone
        local_tz = ZoneInfo(timezone)
        now_local = datetime.now(local_tz)
        current_hour = now_local.hour
        
        # Check if within business hours
        return start_hour <= current_hour < end_hour
    except Exception as e:
        print(f"  [WARN] Could not check business hours: {e}. Defaulting to allow send.")
        return True  # Default to allowing sends if we can't check


def print_divider(title: str = "") -> None:
    line = "=" * 60
    if title:
        print(f"\n{line}")
        print(f"  {title}")
        print(line)
    else:
        print(f"\n{line}")


def run(max_emails: int = 5, dry_run: bool = False) -> None:
    print_divider("Luna POC Pipeline Starting")
    print(f"  Time      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Gmail     : {os.getenv('GMAIL_ADDRESS')}")
    print(f"  Max emails: {max_emails}")
    print(f"  Dry run   : {dry_run}")
    print()

    # Step 1 -- Fetch unread emails
    print_divider("Step 1: Fetching Unread Emails")
    try:
        emails = fetch_unread_emails(max_count=max_emails)
    except Exception as e:
        print(f"  [ERROR] Failed to fetch emails: {e}")
        print("\n  Troubleshooting:")
        print("  1. Make sure GMAIL_ADDRESS and GMAIL_APP_PASSWORD are set in .env")
        print("  2. Enable IMAP in Gmail: Settings > See all settings > Forwarding and POP/IMAP")
        print("  3. Create App Password: Google Account > Security > App Passwords")
        sys.exit(1)

    if not emails:
        print("  No unread emails to process.")
        print_divider("Done -- Nothing to process")
        return

    print(f"\n  Found {len(emails)} unread email(s)")

    # Step 2 -- Process each email
    processed = 0
    skipped = 0
    escalated = 0
    drafted = 0
    on_hold = 0
    errors = 0

    for i, email in enumerate(emails, 1):
        print_divider(f"Email {i}/{len(emails)}")
        print(f"  UID     : {email.uid}")
        print(f"  From    : {email.from_name} <{email.from_addr}>")
        print(f"  Subject : {email.subject}")
        print(f"  Date    : {email.date}")
        print(f"  Body    : {email.body[:150].replace(chr(10), ' ')}...")
        print()

        log_id = str(uuid.uuid4())
        received_at = datetime.now(timezone.utc).isoformat()

        # Skip system emails
        if should_skip(email):
            print("  [SKIP] System/automated sender -- no reply sent")
            skipped += 1
            if not dry_run:
                mark_as_read(email.uid)

            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": "logistical_other",
                "classification_method": "Template",
                "decision": "SKIP",
                "model_used": "-- (No LLM)",
                "template_used": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "ai_cost_usd": 0.0,
                "reply_preview": "",
                "full_reply": "",
                "tools_called": [],
                "status": "skipped",
                "error": None,
            })
            continue

        # Step 3 -- Call Luna agent (single Claude API call with tools)
        print("  Processing with Luna agent...")
        result = None
        try:
            result = process_email(email)
        except Exception as e:
            print(f"  [ERROR] Agent error: {e}")
            errors += 1
            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": "unknown",
                "classification_method": "LLM",
                "decision": "SKIP",
                "model_used": "claude-sonnet-4-5",
                "template_used": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "ai_cost_usd": 0.0,
                "reply_preview": "",
                "full_reply": "",
                "tools_called": [],
                "status": "error",
                "error": str(e),
            })
            continue

        # Unpack result dict
        reply_body = result.get("reply") if result else None
        scenario = result.get("scenario", "unknown") if result else "unknown"
        classification_method = result.get("classification_method", "LLM") if result else "LLM"
        model_used = result.get("model_used", "claude-haiku-4-5") if result else "claude-haiku-4-5"
        template_used = result.get("template_used") if result else None
        input_tokens = result.get("input_tokens", 0) if result else 0
        output_tokens = result.get("output_tokens", 0) if result else 0
        tools_called = result.get("tools_called", []) if result else []

        # Use pre-calculated cost from luna_agent (accurate mixed-model rates)
        # Falls back to calculate_cost only if not provided (e.g. error paths)
        ai_cost = result.get("ai_cost_usd") if result and result.get("ai_cost_usd") is not None \
                  else calculate_cost(model_used, input_tokens, output_tokens)

        if reply_body is None:
            print("  [WARN] No reply generated (agent returned None)")
            errors += 1
            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": scenario,
                "classification_method": classification_method,
                "decision": "SKIP",
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "ai_cost_usd": ai_cost,
                "reply_preview": "",
                "full_reply": "",
                "tools_called": tools_called,
                "status": "error",
                "error": "Agent returned None",
            })
            continue

        if reply_body.strip() == "SKIP":
            print("  [SKIP] Agent determined no reply needed")
            skipped += 1
            if not dry_run:
                mark_as_read(email.uid)

            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": scenario,
                "classification_method": classification_method,
                "decision": "SKIP",
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "ai_cost_usd": ai_cost,
                "reply_preview": "",
                "full_reply": "",
                "tools_called": tools_called,
                "status": "skipped",
                "error": None,
            })
            continue

        if reply_body.strip() == "ESCALATE":
            print("  [ESCALATE] Hard stop detected. Manual review required.")
            print("     This email contains legal/financial/sensitive content.")
            escalated += 1
            if not dry_run:
                mark_as_read(email.uid)

            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": scenario,
                "classification_method": classification_method,
                "decision": "ESCALATE",
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "ai_cost_usd": ai_cost,
                "reply_preview": "",
                "full_reply": "",
                "tools_called": tools_called,
                "status": "escalated",
                "error": None,
            })
            continue

        # Check for DRAFT prefix (unverified sensitive facts)
        if reply_body.startswith("DRAFT:"):
            # Remove DRAFT: prefix for storage
            clean_reply = reply_body[6:].strip()
            print()
            print("  [DRAFT] Reply contains unverified data - saved as draft")
            print("  " + "-" * 50)
            for line in clean_reply.split("\n")[:10]:  # Show first 10 lines
                print(f"  {line}")
            if len(clean_reply.split("\n")) > 10:
                print("  ... (truncated)")
            print("  " + "-" * 50)
            print()
            
            drafted += 1
            if not dry_run:
                mark_as_read(email.uid)

            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": scenario,
                "classification_method": classification_method,
                "decision": "DRAFT",
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "ai_cost_usd": ai_cost,
                "reply_preview": clean_reply[:300],
                "full_reply": clean_reply,
                "tools_called": tools_called,
                "status": "draft",
                "error": None,
            })
            continue

        # Show the generated reply
        print()
        print("  [REPLY GENERATED]")
        print("  " + "-" * 50)
        for line in reply_body.split("\n"):
            print(f"  {line}")
        print("  " + "-" * 50)
        print()

        # Check business hours (HOLD logic)
        if not is_within_business_hours() and not dry_run:
            print("  [HOLD] Outside business hours - reply saved for later dispatch")
            print("     Business hours: 8 AM - 8 PM ET")
            on_hold += 1
            mark_as_read(email.uid)

            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": scenario,
                "classification_method": classification_method,
                "decision": "HOLD",
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "ai_cost_usd": ai_cost,
                "reply_preview": reply_body[:300],
                "full_reply": reply_body,
                "tools_called": tools_called,
                "status": "hold",
                "error": None,
            })
            continue

        if dry_run:
            print("  [DRY RUN] Reply NOT sent (run without --dry-run to send)")
            processed += 1

            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": scenario,
                "classification_method": classification_method,
                "decision": "SKIP",
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "ai_cost_usd": ai_cost,
                "reply_preview": reply_body[:300],
                "full_reply": reply_body,
                "tools_called": tools_called,
                "status": "skipped",
                "error": None,
            })
            continue

        # Step 4 -- Send reply
        success = send_reply(
            to_addr=email.from_addr,
            subject=email.subject,
            body=reply_body,
            in_reply_to=email.message_id,
            references=email.references or email.message_id,
        )

        if success:
            # Step 5 -- Mark as read
            mark_as_read(email.uid)
            processed += 1

            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": scenario,
                "classification_method": classification_method,
                "decision": "SEND",
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "ai_cost_usd": ai_cost,
                "reply_preview": reply_body[:300],
                "full_reply": reply_body,
                "tools_called": tools_called,
                "status": "sent",
                "error": None,
            })
        else:
            errors += 1
            log_email_processing({
                "id": log_id,
                "received_at": received_at,
                "from_addr": email.from_addr,
                "from_name": email.from_name,
                "subject": email.subject,
                "body_preview": email.body[:200],
                "full_body": email.body,
                "scenario": scenario,
                "classification_method": classification_method,
                "decision": "SEND",
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "ai_cost_usd": ai_cost,
                "reply_preview": reply_body[:300],
                "full_reply": reply_body,
                "tools_called": tools_called,
                "status": "error",
                "error": "Failed to send reply via SMTP",
            })

    # Summary
    print_divider("Summary")
    print(f"  Total emails  : {len(emails)}")
    print(f"  Sent          : {processed}")
    print(f"  Drafted       : {drafted}")
    print(f"  On Hold       : {on_hold}")
    print(f"  Escalated     : {escalated}")
    print(f"  Skipped       : {skipped}")
    print(f"  Errors        : {errors}")
    if dry_run and processed > 0:
        print()
        print("  NOTE: Dry run mode -- run without --dry-run to actually send replies")
    if on_hold > 0:
        print()
        print(f"  NOTE: {on_hold} email(s) on hold (outside business hours)")
        print("        These will be dispatched when business hours resume")
    print_divider()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Luna POC Email Pipeline")
    parser.add_argument(
        "--max", type=int, default=1,
        help="Maximum number of emails to process (default: 1)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Process emails and generate replies but do NOT send them"
    )
    args = parser.parse_args()

    run(max_emails=args.max, dry_run=args.dry_run)
