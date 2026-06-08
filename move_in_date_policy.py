"""move_in_date_policy.py — Shared far-future move-in date parsing.

P0-D: Unified far-future threshold and date parsing for Luna.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Optional
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

FAR_FUTURE_THRESHOLD_DAYS = 60

# Regex for move-in date extraction
# Matches "move-in date is May 22, 2026", "moving in May 22 2026",
# "target move-in: 2026-05-22", "Move in date: 7/30/2026", etc.
# The connector token (`is`/`on`/`around`/`about`/`:`/`,`) must explicitly
# match — bare "move in 2026" doesn't because that phrase rarely names a
# concrete date; better to return None and let the caller handle ambiguity.
_MOVE_IN_DATE_RE = re.compile(
    r"(?:Move[ -]?[Ii]n(?:[ -][Dd]ate)?|moves?[ -]in|target\s+move[- ]?in|moving\s+in)"
    r"\s*(?:is\s+|on\s+|around\s+|about\s+|[:,\-]\s*|\s+)"
    r"([A-Za-z]+\s+\d{1,2}(?:,?\s*\d{4})?"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

# Relative phrase patterns
_RELATIVE_MONTH_RE = re.compile(
    r"\bin\s+(\d+)\s+months?\b", re.IGNORECASE
)
_RELATIVE_WEEK_RE = re.compile(
    r"\bin\s+(\d+)\s+weeks?\b", re.IGNORECASE
)
_NEXT_MONTH_RE = re.compile(
    r"\bnext\s+month\b", re.IGNORECASE
)
_THIS_MONTH_RE = re.compile(
    r"\bthis\s+month\b", re.IGNORECASE
)

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _today_eastern() -> _dt.date:
    return _dt.datetime.now(EASTERN).date()


def parse_move_in_date(text: str) -> Optional[_dt.date]:
    """Extract a move-in date from inbound text.

    Supports:
      - ISO: 2026-07-30
      - US:  7/30/2026 or 7/30/26
      - Natural: 'July 30, 2026' / 'Jul 30 2026' / 'July 30'
      - Relative: 'next month', 'in 3 months', 'in 6 weeks'
      - Year-only context: 'Move in: 2026' (treated as ambiguous, returns None)

    Returns None if no date is found or the date is unparseable.
    """
    if not text:
        return None

    today = _today_eastern()

    # 1) Try explicit date patterns after move-in phrases
    m = _MOVE_IN_DATE_RE.search(text)
    if m:
        raw = m.group(1).strip().rstrip(",").strip()

        # ISO yyyy-mm-dd
        try:
            d = _dt.date.fromisoformat(raw)
            return d if d.year >= 2025 else None
        except ValueError:
            pass

        # US m/d/yyyy or m/d/yy
        for fmt in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                d = _dt.datetime.strptime(raw, fmt).date()
                return d if d.year >= 2025 else None
            except (ValueError, TypeError):
                pass

        # Natural-language: "<Month> <day>[, <year>]"
        nl = re.match(
            r"^([A-Za-z]+)\s+(\d{1,2})(?:,?\s*(\d{4}))?\s*$",
            raw,
        )
        if nl:
            month = _MONTHS.get(nl.group(1).lower())
            if month:
                day = int(nl.group(2))
                year = int(nl.group(3)) if nl.group(3) else today.year
                try:
                    d = _dt.date(year, month, day)
                    # If year was inferred and the date is in the past, assume next year
                    if not nl.group(3) and d < today:
                        d = _dt.date(year + 1, month, day)
                    return d if d.year >= 2025 else None
                except ValueError:
                    pass

    # 2) Relative phrases
    # "in X months"
    rm = _RELATIVE_MONTH_RE.search(text)
    if rm:
        months = int(rm.group(1))
        if 1 <= months <= 24:
            try:
                # Add months to today
                month = today.month + months
                year = today.year
                while month > 12:
                    month -= 12
                    year += 1
                # Use min(day, last day of target month)
                last_day = _dt.date(year, month, 1)
                # Get last day of month
                if month == 12:
                    next_month = _dt.date(year + 1, 1, 1)
                else:
                    next_month = _dt.date(year, month + 1, 1)
                last_day = (next_month - _dt.timedelta(days=1)).day
                day = min(today.day, last_day)
                return _dt.date(year, month, day)
            except ValueError:
                pass

    # "in X weeks"
    rw = _RELATIVE_WEEK_RE.search(text)
    if rw:
        weeks = int(rw.group(1))
        if 1 <= weeks <= 52:
            return today + _dt.timedelta(weeks=weeks)

    # "next month"
    if _NEXT_MONTH_RE.search(text):
        month = today.month + 1
        year = today.year
        if month > 12:
            month = 1
            year += 1
        last_day = _dt.date(year, month, 1)
        if month == 12:
            next_month = _dt.date(year + 1, 1, 1)
        else:
            next_month = _dt.date(year, month + 1, 1)
        last_day = (next_month - _dt.timedelta(days=1)).day
        day = min(today.day, last_day)
        return _dt.date(year, month, day)

    # "this month" — not far future, but we still parse it
    if _THIS_MONTH_RE.search(text):
        return today

    # 3) Standalone year like "Move in: 2026" — too ambiguous
    year_only = re.search(r"\bmove\s*in\s*:?\s*(\d{4})\b", text, re.IGNORECASE)
    if year_only:
        return None  # ambiguous year-only

    return None


def is_far_future_move_in(text: str) -> bool:
    """Return True if the text contains a move-in date more than 60 days out."""
    move_in = parse_move_in_date(text)
    if not move_in:
        return False
    today = _today_eastern()
    delta = (move_in - today).days
    return delta > FAR_FUTURE_THRESHOLD_DAYS


def days_until_move_in(text: str) -> Optional[int]:
    """Return the number of days until the parsed move-in date, or None."""
    move_in = parse_move_in_date(text)
    if not move_in:
        return None
    today = _today_eastern()
    return (move_in - today).days
