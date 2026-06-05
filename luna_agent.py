"""
luna_agent.py — Single Claude API call that does everything:
  1. Understands the email (classifies scenario, extracts prospect info)
  2. Decides whether to use a template or draft from scratch
  3. Calls tools as needed (property data, links, templates)
  4. Returns the final reply body

This is the ONLY place Claude is called. One call per email.
"""

import json
import os
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

from property_tools import TOOLS, execute_tool
from gmail_client import InboundEmail

load_dotenv(override=True)

# Hard-stop keywords (escalate, don't auto-reply)
HARD_STOP_KEYWORDS = [
    # Legal/safety
    "voice message", "voicemail", "eviction", "evict", "legal notice", 
    "lease termination", "lease renewal", "lawsuit", "attorney", "complaint",
    "discrimination", "fair housing",
    
    # Financial/pricing disputes
    "deposit refund", "waive deposit", "waive the deposit", "reduce deposit",
    "lower deposit", "deposit back", "return deposit", "refund",
    "concession", "waive", "lower the rent", "reduce the rent", 
    "negotiate the rent", "rent negotiation", "rent too high", "price too high",
    
    # Application outcomes
    "application approved", "application denied", "was i approved", "am i approved",
    "did i get approved", "approval status", "was my application approved",
    "application status", "deny my application", "why was i denied",
    "why was my application denied",
    
    # Fee waivers
    "waive the fee", "waive application fee", "waive my fee",
    "first month free", "free month", "no deposit",
]

# Load SOUL.md once at startup
_SOUL_PATH = Path(__file__).parent / "SOUL.md"
_SOUL_CONTENT = _SOUL_PATH.read_text(encoding="utf-8") if _SOUL_PATH.exists() else ""

# Scenario descriptions for the LLM
SCENARIO_DESCRIPTIONS = """
AVAILABLE SCENARIOS (pick the single best match):
- new_lead: First contact from a prospect about a property. They saw a listing and are reaching out.
- inquiry_reply: Follow-up question in an ongoing thread about rent, availability, application process.
- tour_confirm: ShowMojo or similar notification that a showing has been confirmed/booked.
- tour_reschedule: Showing was canceled, needs rescheduling, or prospect wants to change their tour time.
- post_tour: Follow-up after a showing — "how was your tour?", "ready to apply?", prospect asking next steps.
- objection: Prospect has a concern — credit score, deposit, short-term lease, Section 8 voucher, co-signer, eviction history.
- far_future: Prospect wants to hold/reserve a unit for a distant move-in date, or asks about a waiting list.
- re_engagement: Outbound follow-up to a warm/cold lead — "still interested?", "following up on your inquiry".
- student_housing: Prospect is a student looking for housing near a college/university.
- logistical_other: Internal operational email, commercial inquiry, team routing, or anything that does not fit above.
"""

_SEP = "  " + "-" * 50


def _log(msg: str) -> None:
    """Print a log line with consistent indentation."""
    print(f"  {msg}")


def _check_hard_stop(email_body: str, email_subject: str) -> bool:
    """
    Check if the email contains any hard-stop keywords that require escalation.
    Returns True if a hard-stop keyword is found.
    """
    combined_text = f"{email_subject} {email_body}".lower()
    for keyword in HARD_STOP_KEYWORDS:
        if keyword.lower() in combined_text:
            _log(f"[HARD-STOP] Detected keyword: '{keyword}'")
            return True
    return False


