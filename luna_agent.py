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
from move_in_date_policy import parse_move_in_date, is_far_future_move_in, FAR_FUTURE_THRESHOLD_DAYS

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

    # Check for far-future move-in date BEFORE calling Claude
    combined_text = f"{email.subject} {email.body}"
    move_in_date = parse_move_in_date(combined_text)
    is_far_future = is_far_future_move_in(combined_text)
    
    if is_far_future and move_in_date:
        _log(f"[FAR-FUTURE] Move-in date detected: {move_in_date} (more than {FAR_FUTURE_THRESHOLD_DAYS} days away)")

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

MOVE-IN DATE POLICY:
- If the prospect mentions a move-in date MORE THAN {FAR_FUTURE_THRESHOLD_DAYS} days away:
  * DO NOT provide direct booking links (ShowMojo links)
  * DO NOT say "schedule a tour here" or give property_page_url
  * DO NOT call get_property_link or provide any links
  * INSTEAD, say: "We're a bit early for scheduling since your move-in is [date]. Reach out about 30-45 days before your target move-in and we'll get you set up."
  * Keep the tone helpful, not dismissive
  * Classify as: far_future scenario
  * DO NOT provide rent, pricing, or unit details
  
- If move-in is WITHIN {FAR_FUTURE_THRESHOLD_DAYS} days or no move-in date mentioned:
  * Normal process - provide booking links as usual
  * Call tools and provide information normally
  * Classify as: new_lead or inquiry_reply (depending on context)

---

THIRD-PARTY FUNDING / RENTAL ASSISTANCE POLICY:

🚨 CRITICAL: DO NOT call get_unit_availability for rental assistance questions 🚨

We accept ALL forms of third-party rental assistance:
- Section 8 vouchers
- Rapid Rehousing
- Rental subsidies  
- Agency payments
- Organizational funding

WHEN PROSPECT ASKS ABOUT RENTAL ASSISTANCE / THIRD-PARTY FUNDING:
1. Acknowledge the specific program they mentioned (e.g., "yes, we accept Rapid Rehousing")
2. Include: "For program-specific details or paperwork requirements, reach out to Matan at matan@tristarrei.com"
3. ONLY call get_property_link to provide the property page link
4. DO NOT call get_unit_availability UNLESS they also ask about rent/pricing/availability

Examples:
- "Do you accept rental subsidies?" → ONLY call get_property_link
- "I have a Rapid Rehousing voucher" → ONLY call get_property_link  
- "Do you take third-party funding and how much is rent?" → call BOTH tools

Keep tone professional and helpful

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

STEP 3 — DECIDE reply strategy and call ALL needed tools IN PARALLEL (single tool_use response):

⚡ PARALLEL TOOL CALLING RULE: Always call ALL required tools in a SINGLE response.
   Never call one tool, wait for the result, then call another.
   Call get_property_link AND use_template together in the same response.
   Call get_unit_availability AND get_property_link together in the same response.

A) TEMPLATE PATH — if scenario is one of these:
   
   **POLICY TEMPLATES (need property_page_url):**
   apply_now, voucher, cosigner, short_term_lease, six_month_lease, month_to_month,
   eighteen_month_lease, far_future_inquiry
   
   → Call BOTH tools in ONE response simultaneously:
      • get_property_link(property_query=<address>)
      • use_template(template_type=<type>, prospect_name=<name>, property_address=<address>, property_page_url="PENDING")
   → The system will inject the real URL from get_property_link into use_template automatically.
   → Return the template body as-is. Do not call any other tools. Do not modify or draft further.
   
   **SIMPLE TEMPLATES (no property needed):**
   eviction, credit, income, esa, criminal_background, bankruptcy, pet_review
   
   → Call use_template immediately (single tool call is fine here — no URL needed).
   → Return the template body as-is. Do not call any other tools.
   
   **SHOWING TEMPLATES (need booking_url):**
   tour_confirm, tour_reschedule, post_tour
   
   → Call BOTH tools in ONE response simultaneously:
      • get_property_link(property_query=<address>)
      • use_template(template_type=<type>, prospect_name=<name>, property_address=<address>, booking_url="PENDING")
   → The system will inject the real booking URL automatically.
   → Return the template body as-is. Do not call any other tools.

