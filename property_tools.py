"""
property_tools.py — Five Claude tools:
  1. fetch_property_data   — looks up property info from luna_property_master.csv
  2. get_unit_availability — live unit-level data from YARDI_UNITS.json (rent, beds, status)
  3. check_property_status — checks if a property is active, sold, or inactive
  4. get_property_link     — returns booking/ShowMojo URL from property_link_registry.json
  5. use_template          — selects a zero-cost predefined reply template

These are passed to Claude as tools so it can call them as needed per email.
"""

import csv
import json
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent / "property_data"
MASTER_CSV        = BASE / "luna_property_master.csv"
REGISTRY_JSON     = BASE / "property_link_registry.json"
YARDI_UNITS_JSON  = BASE / "YARDI_UNITS.json"          # structured JSON — single source of truth
YARDI_STATUS_CSV  = BASE / "luna_yardi_property_status.csv"
STATUS_OVERRIDES  = BASE / "luna_property_status_overrides.json"


# ---------------------------------------------------------------------------
# Module-level cache — each file is loaded once per process lifetime
# ---------------------------------------------------------------------------

_master_rows: Optional[list] = None
_registry_records: Optional[list] = None
_yardi_units: Optional[dict] = None   # { "Property Name": { "units": { "16": {...} } } }
_yardi_status_rows: Optional[list] = None
_status_overrides: Optional[dict] = None


def _load_master() -> list:
    global _master_rows
    if _master_rows is None:
        _master_rows = []
        if MASTER_CSV.exists():
            with open(MASTER_CSV, encoding="utf-8") as f:
                _master_rows = list(csv.DictReader(f))
    return _master_rows


def _load_registry() -> list:
    global _registry_records
    if _registry_records is None:
        _registry_records = []
        if REGISTRY_JSON.exists():
            with open(REGISTRY_JSON, encoding="utf-8") as f:
                _registry_records = json.load(f).get("canonical_records", [])
    return _registry_records


def _load_yardi_units() -> dict:
    """
    Load YARDI_UNITS.json.
    Structure: { "Property Name": { "units": { "unit_id": { beds, baths, sqft, rent, deposit, status, rent_ready } } } }
    Returns the raw dict as-is — callers do their own matching.
    """
    global _yardi_units
    if _yardi_units is None:
        _yardi_units = {}
        if YARDI_UNITS_JSON.exists():
            with open(YARDI_UNITS_JSON, encoding="utf-8") as f:
                _yardi_units = json.load(f)
    return _yardi_units


def _load_yardi_status() -> list:
    global _yardi_status_rows
    if _yardi_status_rows is None:
        _yardi_status_rows = []
        if YARDI_STATUS_CSV.exists():
            with open(YARDI_STATUS_CSV, encoding="utf-8") as f:
                _yardi_status_rows = list(csv.DictReader(f))
    return _yardi_status_rows


def _load_status_overrides() -> dict:
    global _status_overrides
    if _status_overrides is None:
        _status_overrides = {}
        if STATUS_OVERRIDES.exists():
            with open(STATUS_OVERRIDES, encoding="utf-8") as f:
                data = json.load(f)
                raw = data.get("properties", data)
                if isinstance(raw, dict):
                    _status_overrides = raw
    return _status_overrides


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _score_match(query_lower: str, target: str) -> int:
    """
    Word-overlap score. Returns how many query words (len > 2) appear in target.
    Both strings compared in lowercase.
    """
    target_lower = target.lower()
    words = [w for w in query_lower.split() if len(w) > 2]
    if not words:
        return 0
    return sum(1 for w in words if w in target_lower)


def _best_property_match(query_lower: str, data: dict) -> Optional[str]:
    """
    Find the best-matching property key in `data` (a dict keyed by property name).
    Returns the matching key or None.
    """
    best_score = 0
    best_key = None
    for key in data:
        score = _score_match(query_lower, key)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key if best_score > 0 else None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def fetch_property_data(property_query: str) -> dict:
    """
    Look up property details (city, state, zip, active/leasing status)
    from luna_property_master.csv.
    """
    if not property_query or not property_query.strip():
        return {"error": "No property query provided"}

    rows = _load_master()
    if not rows:
        return {"error": "Property master data not available"}

    query_lower = property_query.lower().strip()
    matches = []
    for row in rows:
        searchable = " ".join([
            row.get("canonical_property_name", ""),
            row.get("address_line_1", ""),
            row.get("address", ""),
        ])
        score = _score_match(query_lower, searchable)
        if score > 0:
            matches.append((score, row))

    if not matches:
        return {"found": False, "message": f"No property found matching '{property_query}'"}

    matches.sort(key=lambda x: x[0], reverse=True)
    best = matches[0][1]

    return {
        "found": True,
        "canonical_name": best.get("canonical_property_name", ""),
        "address": best.get("address_line_1", best.get("address", "")),
        "city": best.get("city", ""),
        "state": best.get("state", ""),
        "zip": best.get("zip", ""),
        "market": best.get("market", ""),
        "active_status": best.get("active_status", ""),
        "leasing_status": best.get("leasing_status", ""),
        "notes": best.get("issue_notes", best.get("notes", "")),
    }


