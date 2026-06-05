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


def process_email(email: InboundEmail) -> dict:
    """
    Process one inbound email using a single Claude API call with tools.
    Returns a dict with reply, scenario, tokens, cost info.
    """

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

A) TEMPLATE PATH — if scenario is one of these, call use_template immediately:
   tour_confirm, tour_reschedule, post_tour, voucher, cosigner, short_term_lease,
   eviction, credit, income, esa, criminal_background, bankruptcy, pet_review

B) PROPERTY PATH — for new_lead, inquiry_reply, far_future, re_engagement, student_housing:

   Read the email carefully. What does the prospect want to know?

   **FOR QUESTIONS ABOUT UNITS, RENT, OR AVAILABILITY:**
   
   → For the Questions About rent, pricing, availability, bedrooms, or unit details, use `get_unit_availability(property_query=<address>)`. 
   → If a specific unit number is mentioned (e.g., Unit 16, Apt 3), use `get_unit_availability(property_query=<address>, unit="<unit_number>")` and use the exact returned values without assuming details.
      
   → Call get_property_link(property_query=<address>) if you need schedule_url/booking URL/ShowMojo url and property page URL they can schedule a showing
   
   → Call fetch_property_data if you need property details (city, state, zip, active/leasing status)

   → Call check_property_status if get_unit_availability returns found=False (property might be sold)

STEP 4 — DRAFT your final reply using the tool data.
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
            cost = (total_input_tokens * 3.0 / 1_000_000) + (total_output_tokens * 15.0 / 1_000_000)
            _log(f"  Est. cost  : ${cost:.6f}")
            _log(f"  Reply type : {'SKIP' if reply_text == 'SKIP' else 'ESCALATE' if reply_text == 'ESCALATE' else 'Email reply'}")
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
            "voucher": "objection",
            "cosigner": "objection",
            "short_term_lease": "objection",
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