B) PROPERTY PATH — for new_lead, inquiry_reply, far_future, re_engagement, student_housing:
   
   **🚫 CRITICAL RULE: DO NOT CALL get_unit_availability UNLESS EXPLICITLY ASKED 🚫**
   
   BEFORE calling get_unit_availability, ask yourself: "Did the PROSPECT (not the platform) ask about rent or availability?"
   
   You may ONLY call get_unit_availability if the prospect's OWN message contains:
   ✓ "how much is rent" / "what's the rent" / "rent price" / "cost"
   ✓ "is it available" / "when available" / "availability"
   ✓ Specific unit number mentioned by the prospect (e.g., "I want Unit 16")
   
   ⚠️ PLATFORM EMAILS (RentCafe, Zillow, Apartments.com, etc.):
   These emails contain metadata fields like "Beds: Studio", "Rent budget: $950", "Move-in date: ..."
   This is NOT the prospect asking about pricing — it is platform-generated data.
   For platform emails where the prospect just says "I like it" or "contact me" or "I want to move here"
   → DO NOT call get_unit_availability
   → ONLY call get_property_link
   
   ⚠️ GENERAL INTEREST PHRASES — these are NOT pricing questions:
   "discuss details", "details about moving", "moving details", "more details",
   "discuss moving", "talk about", "learn more", "find out more", "interested in"
   These mean the prospect wants general info — NOT rent, pricing, or unit specs.
   → DO NOT call get_unit_availability for these phrases
   → ONLY call get_property_link
   
   DO NOT call get_unit_availability if they only ask about:
   ✗ Policy questions (vouchers, pets, rental assistance, lease terms, third-party funding)
   ✗ Tours / showings / viewing / scheduling
   ✗ Application process ("how do I apply", "send me an application")
   ✗ General interest ("I like it", "contact me", "I want to move here")
   
   🔴 SPECIAL CASE - RENTAL ASSISTANCE / THIRD-PARTY FUNDING:
   If they ask "Do you accept [vouchers/rapid rehousing/subsidies]?" → ONLY call get_property_link
   DO NOT call get_unit_availability unless they ALSO ask about rent/pricing
   
   → If pricing asked: call get_unit_availability AND get_property_link IN THE SAME RESPONSE
   → If only link needed: call get_property_link alone
   → Call fetch_property_data ONLY if you need property location (city, state, zip)
   → Call check_property_status ONLY if get_unit_availability returns found=False

STEP 4 — DRAFT your final reply using the tool data.

**WRITING STYLE - CRITICAL:**
- Keep replies SHORT (under 100 words)
- DO NOT use "Thanks for reaching out" or "Thanks for your interest"
- DO NOT say "available on", "timing works", "works perfectly", "fits your budget"
- DO NOT say "is available for showings", "is available now", "is available for rent", "units are available"
- DO NOT say "is taking applications" — this sounds like a generic marketing phrase
- DO NOT say "We have", "We also have", "We have several" — always use the property name instead
- DO NOT say "Several units are showing as vacant" — unnecessary filler
- DO NOT make promises about move-in dates or timing
- DO NOT be enthusiastic with "Great!", "Perfect!", "Excellent!"
- Use the PROPERTY NAME (e.g. "Wehnwood Court") NOT the street address (e.g. "2708 Wehnwood Road") when the tool returns a canonical name
- When multiple units exist at different prices, say "starting at $X/mo" (lowest price) — not a range
- When prospect mentions a budget, you may briefly acknowledge it fits (e.g. "right in the range you're looking at")
- When units are available, a brief natural urgency note is fine ("these move fast" / "worth a look soon")
- State ONLY facts from tool results - no interpretation, no inference
- When stating unit availability status: say "Unit X shows as vacant" NOT "Unit X is available now"
- When stating pricing: just say "[Property Name] has 2-bedroom units starting at $825/mo" — no "per our records" prefix
- DO NOT use "Per our records" as a prefix — it sounds robotic. Just state the fact naturally.
- NEVER start a sentence with "We have" or "We also have" when describing property units — always use the property name

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

⚠️ PLATFORM SUBJECT PREFIXES — do NOT misclassify these:
- "[Luna commercial lead]" — this is a RentCafe platform notification for a RESIDENTIAL leasing lead. "Commercial" here means the lead came via a commercial platform/channel, NOT that it is a commercial real estate inquiry. Treat as new_lead.
- "[Luna lead]", "[Rental lead]", "[Prospect inquiry]" — all residential leasing leads. Treat as new_lead.
"""

    user_message = f"""INBOUND EMAIL:

From: {email.from_name} <{email.from_addr}>
Subject: {email.subject}
Date: {email.date}

Body:
{email.body[:3000]}

---

