"""
scenario_classifier.py — Scenario taxonomy for the POC.

In the original project, classification used regex patterns.
In this POC, classification is done by the LLM inside luna_agent.py
as part of the single Claude API call (no separate regex pass).

This file exists only to provide the canonical scenario list and
descriptions that are injected into the Claude system prompt.
"""

# The 10 canonical scenario labels — same as the original project
SCENARIOS = (
    "new_lead",        # First contact from a prospect about a property
    "inquiry_reply",   # Follow-up question on an existing thread
    "tour_confirm",    # Showing has been confirmed/booked
    "tour_reschedule", # Showing needs reschedule or was canceled
    "post_tour",       # After the tour — next steps or application
    "objection",       # Credit, deposit, lease length, Section 8, co-signer concern
    "far_future",      # Prospect wants to hold/reserve unit for far future
    "re_engagement",   # Outbound follow-up to warm/cold lead
    "student_housing", # Student looking for housing near college
    "logistical_other" # Internal / operational / commercial / non-leasing
)

# Scenarios that have zero-cost deterministic templates (no LLM needed)
SCRIPT_SCENARIOS = {"tour_confirm", "tour_reschedule", "post_tour"}

# Policy topics that have zero-cost templates
POLICY_TOPICS = {
    "voucher", "cosigner", "short_term_lease", "eviction",
    "credit", "income", "esa", "criminal_background",
    "bankruptcy", "pet_review",
}

# Scenarios that should never get an auto-reply
ESCALATE_SCENARIOS = {"logistical_other"}