def get_unit_availability(
    property_query: str,
    unit: Optional[str] = None,
    beds: Optional[str] = None,
) -> dict:
    """
    Look up live unit-level rent, deposit, availability, and bed/bath counts
    from YARDI_UNITS.json.

    Args:
        property_query : property address / name
        unit           : specific unit number (e.g. "16", "3", "B") — returns that unit's
                         full details plus all available units at the property
        beds           : bedroom count filter ("0"/"studio", "1", "2", "3", "4")

    Returns a dict with:
        property        — matched property name
        requested_unit  — full details for the unit asked about (if unit= was passed)
        available_now   — list of units available immediately
        available_soon  — list of units with a future available date
        available_now_count / available_soon_count
        occupied_sample — 3 occupied units (only when nothing is available)
    """
    if not property_query or not property_query.strip():
        return {"error": "No property query provided"}

    data = _load_yardi_units()
    if not data:
        return {"error": "Yardi unit data not available"}

    query_lower = property_query.lower().strip()
    matched_key = _best_property_match(query_lower, data)

    if not matched_key:
        return {"found": False, "message": f"No unit data found for '{property_query}'"}

    units_dict = data[matched_key].get("units", {})

    # Normalise filters
    unit_filter = unit.strip() if unit and unit.strip() else None
    beds_filter: Optional[str] = None
    if beds:
        b = beds.strip().lower()
        beds_filter = "0" if b in ("0", "studio", "eff", "efficiency") else (b if b.isdigit() else None)

    available_now = []
    available_soon = []
    occupied = []
    requested_unit_data = None

    for unit_id, u in units_dict.items():
        status_raw = str(u.get("status", "")).lower()
        unit_beds   = str(u.get("beds", ""))

        # Always capture the specifically requested unit (ignores other filters)
        if unit_filter and unit_id.lower() == unit_filter.lower():
            requested_unit_data = {
                "unit":       unit_id,
                "beds":       u.get("beds", ""),
                "baths":      u.get("baths", ""),
                "sqft":       u.get("sqft") or "",
                "rent":       u.get("rent", ""),
                "deposit":    u.get("deposit", ""),
                "status":     u.get("status", ""),
                "rent_ready": u.get("rent_ready", ""),
            }

        # Apply bed filter (skip non-matching)
        if beds_filter is not None and unit_beds != beds_filter:
            continue

        # Apply unit filter (skip non-matching)
        if unit_filter and unit_id.lower() != unit_filter.lower():
            continue

        is_not_ready   = "not ready" in status_raw
        is_avail_now   = (
            "vacant (available now)"   in status_raw
            or "notice (available now)"   in status_raw
            or "occupied (available now)" in status_raw
        )
        is_avail_soon  = (
            "vacant (available on"   in status_raw
            or "notice (available on"   in status_raw
            or "occupied (available on" in status_raw
        )

        summary = {
            "unit":       unit_id,
            "beds":       u.get("beds", ""),
            "baths":      u.get("baths", ""),
            "sqft":       u.get("sqft") or "",
            "rent":       u.get("rent", ""),
            "deposit":    u.get("deposit", ""),
            "status":     u.get("status", ""),
            "rent_ready": u.get("rent_ready", ""),
        }

        if is_avail_now and not is_not_ready:
            available_now.append(summary)
        elif is_avail_soon and not is_not_ready:
            available_soon.append(summary)
        else:
            occupied.append(summary)

    result: dict = {
        "found":               True,
        "property":            matched_key,
        "total_units":         len(units_dict),
        "available_now_count": len(available_now),
        "available_soon_count":len(available_soon),
        "available_now":       available_now,
        "available_soon":      available_soon,
        # only include occupied sample when nothing else is available
        "occupied_sample":     occupied[:3] if not available_now and not available_soon else [],
    }

    if unit_filter:
        if requested_unit_data:
            result["requested_unit"] = requested_unit_data
        else:
            result["requested_unit"]           = None
            result["requested_unit_not_found"] = (
                f"Unit '{unit_filter}' not found at {matched_key}."
            )

    return result