def process_email(email: InboundEmail) -> dict:
    """
    Process one inbound email using a single Claude API call with tools.
    Returns a dict with reply, scenario, tokens, cost info.
    """

    # Check for hard-stop keywords BEFORE calling Claude
    if _check_hard_stop(email.body, email.subject):
        _log("[ESCALATE] Hard-stop keyword detected. Manual review required.")
        return {
            "reply": "ESCALATE",
            "scenario": "escalated",
            "classification_method": "Rule",
            "model_used": "—",
            "template_used": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "tools_called": [],
        }

    # Validate API key
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        _log("[ERROR] ANTHROPIC_API_KEY is not set in .env")
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
    if not api_key.startswith("sk-ant-"):
        _log(f"[WARN]  ANTHROPIC_API_KEY looks invalid (starts with: {api_key[:10]}...)")
        _log("[WARN]  Replies may fail — check your API key in .env")

    client = anthropic.Anthropic(api_key=api_key)

    _log(f"[EMAIL] From: {email.from_name} <{email.from_addr}>")
    _log(f"[EMAIL] Subject: {email.subject}")
    _log(f"[EMAIL] Body preview: {email.body[:150]}...")

    system_prompt = f"""You are Luna, a professional leasing assistant for a property management company.

{_SOUL_CONTENT}

---

YOUR WORKFLOW:
1. READ the email and understand what the prospect is asking
2. CHOOSE which tools you need based on their request
3. CALL the tools to get data (you can call multiple tools)
4. USE the actual data from tool results to write your final reply

When you call a tool, wait for its result before continuing. Never make up information - only use what tools return.

---

YOUR TASK FOR THIS EMAIL:
You will receive one inbound email. You must:

STEP 1 — CLASSIFY the email scenario using EXACTLY one of these scenario labels:
{SCENARIO_DESCRIPTIONS}

STEP 2 — EXTRACT prospect information:
- Prospect name (first name if possible)
- Prospect email address
- Property they are asking about (if mentioned)

STEP 3 — DECIDE reply strategy and call tools:

A) TEMPLATE PATH — if scenario is one of these, use the template immediately:
   
   **POLICY TEMPLATES (need property_page_url):**
   apply_now, voucher, cosigner, short_term_lease, six_month_lease, month_to_month,
   eighteen_month_lease, far_future_inquiry, third_party_funding
   
   → ONLY call get_property_link(property_query=<address>) to get property_page_url
   → Then call use_template with template_type, prospect_name, property_address, property_page_url
   → Return the template body as-is. Do not call any other tools. Do not modify or draft further.
   
   **SIMPLE TEMPLATES (no property needed):**
   eviction, credit, income, esa, criminal_background, bankruptcy, pet_review
   
   → Call use_template immediately with just template_type and prospect_name
   → Return the template body as-is. Do not call any other tools. Do not modify or draft further.
   
   **SHOWING TEMPLATES (need booking_url):**
   tour_confirm, tour_reschedule, post_tour
   
   → ONLY call get_property_link(property_query=<address>) to get schedule_url
   → Then call use_template with template_type, prospect_name, property_address, booking_url
   → Return the template body as-is. Do not call any other tools. Do not modify or draft further.

B) PROPERTY PATH — for new_lead, inquiry_reply, far_future, re_engagement, student_housing:
   
   **CRITICAL: Only call tools for data the prospect EXPLICITLY asked about.**
   
   DO NOT call get_unit_availability unless the prospect asked about:
   - Rent amount / pricing / cost
   - Availability / "is it available"
   - Unit details / bedrooms / bathrooms / square footage
   - Specific unit number
   
   If prospect ONLY asks for:
   - Application → Just call get_property_link for application URL, do NOT call get_unit_availability
   - Tour/showing → Just call get_property_link for booking URL, do NOT call get_unit_availability
   - General inquiry → Just call get_property_link for property page, do NOT call get_unit_availability

   **CRITICAL: Only call tools for data the prospect EXPLICITLY asked about.**
   
   DO NOT call get_unit_availability unless the prospect asked about:
   - Rent amount / pricing / cost
   - Availability / "is it available"
   - Unit details / bedrooms / bathrooms / square footage
   - Specific unit number
   
   If prospect ONLY asks for:
   - Application → Just call get_property_link for application URL, do NOT call get_unit_availability
   - Tour/showing → Just call get_property_link for booking URL, do NOT call get_unit_availability
   - General inquiry → Just call get_property_link for property page, do NOT call get_unit_availability

   **FOR QUESTIONS ABOUT UNITS, RENT, OR AVAILABILITY:**
   
   → ONLY call get_unit_availability if prospect explicitly asked about rent, pricing, availability, or unit details
   → If a specific unit number is mentioned, use get_unit_availability(property_query=<address>, unit="<unit_number>")
   → Call get_property_link if you need schedule_url/booking URL or property page URL
   → Call fetch_property_data ONLY if you need property location (city, state, zip)
   → Call check_property_status ONLY if get_unit_availability returns found=False

STEP 4 — DRAFT your final reply using the tool data.

**WRITING STYLE - CRITICAL:**
- Keep replies SHORT (under 100 words)
- DO NOT use "Thanks for reaching out" or "Thanks for your interest"
- DO NOT say "available on", "timing works", "works perfectly", "fits your budget"
- DO NOT make promises about move-in dates or timing
- DO NOT be enthusiastic with "Great!", "Perfect!", "Excellent!"
- State ONLY facts from tool results - no interpretation, no inference
- If stating availability, say: "Per our records, Unit X shows [status]" NOT "Unit X is available now"
- When mentioning units, use neutral language: "showing" or "per our records" NOT "available" or "ready"
- Use property name as subject, NOT "we have" - say "[Property] has units" NOT "we have units"

**WHEN GIVING LINKS:**
Make link phrases more descriptive by combining actions. Instead of just "book a tour here:" or "apply here:", mention 2-3 things they can do (check details, see availability, schedule tour, apply, review units). Keep it natural and vary based on context. DO NOT add explanations after the link.

**FOLLOW-UP / CLOSING - Add natural, contextual closing:**
Choose a natural follow-up that fits what you just said. VARY YOUR LANGUAGE - don't repeat patterns. 

Use conversational phrasing like:
- "If you have questions about [relevant topic], just reply here and I'll help you through it."
- "Reply here if you'd like to talk through the details."
- "If you have questions or run into anything, just reply here and I'll help you."
- "Reply here once you're ready and I'll walk you through next steps."
- "Feel free to reply here if you need anything else."
- "Reply here if you want to move forward and I'll help."
- "If you need more information, just reply here."
- "Reply here if you'd like to discuss further."

Make the [relevant topic] specific to what you just told them. Examples:
- If you gave application link → "questions about the process"
- If you gave rent info → "questions about the unit" or "questions about availability"
- If you answered policy → "questions about this" or "questions about our lease terms"

Mix up your phrasing naturally. Use "If you have questions about X, just reply here and I'll help..." sometimes, 
"Reply here if..." other times, "Feel free to reply..." other times.

Make it conversational, relevant, and helpful. Don't fall into a pattern. Keep it ONE sentence, natural tone.

Return only the final email body. No subject line. No reasoning. No labels.
Just the reply text starting with the greeting.

CRITICAL RULES:
- NEVER mention AI, systems, databases, or tools
- NEVER make up property facts — only use what the tools return
- NEVER promise specific showing times — only provide booking links
- ALWAYS sign off as: Luna, Tri Star Realty
- If the scenario is logistical_other or the email is clearly spam → return exactly: SKIP
- If it is a hard-stop situation (legal threat, eviction notice, lease termination, discrimination complaint) → return exactly: ESCALATE
"""

    user_message = f"""INBOUND EMAIL:

From: {email.from_name} <{email.from_addr}>
Subject: {email.subject}
Date: {email.date}

Body:
{email.body[:3000]}

---

Process this email following your workflow. Call tools to get data, then use that data to write your final reply.
"""

    messages = [{"role": "user", "content": user_message}]

    # Log: About to call Claude
    _log(_SEP)
    _log("[CLAUDE CALL] Sending request to Anthropic API...")
    _log(f"  Model    : claude-sonnet-4-5")
    _log(f"  API key  : {api_key[:14]}...{api_key[-4:]}")
    _log(f"  Tools    : {[t['name'] for t in TOOLS]}")
    _log(f"  SOUL.md  : {len(_SOUL_CONTENT)} chars loaded")
    _log(_SEP)

    # Token accumulators
    total_input_tokens = 0
    total_output_tokens = 0
    tools_called = []
    tool_results_data = []  # Track actual tool results for DRAFT detection
    template_used = None

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        _log(f"[CLAUDE] Iteration {iteration} — waiting for response...")

        try:
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.AuthenticationError as e:
            _log(f"[ERROR] Authentication failed — invalid API key!")
            _log(f"        {str(e)[:120]}")
            _log(f"        Fix: update ANTHROPIC_API_KEY in .env")
            raise
        except anthropic.APIConnectionError as e:
            _log(f"[ERROR] Could not connect to Anthropic API: {str(e)[:100]}")
            raise
        except anthropic.RateLimitError as e:
            _log(f"[ERROR] Rate limit hit: {str(e)[:100]}")
            raise
        except Exception as e:
            _log(f"[ERROR] Anthropic API error: {type(e).__name__}: {str(e)[:120]}")
            raise

        # Accumulate token usage
        if hasattr(response, "usage") and response.usage:
            iter_input = getattr(response.usage, "input_tokens", 0)
            iter_output = getattr(response.usage, "output_tokens", 0)
            total_input_tokens += iter_input
            total_output_tokens += iter_output
            _log(f"[CLAUDE] Response received | stop_reason={response.stop_reason}")
            _log(f"         Tokens this iteration: input={iter_input}, output={iter_output}")
            _log(f"         Tokens cumulative    : input={total_input_tokens}, output={total_output_tokens}")

        if response.stop_reason == "end_turn":
            reply_text = None
            for block in response.content:
                if hasattr(block, "text"):
                    reply_text = block.text.strip()
                    break

            classification_method = "Template" if template_used else "LLM"
            model_used = "claude-sonnet-4-5"
            if reply_text in ("SKIP", "ESCALATE"):
                classification_method = "LLM"

            # Check for unverified sensitive facts (DRAFT detection)
            if _check_unverified_sensitive_facts(reply_text, tools_called, tool_results_data):
                reply_text = f"DRAFT:{reply_text}"  # Prefix with DRAFT marker

            scenario = _infer_scenario(reply_text, tools_called, template_used)

            # Log: Final result summary
            _log(_SEP)
            _log("[CLAUDE DONE] Final result:")
            _log(f"  Scenario   : {scenario}")
            _log(f"  Method     : {classification_method}")
            _log(f"  Template   : {template_used or 'None (AI drafted)'}")
            _log(f"  Tools used : {tools_called or 'None'}")
            _log(f"  Input tok  : {total_input_tokens:,}")
            _log(f"  Output tok : {total_output_tokens:,}")
            
            # Calculate cost using centralized function for accuracy
            from email_log import calculate_cost as calc_cost
            cost = calc_cost("claude-sonnet-4-5", total_input_tokens, total_output_tokens)
            _log(f"  Est. cost  : ${cost:.6f}")
            
            reply_type = (
                'SKIP' if reply_text == 'SKIP' 
                else 'ESCALATE' if reply_text == 'ESCALATE'
                else 'DRAFT (unverified data)' if reply_text and reply_text.startswith('DRAFT:')
                else 'Email reply'
            )
            _log(f"  Reply type : {reply_type}")
            _log(_SEP)

            return {
                "reply": reply_text,
                "scenario": scenario,
                "classification_method": classification_method,
                "model_used": model_used,
                "template_used": template_used,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "tools_called": tools_called,
            }

        elif response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    _log(f"[TOOL]  Claude calling: {block.name}({json.dumps(block.input)[:80]})")
                    result_str = execute_tool(block.name, block.input)
                    result_data = json.loads(result_str)
                    _log(f"[TOOL]  Result: {str(result_data)[:120]}")

                    if block.name not in tools_called:
                        tools_called.append(block.name)
                    
                    # Store tool result data for DRAFT detection
                    tool_results_data.append(result_data)
                    
                    if block.name == "use_template":
                        template_used = block.input.get("template_type")
                        _log(f"[TOOL]  Template selected: {template_used}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            messages.append({"role": "user", "content": tool_results})

        else:
            _log(f"[WARN]  Unexpected stop_reason={response.stop_reason}")
            break

    _log("[WARN]  Max iterations reached without end_turn")
    return {
        "reply": None,
        "scenario": "unknown",
        "classification_method": "LLM",
        "model_used": "claude-sonnet-4-5",
        "template_used": template_used,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "tools_called": tools_called,
    }


def _check_unverified_sensitive_facts(reply_text: str, tools_called: list, tool_results: list = None) -> bool:
    """
    Check if the reply contains sensitive facts (rent, pricing, deposit) that were NOT
    verified by tool calls, OR if the property mentioned doesn't exist in our data.
    Returns True if unverified sensitive facts are detected.
    
    Rules:
    1. If the reply mentions rent/pricing but get_unit_availability was NOT called → DRAFT
    2. If any tool returned found=False (property not in our data) → DRAFT
    """
    if not reply_text or reply_text in ("SKIP", "ESCALATE"):
        return False
    
    reply_lower = reply_text.lower()
    
    # Rule 2: Check if any tool returned "found: False" (property not in our data)
    if tool_results:
        for result in tool_results:
            if isinstance(result, dict) and result.get("found") is False:
                _log("[DRAFT] Reply references property not found in our data")
                return True
    
    # Rule 1: Patterns indicating rent/pricing information
    sensitive_patterns = [
        r'\$\d+',  # Dollar amounts
        'rent is', 'rent for', 'rent of', 'monthly rent',
        'deposit is', 'deposit of', 'security deposit',
        'pricing', 'price is', 'costs', 'cost is',
    ]
    
    import re
    has_sensitive_info = any(
        re.search(pattern, reply_lower) if pattern.startswith(r'\$') 
        else pattern in reply_lower
        for pattern in sensitive_patterns
    )
    
    # If reply contains sensitive info but get_unit_availability was NOT called, it's unverified
    if has_sensitive_info and "get_unit_availability" not in tools_called:
        _log("[DRAFT] Reply contains unverified sensitive facts (rent/pricing without tool verification)")
        return True
    
    return False


def _infer_scenario(reply_text: Optional[str], tools_called: list, template_used: Optional[str]) -> str:
    if reply_text == "SKIP":
        return "logistical_other"
    if reply_text == "ESCALATE":
        return "escalated"
    if template_used:
        template_scenario_map = {
            "tour_confirm": "tour_confirm",
            "tour_reschedule": "tour_reschedule",
            "post_tour": "post_tour",
            "apply_now": "new_lead",
            "voucher": "objection",
            "cosigner": "objection",
            "short_term_lease": "objection",
            "six_month_lease": "objection",
            "month_to_month": "objection",
            "eighteen_month_lease": "objection",
            "far_future_inquiry": "far_future",
            "third_party_funding": "objection",
            "eviction": "objection",
            "credit": "objection",
            "income": "objection",
            "esa": "objection",
            "criminal_background": "objection",
            "bankruptcy": "objection",
            "pet_review": "objection",
        }
        return template_scenario_map.get(template_used, "unknown")
    if "fetch_property_data" in tools_called or "get_property_link" in tools_called \
            or "get_unit_availability" in tools_called or "check_property_status" in tools_called:
        return "new_lead"
    return "unknown"
