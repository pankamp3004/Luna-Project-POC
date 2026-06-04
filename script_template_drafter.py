"""
script_template_drafter.py — Zero-cost deterministic template replies.

Handles these scenarios with no AI call needed:
  Showing scenarios : tour_confirm, tour_reschedule, post_tour
  Policy topics     : voucher, cosigner, short_term_lease, eviction,
                      credit, income, esa, criminal_background,
                      bankruptcy, pet_review

All templates follow SOUL.md voice rules:
  - Warm, professional tone
  - Sign off as "Luna, Tri Star Realty"
  - Never commit to showing times or property facts
  - Refer complex cases to Matan
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, Optional


_HTTP_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _first_name(name: Optional[str]) -> str:
    """Return clean first name or 'there' fallback."""
    if not name:
        return "there"
    cleaned = re.sub(r"\[[^\]]*\]", "", str(name)).strip().strip('"')
    if not cleaned:
        return "there"
    return cleaned.split()[0]


# ---------------------------------------------------------------------------
# Tour / showing templates  (SCRIPT lane — costs zero tokens)
# ---------------------------------------------------------------------------

def _mountain_view_confirm_body(name: str, booking_url: str) -> str:
    link_line = (
        f"\n\nIf you need to reschedule, grab a new time here: {booking_url}"
        if booking_url else ""
    )
    return (
        f"Hi {name},\n\n"
        "You're confirmed for your showing at Mountain View Apartments. "
        "These are spacious 2BR/2BA apartments.\n\n"
        "Important: all Mountain View showings take place at our staged unit — "
        "200 College Park Dr, Unit 206, Altoona, PA 16601 — "
        "not the individual unit listed online.\n\n"
        "Take a virtual look before you arrive: "
        "https://my.matterport.com/show/?m=tFr2DhrVeGQ&brand=0"
        f"{link_line}\n\n"
        "Luna, Tri Star Realty"
    )


_TOUR_CONFIRM_WITH_DATE = [
    (
        "Hi {name},\n\n"
        "You're confirmed for {showing_datetime} at {property}. "
        "If you need to reschedule, use the booking link here: {booking_url}\n\n"
        "Looking forward to seeing you!\n\n"
        "Luna, Tri Star Realty"
    ),
    (
        "Hi {name}, All set for {showing_datetime} at {property}. "
        "If your plans shift, grab a new time here: {booking_url} — "
        "otherwise, see you there!\n\n"
        "Luna, Tri Star Realty"
    ),
    (
        "Hi {name},\n\n"
        "Thanks for booking — your tour at {property} is confirmed for "
        "{showing_datetime}. If your timing changes, use the booking link "
        "here: {booking_url}\n\n"
        "Luna, Tri Star Realty"
    ),
]

_TOUR_CONFIRM_GENERIC = [
    (
        "Hi {name},\n\n"
        "You're confirmed for your showing at {property}. "
        "If you need to reschedule, use the booking link here: {booking_url}\n\n"
        "Looking forward to seeing you!\n\n"
        "Luna, Tri Star Realty"
    ),
    (
        "Hi {name}, All set for your tour at {property}. "
        "If your plans shift, grab a new time here: {booking_url} — "
        "otherwise, see you there!\n\n"
        "Luna, Tri Star Realty"
    ),
    (
        "Hi {name},\n\n"
        "Thanks for booking — your tour at {property} is confirmed. "
        "If your timing changes, use the booking link here: {booking_url}\n\n"
        "Luna, Tri Star Realty"
    ),
]

_TOUR_RESCHEDULE_VARIANTS = [
    (
        "Hi {name}, No worries — things come up. Whenever you're ready, "
        "grab a new time here: {booking_url}\n\n"
        "Luna, Tri Star Realty"
    ),
    (
        "Hi {name}, Totally understand. The fastest way to grab a new slot "
        "is through the booking link here: {booking_url}\n\n"
        "Luna, Tri Star Realty"
    ),
    (
        "Hi {name}, No problem at all. Pick a new time here when you're "
        "ready: {booking_url}\n\n"
        "Luna, Tri Star Realty"
    ),
]

_POST_TOUR_VARIANTS = [
    (
        "Hi {name},\n\n"
        "Hope your showing at {property} went well! If you're ready to "
        "move forward or have questions, just reply here and I'll help.\n\n"
        "Luna, Tri Star Realty"
    ),
    (
        "Hi {name}, Thanks for stopping by {property}. Reply here if you "
        "want to talk through anything you saw or if you're ready to take "
        "next steps.\n\n"
        "Luna, Tri Star Realty"
    ),
    (
        "Hi {name},\n\n"
        "Hope the tour was worth the trip! Reply here with any questions "
        "or if you're ready to move forward.\n\n"
        "Luna, Tri Star Realty"
    ),
]


_TEMPLATE_BANK: Dict[str, Any] = {
    "tour_confirm": {
        "with_date": _TOUR_CONFIRM_WITH_DATE,
        "generic": _TOUR_CONFIRM_GENERIC,
    },
    "tour_reschedule": {
        "with_date": _TOUR_RESCHEDULE_VARIANTS,
        "generic": _TOUR_RESCHEDULE_VARIANTS,
    },
    "post_tour": {
        "with_date": _POST_TOUR_VARIANTS,
        "generic": _POST_TOUR_VARIANTS,
    },
}


# ---------------------------------------------------------------------------
# Policy templates  (SCRIPT_POLICY lane — costs zero tokens)
# ---------------------------------------------------------------------------

_POLICY_TEMPLATES: Dict[str, str] = {
    "voucher": (
        "Hi {name}!\n\n"
        "We do accept vouchers — the main thing to keep in mind is that the "
        "voucher should match the bedroom count for the unit you're interested in.\n\n"
        "For questions about your specific situation, Matan is the best person "
        "to help: matan@tristarrei.com\n\n"
        "Luna, Tri Star Realty"
    ),
    "income": (
        "Hi {name},\n\n"
        "Thanks for sharing that. Our income guideline is 2.5x the monthly rent, "
        "so if you're below that threshold it can be a sticking point.\n\n"
        "If you want to talk through your situation or explore what might work, "
        "Matan can help — reach him at matan@tristarrei.com\n\n"
        "Luna, Tri Star Realty"
    ),
    "esa": (
        "Hi {name},\n\n"
        "For anything related to support or assistance animals, Matan handles "
        "those requests directly and can walk you through what's needed — "
        "reach him at matan@tristarrei.com\n\n"
        "Luna, Tri Star Realty"
    ),
    "cosigner": (
        "Hi {name},\n\n"
        "Co-signers are typically fine — here's what we'd usually need:\n\n"
        "- A completed rental application from the co-signer\n"
        "- Proof of income (recent paystubs or tax returns)\n"
        "- A credit check\n"
        "- Government-issued ID\n\n"
        "The co-signer would generally need income around 2.5x the monthly rent.\n\n"
        "Reply here once you're ready to get started and we'll walk you through it.\n\n"
        "Luna, Tri Star Realty"
    ),
    "eviction": (
        "Hi {name},\n\n"
        "Thanks for sharing that. We'd need a full application before making "
        "any decisions.\n\n"
        "If you'd like to talk through the situation first, Matan can help at "
        "matan@tristarrei.com\n\n"
        "Luna, Tri Star Realty"
    ),
    "short_term_lease": (
        "Hi {name},\n\n"
        "Our standard lease term is 12 months, so shorter terms are generally "
        "not available for this property.\n\n"
        "If your timeline is flexible or you'd like to explore options, reach "
        "out to Matan at matan@tristarrei.com — otherwise reply here once "
        "12 months works for you and we'll get you moving.\n\n"
        "Luna, Tri Star Realty"
    ),
    "credit": (
        "Hi {name},\n\n"
        "Credit is reviewed as part of the overall application, and the specifics "
        "matter. Matan would be the best person to walk through your situation — "
        "matan@tristarrei.com\n\n"
        "Luna, Tri Star Realty"
    ),
    "criminal_background": (
        "Hi {name},\n\n"
        "For anything related to background history, the best person to talk "
        "through your situation with is Matan — matan@tristarrei.com\n\n"
        "Luna, Tri Star Realty"
    ),
    "bankruptcy": (
        "Hi {name},\n\n"
        "For questions about how bankruptcy history factors in, Matan is the "
        "right person to speak with — matan@tristarrei.com\n\n"
        "Luna, Tri Star Realty"
    ),
    "pet_review": (
        "Hi {name},\n\n"
        "Pet decisions depend on the specific property and the details of your "
        "situation. For a direct answer on what's allowed, reach out to Matan "
        "at matan@tristarrei.com\n\n"
        "Luna, Tri Star Realty"
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def supports(scenario: str) -> bool:
    """Return True if this scenario can be handled by a zero-cost template."""
    return scenario in _TEMPLATE_BANK


def policy_topics() -> tuple:
    """Return all supported policy topics."""
    return tuple(_POLICY_TEMPLATES.keys())


def draft_template_reply(
    scenario: str,
    prospect_name: Optional[str] = None,
    property_address: Optional[str] = None,
    showing_datetime: Optional[str] = None,
    booking_url: Optional[str] = None,
    seed: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Build a deterministic template reply for a showing scenario.

    Returns dict with 'body' key, or None if not applicable.
    """
    bank = _TEMPLATE_BANK.get(scenario)
    if not bank:
        return None

    name = _first_name(prospect_name)
    prop = (property_address or "your showing").strip() or "your showing"
    dt = (showing_datetime or "").strip()
    url = (booking_url or "").strip()

    # tour_confirm and tour_reschedule require a valid booking URL
    if scenario in ("tour_confirm", "tour_reschedule") and not _HTTP_URL_RE.match(url):
        # Return generic fallback without URL for tour_reschedule
        if scenario == "tour_reschedule":
            body = (
                f"Hi {name}, No worries — things come up. When you're ready to "
                f"reschedule {prop}, just reply here and I'll help you find a new time.\n\n"
                "Luna, Tri Star Realty"
            )
            return {"body": body, "scenario": scenario, "lane": "SCRIPT"}
        return None

    # Special Mountain View template
    if scenario == "tour_confirm" and re.search(
        r"\b(?:college park|mountain view)\b", prop, re.IGNORECASE
    ):
        body = _mountain_view_confirm_body(name, url)
        return {"body": body, "scenario": scenario, "lane": "SCRIPT"}

    # Pick tier
    tier = "with_date" if dt else "generic"
    variants = bank.get(tier) or bank.get("generic") or []
    if not variants:
        return None

    rng = random.Random(seed) if seed is not None else random
    idx = rng.randrange(len(variants))
    body = variants[idx].format(
        name=name,
        property=prop,
        showing_datetime=dt,
        booking_url=url,
    )

    return {"body": body, "scenario": scenario, "lane": "SCRIPT"}


def draft_policy_reply(
    topic: str,
    prospect_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Build a deterministic policy reply for a hard-stop topic.

    Returns dict with 'body' key, or None if topic not found.
    """
    template = _POLICY_TEMPLATES.get(topic)
    if not template:
        return None

    name = _first_name(prospect_name)
    body = template.format(name=name)

    return {
        "body": body,
        "scenario": "hard_stop",
        "policy_topic": topic,
        "lane": "SCRIPT_POLICY",
    }