def get_property_link(property_query: str) -> dict:
    """
    Return the ShowMojo/booking URL and property page URL from property_link_registry.json.
    """
    if not property_query or not property_query.strip():
        return {"error": "No property query provided"}

    records = _load_registry()
    if not records:
        return {"error": "Property link registry not available"}

    query_lower = property_query.lower().strip()
    best_score  = 0
    best_record = None

    for record in records:
        canonical = str(record.get("canonical_display", "")).lower()
        aliases   = [str(a).lower() for a in record.get("aliases", [])]
        for name in [canonical] + aliases:
            score = _score_match(query_lower, name)
            if score > best_score:
                best_score  = score
                best_record = record

    if not best_record:
        return {"found": False, "message": f"No link found for '{property_query}'"}

    return {
        "found":             True,
        "canonical_display": best_record.get("canonical_display", ""),
        "schedule_url":      best_record.get("schedule_url", ""),
        "property_page_url": best_record.get("property_page_url", ""),
        "showmojo_url":      best_record.get("primary_showmojo_url", ""),
        "schedule_strategy": best_record.get("schedule_strategy", ""),
    }


def check_property_status(property_query: str) -> dict:
    """
    Check if a property is active, sold, or inactive.
    Checks manual overrides first, then luna_yardi_property_status.csv.
    """
    if not property_query or not property_query.strip():
        return {"error": "No property query provided"}

    query_lower = property_query.lower().strip()

    # 1 — manual overrides (highest priority: sold properties etc.)
    for key, override in _load_status_overrides().items():
        if _score_match(query_lower, key.lower()) > 0:
            return {
                "found":         True,
                "property":      key,
                "status":        override.get("status", "unknown"),
                "is_active":     False,
                "source":        "manual_override",
                "override_date": override.get("date", ""),
                "message":       f"Property has a manual status override: {override.get('status', 'unknown')}",
            }

    # 2 — Yardi status CSV
    best_score = 0
    best_row   = None
    for row in _load_yardi_status():
        searchable = " ".join([
            row.get("raw_property_name", ""),
            row.get("normalized_property_name", ""),
            row.get("address", ""),
        ])
        score = _score_match(query_lower, searchable)
        if score > best_score:
            best_score = score
            best_row   = row

    if not best_row:
        return {"found": False, "message": f"No status data found for '{property_query}'"}

    yardi_status = best_row.get("yardi_status", "").strip()
    is_inactive  = best_row.get("blInactive", "false").strip().lower() == "true"
    is_active    = (yardi_status.lower() == "active") and not is_inactive

    return {
        "found":        True,
        "property":     best_row.get("raw_property_name", ""),
        "address":      best_row.get("address", ""),
        "city":         best_row.get("city", ""),
        "state":        best_row.get("state", ""),
        "zip":          best_row.get("zip", ""),
        "owner":        best_row.get("owner_name", ""),
        "yardi_status": yardi_status,
        "is_active":    is_active,
        "is_inactive":  is_inactive,
        "source":       "yardi_status_csv",
        "message": (
            "Property is active and available for leasing."
            if is_active
            else f"Property is NOT active (yardi_status={yardi_status}, inactive={is_inactive})."
        ),
    }


