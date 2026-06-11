"""
email_log.py — Logging module for Luna POC email processing records.

Saves processing records to POC_LUNA/data/email_log.json in JSON Lines format
(one JSON object per line). This file is read by the FastAPI backend to power
the admin dashboard.

Usage:
    from email_log import log_email_processing, load_all_logs, get_stats
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Path to the data directory and log file
DATA_DIR = Path(__file__).parent / "data"
LOG_FILE = DATA_DIR / "email_log.json"

# Cost rates per million tokens (USD)
COST_RATES = {
    "claude-sonnet-4-5": {
        "input": 3.00 / 1_000_000,    
        "output": 15.00 / 1_000_000, 
    },
    "claude-haiku": {
        "input": 0.80 / 1_000_000,   
        "output": 4.00 / 1_000_000,   
    },
    # Also handle full model name variants
    "claude-haiku-4-5": {
        "input": 0.80 / 1_000_000,
        "output": 4.00 / 1_000_000,
    },
    "claude-3-5-haiku": {
        "input": 0.80 / 1_000_000,
        "output": 4.00 / 1_000_000,
    },
    "claude-3-haiku": {
        "input": 0.80 / 1_000_000,
        "output": 4.00 / 1_000_000,
    },
}


def calculate_cost(model_used: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the AI cost for a given model and token counts.

    Args:
        model_used: model name string (e.g., "claude-sonnet-4-5")
        input_tokens: number of input tokens used
        output_tokens: number of output tokens used

    Returns:
        Cost in USD as a float
    """
    if not model_used or model_used in ("—", "— (No LLM)", "Template", ""):
        return 0.0

    # Normalize model name to match our rates dict
    model_lower = model_used.lower().strip()

    rates = None
    for key in COST_RATES:
        if key in model_lower:
            rates = COST_RATES[key]
            break

    if rates is None:
        # Default to sonnet rates if unknown model
        rates = COST_RATES["claude-sonnet-4-5"]

    cost = (input_tokens * rates["input"]) + (output_tokens * rates["output"])
    return round(cost, 6)


def _ensure_data_dir() -> None:
    """Create the data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def log_email_processing(record: dict) -> None:
    """
    Append a single email processing record to the JSON Lines log file.

    The record must contain all required fields. Missing fields will be
    filled with safe defaults.

    Args:
        record: dict with email processing details
    """
    _ensure_data_dir()

    # Ensure all required fields are present with safe defaults
    safe_record = {
        "id": record.get("id", ""),
        "received_at": record.get("received_at", datetime.now(timezone.utc).isoformat()),
        "from_addr": record.get("from_addr", ""),
        "from_name": record.get("from_name", ""),
        "subject": record.get("subject", ""),
        "body_preview": record.get("body_preview", "")[:200],
        "full_body": record.get("full_body", ""),  # Store complete email body
        "scenario": record.get("scenario", "unknown"),
        "classification_method": record.get("classification_method", "LLM"),
        "decision": record.get("decision", "SKIP"),
        "model_used": record.get("model_used", "—"),
        "template_used": record.get("template_used"),  # None is valid
        "input_tokens": int(record.get("input_tokens", 0)),
        "output_tokens": int(record.get("output_tokens", 0)),
        "ai_cost_usd": float(record.get("ai_cost_usd", 0.0)),
        "reply_preview": (record.get("reply_preview") or "")[:300],
        "full_reply": record.get("full_reply", ""),
        "tools_called": record.get("tools_called", []),
        "status": record.get("status", "skipped"),
        "error": record.get("error"),  # None is valid
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(safe_record, ensure_ascii=False) + "\n")


def load_all_logs() -> list:
    """
    Load all log entries from the JSON Lines file.

    Returns:
        List of dicts, newest first (reversed by file order).
    """
    _ensure_data_dir()

    if not LOG_FILE.exists():
        return []

    records = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip malformed lines
                continue

    # Return newest first
    return list(reversed(records))


def get_stats() -> dict:
    """
    Compute aggregate statistics across all log entries.

    Returns:
        dict with keys: total_emails, auto_sent, drafts, escalations,
                        on_hold, total_cost, llm_calls, template_calls
    """
    records = load_all_logs()

    total_emails = len(records)
    auto_sent = sum(1 for r in records if r.get("status") == "sent")
    drafts = sum(1 for r in records if r.get("status") == "draft" or r.get("decision") == "DRAFT")
    escalations = sum(1 for r in records if r.get("status") == "escalated")
    on_hold = sum(1 for r in records if r.get("status") == "hold" or r.get("decision") == "HOLD")
    skipped = sum(1 for r in records if r.get("status") == "skipped" and r.get("decision") == "SKIP")
    total_cost = sum(float(r.get("ai_cost_usd", 0.0)) for r in records)
    llm_calls = sum(1 for r in records if r.get("classification_method") == "LLM")
    template_calls = sum(1 for r in records if r.get("classification_method") == "Template")

    return {
        "total_emails": total_emails,
        "auto_sent": auto_sent,
        "drafts": drafts,
        "escalations": escalations,
        "on_hold": on_hold,
        "skipped": skipped,
        "total_cost_usd": round(total_cost, 6),
        "llm_calls": llm_calls,
        "template_calls": template_calls,
    }