"""
    
    # Add far-future move-in context if detected
    if is_far_future and move_in_date:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/New_York")).date()
        days_away = (move_in_date - today).days
        
        user_message += f"""⚠️ FAR-FUTURE MOVE-IN DETECTED:
The prospect mentioned a move-in date of {move_in_date.strftime('%B %d, %Y')}, which is {days_away} days away (more than {FAR_FUTURE_THRESHOLD_DAYS} days).

FOLLOW THE FAR-FUTURE POLICY:
- DO NOT provide booking links or call get_property_link
- DO NOT provide pricing or unit details  
- Tell them to reach out 30-45 days before their move-in date
- Keep the tone helpful and professional

---

"""
    elif move_in_date and not is_far_future:
        # Near-future move-in — pass the date to Claude so it can reference it naturally
        user_message += f"""ℹ️ MOVE-IN DATE DETECTED: {move_in_date.strftime('%B %d, %Y')}
The prospect mentioned a move-in date. You may naturally reference it in your reply
(e.g. "with a {move_in_date.strftime('%B %d')} move-in you're right on time").
Normal process applies — provide booking links and information as usual.

---

"""
    
    user_message += "Process this email following your workflow. Call tools to get data, then use that data to write your final reply.\n"

    messages = [{"role": "user", "content": user_message}]

    # Log: About to call Claude
    _log(_SEP)
    _log("[CLAUDE CALL] Sending request to Anthropic API...")
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
    _iter_costs: list = []  # [(model, input_tokens, output_tokens)] per iteration

    # Model routing — inspired by lane_router.py concept:
    # Iteration 1: Sonnet (tool selection must be reliable — parallel calling, correct tool choice)
    # Iteration 2: Chosen AFTER we know what Iter 1 decided:
    #   - Template used → Haiku (just echoes pre-written text, no creativity needed)
    #   - Only get_property_link → Haiku (simple 2-sentence reply with a link)
    #   - get_unit_availability called → Sonnet (must write factually with correct tone)
    #   - far_future detected → Haiku (short, no links, templated phrasing)
    # NOTE: Iter 1 stays on Sonnet because Haiku struggles with parallel tool calling
    # instructions and leaks reasoning text into replies. Iter 2 is where savings are.
    MODEL_ITER1  = "claude-sonnet-4-5"  # tool selection — needs reliable parallel calling
    MODEL_SONNET = "claude-sonnet-4-5"  # AI-drafted replies with data — quality needed
    MODEL_HAIKU  = "claude-haiku-4-5"   # template echo + simple replies — cheap

    def _pick_model_for_iter2() -> str:
        """Pick model for Iteration 2 based on what Iteration 1 decided.
        
        Only use Haiku when the output is guaranteed to be simple:
        - Template echo: Claude just reads the template body and returns it — no writing
        - All other cases: Sonnet (writing quality and instruction-following matters)
        """
        # Template was confirmed used → Iter 2 just reads and returns template text
        # Haiku is sufficient for this — it's not generating anything new
        if template_used:
            return MODEL_HAIKU
        # All other cases (AI-drafted reply, unit data, general inquiry) → Sonnet
        # Haiku leaks reasoning text into replies and doesn't follow format instructions
        # reliably enough for customer-facing emails
        return MODEL_SONNET

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        _log(f"[CLAUDE] Iteration {iteration} — waiting for response...")

        # Pick model: Iter 1 always Haiku, Iter 2+ based on what Iter 1 decided
        current_model = MODEL_ITER1 if iteration == 1 else _pick_model_for_iter2()
        _log(f"[CLAUDE] Model: {current_model}")

        try:
            response = client.messages.create(
                model=current_model,
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
            _iter_costs.append((current_model, iter_input, iter_output))
            _log(f"[CLAUDE] Response received | stop_reason={response.stop_reason}")
            _log(f"         Model this iteration : {current_model}")
            _log(f"         Tokens this iteration: input={iter_input}, output={iter_output}")
            _log(f"         Tokens cumulative    : input={total_input_tokens}, output={total_output_tokens}")

        if response.stop_reason == "end_turn":
            reply_text = None
            for block in response.content:
                if hasattr(block, "text"):
                    reply_text = block.text.strip()
                    break

            classification_method = "Template" if template_used else "LLM"
            # Build a readable model string showing both iterations
            # e.g. "Sonnet 4.5 + Haiku 4.5" (iter1 + iter2) or just "Sonnet 4.5" if same
            def _short(m):
                if not m: return "—"
                if "sonnet" in m: return "Sonnet 4.5"
                if "haiku"  in m: return "Haiku 4.5"
                if "opus"   in m: return "Opus 4"
                return m
            iter1_model = MODEL_ITER1
            iter2_model = current_model
            if iter1_model == iter2_model:
                model_used = f"{_short(iter1_model)} × 2"
            else:
                model_used = f"{_short(iter1_model)} + {_short(iter2_model)}"
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
            
            # Calculate cost using per-iteration model rates (accurate mixed-model costing)
            from email_log import calculate_cost as calc_cost
            cost = sum(calc_cost(m, i, o) for m, i, o in _iter_costs)
            _log(f"  Est. cost  : ${cost:.6f}  (iter1={MODEL_ITER1}, iter2={current_model})")
            
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
                "ai_cost_usd": cost,  # pre-calculated with per-iteration model rates
            }

        elif response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            # Collect all tool_use blocks first (Claude may call multiple tools in parallel)
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            # --- PARALLEL TOOL INJECTION ---
            # If Claude calls get_property_link AND use_template together,
            # we need to run get_property_link first, then inject the real URL
            # into the use_template call before executing it.
            prop_link_result: Optional[dict] = None
            prop_link_block = next((b for b in tool_use_blocks if b.name == "get_property_link"), None)
            use_tmpl_block  = next((b for b in tool_use_blocks if b.name == "use_template"), None)

            if prop_link_block and use_tmpl_block:
                # Execute get_property_link first to get the real URL
                link_result_str  = execute_tool("get_property_link", prop_link_block.input)
                prop_link_result = json.loads(link_result_str)
                _log(f"[TOOL]  Claude calling (parallel): get_property_link({json.dumps(prop_link_block.input)[:60]})")
                _log(f"[TOOL]  Result: {str(prop_link_result)[:120]}")
                if "get_property_link" not in tools_called:
                    tools_called.append("get_property_link")
                tool_results_data.append(prop_link_result)

                # Inject real URL into use_template inputs before executing
                tmpl_input = dict(use_tmpl_block.input)
                real_page_url    = prop_link_result.get("property_page_url", "")
                real_schedule_url = prop_link_result.get("schedule_url", "") or prop_link_result.get("showmojo_url", "")

                # Replace PENDING placeholders with real URLs
                if tmpl_input.get("property_page_url") in ("PENDING", "", None):
                    tmpl_input["property_page_url"] = real_page_url
                if tmpl_input.get("booking_url") in ("PENDING", "", None):
                    tmpl_input["booking_url"] = real_schedule_url or real_page_url

                _log(f"[TOOL]  Claude calling (parallel): use_template({json.dumps(tmpl_input)[:80]})")
                tmpl_result_str  = execute_tool("use_template", tmpl_input)
                tmpl_result_data = json.loads(tmpl_result_str)
                _log(f"[TOOL]  Result: {str(tmpl_result_data)[:120]}")
                if "use_template" not in tools_called:
                    tools_called.append("use_template")
                tool_results_data.append(tmpl_result_data)
                if tmpl_input.get("template_type"):
                    template_used = tmpl_input["template_type"]
                    _log(f"[TOOL]  Template selected: {template_used}")

                # Build tool_results for both blocks
                tool_results = [
                    {"type": "tool_result", "tool_use_id": prop_link_block.id, "content": link_result_str},
                    {"type": "tool_result", "tool_use_id": use_tmpl_block.id,  "content": tmpl_result_str},
                ]

                # Handle any remaining tool blocks (unlikely but safe)
                for block in tool_use_blocks:
                    if block.name in ("get_property_link", "use_template"):
                        continue
                    _log(f"[TOOL]  Claude calling: {block.name}({json.dumps(block.input)[:80]})")
                    result_str  = execute_tool(block.name, block.input)
                    result_data = json.loads(result_str)
                    _log(f"[TOOL]  Result: {str(result_data)[:120]}")
                    if block.name not in tools_called:
                        tools_called.append(block.name)
                    tool_results_data.append(result_data)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            else:
                # Normal path: execute all tool blocks as-is
                tool_results = []
                for block in tool_use_blocks:
                    _log(f"[TOOL]  Claude calling: {block.name}({json.dumps(block.input)[:80]})")
                    result_str  = execute_tool(block.name, block.input)
                    result_data = json.loads(result_str)
                    _log(f"[TOOL]  Result: {str(result_data)[:120]}")

                    if block.name not in tools_called:
                        tools_called.append(block.name)
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