# ---------------------------------------------------------------------------
# Claude tool definitions  (Anthropic tools API format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "fetch_property_data",
        "description": (
            "Look up a property's city, state, zip, market, and active/leasing status "
            "from the property database. Use this when you need location details or "
            "to confirm a property is in the portfolio."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_query": {
                    "type": "string",
                    "description": "Property address or name (e.g. '508 W Brighton Ave')"
                }
            },
            "required": ["property_query"]
        }
    },
    {
        "name": "get_unit_availability",
        "description": (
            "**PRIMARY DATA SOURCE** - Get real-time unit data from Yardi property management system.\n"
            "Returns: rent, deposit, beds, baths, sqft, availability status for units.\n\n"
            "**WHEN TO USE THIS TOOL:**\n"
            "✓ Prospect asks about a specific unit number\n"
            "✓ Prospect asks \"how much is rent?\" or \"what's the price?\"\n"
            "✓ Prospect asks \"is it available?\" or \"when can I move in?\"\n"
            "✓ Prospect asks about bedrooms, bathrooms, or square footage\n"
            "✓ ANY question about unit details, pricing, or availability\n\n"
            "**USAGE:**\n"
            "- If unit number mentioned: call with unit parameter\n"
            "- Returns 'requested_unit' with exact details for that unit\n"
            "- Also returns 'available_now' and 'available_soon' lists\n\n"
            "**CRITICAL:** Always use this tool for unit/pricing questions. "
            "The data is accurate and current. Do not say \"I don't have details\" - call this tool to get them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_query": {
                    "type": "string",
                    "description": "Property address or name (e.g. '508 W Brighton Ave', '1017 Pine Street')"
                },
                "unit": {
                    "type": "string",
                    "description": "Unit number if prospect asks about it (e.g. '16', '3', 'B')"
                },
                "beds": {
                    "type": "string",
                    "description": "Filter by bedrooms: '0', 'studio', '1', '2', '3', or '4'"
                }
            },
            "required": ["property_query"]
        }
    },
    {
        "name": "check_property_status",
        "description": (
            "Check whether a property is active, sold, or inactive. "
            "Use this when the property might be off-market, when get_unit_availability "
            "returns no data, or when the subject mentions an address you are unsure about."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_query": {
                    "type": "string",
                    "description": "Property address or name to check"
                }
            },
            "required": ["property_query"]
        }
    },
    {
        "name": "get_property_link",
        "description": (
            "Get the ShowMojo booking URL and property page URL for a property. "
            "Call this for new_lead, inquiry_reply, tour_confirm, tour_reschedule, "
            "and post_tour emails so you can include the scheduling link in the reply."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_query": {
                    "type": "string",
                    "description": "Property address or name (e.g. '508 W Brighton Ave')"
                }
            },
            "required": ["property_query"]
        }
    },
    {
        "name": "use_template",
        "description": (
            "Use a predefined zero-cost template reply instead of drafting from scratch. "
            "Call this when the scenario matches one of: "
            "tour_confirm, tour_reschedule, post_tour, voucher, cosigner, "
            "short_term_lease, eviction, credit, income, esa, criminal_background, "
            "bankruptcy, pet_review. Prefer templates whenever available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "template_type": {
                    "type": "string",
                    "enum": [
                        "tour_confirm", "tour_reschedule", "post_tour",
                        "voucher", "cosigner", "short_term_lease", "eviction",
                        "credit", "income", "esa", "criminal_background",
                        "bankruptcy", "pet_review"
                    ],
                    "description": "Template to use"
                },
                "prospect_name": {
                    "type": "string",
                    "description": "First name of the prospect (or 'there' if unknown)"
                },
                "property_address": {
                    "type": "string",
                    "description": "Property address (optional, used for tour templates)"
                },
                "booking_url": {
                    "type": "string",
                    "description": "ShowMojo or booking URL (required for tour_confirm and tour_reschedule)"
                }
            },
            "required": ["template_type", "prospect_name"]
        }
    }
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result as a JSON string."""

    if tool_name == "fetch_property_data":
        result = fetch_property_data(tool_input.get("property_query", ""))

    elif tool_name == "get_unit_availability":
        result = get_unit_availability(
            property_query=tool_input.get("property_query", ""),
            unit=tool_input.get("unit"),
            beds=tool_input.get("beds"),
        )

    elif tool_name == "check_property_status":
        result = check_property_status(tool_input.get("property_query", ""))

    elif tool_name == "get_property_link":
        result = get_property_link(tool_input.get("property_query", ""))

    elif tool_name == "use_template":
        from script_template_drafter import draft_template_reply, draft_policy_reply

        template_type    = tool_input.get("template_type", "")
        prospect_name    = tool_input.get("prospect_name", "there")
        property_address = tool_input.get("property_address", "")
        booking_url      = tool_input.get("booking_url", "")

        if template_type in ("tour_confirm", "tour_reschedule", "post_tour"):
            draft = draft_template_reply(
                scenario=template_type,
                prospect_name=prospect_name,
                property_address=property_address or None,
                booking_url=booking_url or None,
            )
        else:
            draft = draft_policy_reply(topic=template_type, prospect_name=prospect_name)

        result = (
            {"template_used": True,  "body": draft["body"]}
            if draft
            else {"template_used": False, "reason": f"No template for '{template_type}'"}
        )

    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result)
