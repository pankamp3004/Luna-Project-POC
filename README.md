# it's a complete flow of the project for the other developer
# Luna POC — Leasing Email Automation

A working proof-of-concept that replicates the core Luna leasing assistant
behavior using your own Gmail and the Anthropic API.

---

## What This Does

- Reads unread emails from your Gmail inbox via IMAP
- For each email, makes **one Claude API call** that:
  - Classifies the email (new lead, tour request, objection, etc.)
  - Extracts prospect info (name, email, property)
  - Calls tools to fetch property data and booking links
  - Decides: use a predefined template OR draft a custom reply
- Sends the reply via Gmail SMTP
- Marks the email as read

---

## Folder Structure

```
POC_LUNA/
├── poc_pipeline.py         ← Main entry point — run this
├── luna_agent.py           ← Single Claude API call (agentic loop)
├── gmail_client.py         ← Gmail IMAP reader + SMTP sender
├── property_tools.py       ← Claude tools: property data + links + templates
├── script_template_drafter.py ← Zero-cost predefined reply templates
├── scenario_classifier.py  ← Scenario labels (classification done by LLM)
├── SOUL.md                 ← Luna's personality and rules (injected into prompt)
├── requirements.txt        ← Python dependencies
├── .env.example            ← Copy this to .env and fill in your credentials
└── property_data/
    ├── luna_property_master.csv      ← Property database
    └── property_link_registry.json  ← Booking URLs per property
```

---

## Setup

### 1. Install dependencies

```bash
cd POC_LUNA
pip install -r requirements.txt
```

### 2. Set up Gmail App Password

1. Go to your Google Account → Security
2. Enable **2-Step Verification** (required for App Passwords)
3. Go to **App Passwords** → Select app: Mail → Generate
4. Copy the 16-character password

Also enable IMAP in Gmail:
- Gmail → Settings → See all settings → Forwarding and POP/IMAP → **Enable IMAP**

### 3. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
GMAIL_ADDRESS=pankaj@amplework.in
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
REPLY_FROM_NAME=Luna
REPLY_FROM_EMAIL=pankaj@amplework.in

# Business hours for sending emails (Eastern Time, 24-hour format)
SENDING_HOUR_START=8   # 8 AM ET
SENDING_HOUR_END=20    # 8 PM ET
```

---

## Running the POC

### Dry run first (recommended — no emails sent)

```bash
python poc_pipeline.py --dry-run
```

This fetches emails, generates replies, and prints them — but does NOT send anything.

### Send replies

```bash
python poc_pipeline.py
```

### Process more emails

```bash
python poc_pipeline.py --max 10
```

---

## How to Test

Send these test emails **to your own Gmail** from another account:

**Test 1 — New lead inquiry:**
> Subject: Interested in 2BR apartment
> Body: Hi, I saw your listing for the apartment on 10 Danbury Street. Is it still available? How much is rent?

**Test 2 — Tour confirmation (simulate):**
> Subject: Showing Confirmed for: 10 Danbury Street Southeast
> Body: Your showing is confirmed for June 15 at 3 PM.

**Test 3 — Section 8 voucher question:**
> Subject: Voucher question
> Body: Do you accept Section 8 housing vouchers?

**Test 4 — Hard stop (will be escalated, not replied):**
> Subject: Legal complaint
> Body: I am going to file a lawsuit against your company.

**Test 5 — Credit concern:**
> Subject: Question about my application
> Body: My credit score is around 580. Will that be a problem for applying?

**Test 6 — Tour reschedule:**
> Subject: Re: Need to reschedule my tour
> Body: Sorry, something came up. Can we reschedule my showing at 1913 South 20th Street?

---

## Architecture

### Email Processing Modes

Luna POC now supports **5 intelligent processing modes** for safe and accurate email handling:

1. **SKIP** — System/automated emails (noreply@, etc.)
2. **DRAFT** — Replies with unverified rent/pricing data (saved, not sent)
3. **ESCALATE** — Hard-stop keywords requiring manual review (legal, application status)
4. **HOLD** — Outside business hours (8 AM - 8 PM ET)
5. **SENT** — Verified replies successfully sent

See [MODES_DOCUMENTATION.md](MODES_DOCUMENTATION.md) for detailed information about each mode.

### Single Claude Call Per Email

The key design decision: **one API call per email**, not multiple.

```
Email arrives
    ↓
luna_agent.py builds system prompt (SOUL.md + scenario descriptions)
    ↓
Claude (claude-sonnet-4-5) receives email + 3 tools available:
    - fetch_property_data   → looks up CSV
    - get_property_link     → looks up registry JSON
    - use_template          → returns predefined reply text
    ↓
Claude may call 0, 1, or 2 tools depending on email type
    ↓
Claude returns final reply body
    ↓
Pipeline sends via SMTP
```

### Template-First Logic

Claude is instructed to prefer templates when available:
- `tour_confirm` → template (no AI text needed)
- `tour_reschedule` → template
- `post_tour` → template
- `voucher` / `cosigner` / `credit` / etc. → policy template

For everything else (new leads, objections, complex inquiries), Claude drafts a custom reply using SOUL.md voice rules.

### Scenarios (10 categories)

Same as the original Luna system:
- `new_lead` — first contact from prospect
- `inquiry_reply` — follow-up question
- `tour_confirm` — showing confirmed
- `tour_reschedule` — showing canceled/rescheduled
- `post_tour` — after the showing
- `objection` — credit, deposit, lease term concerns
- `far_future` — wants to hold unit for distant move-in
- `re_engagement` — outbound follow-up
- `student_housing` — college student inquiry
- `logistical_other` — internal / skip

---

## What This POC Does NOT Include

- Telegram notifications (prints to console instead)
- MEMORY.md / lead pipeline tracking
- Idempotency store (same email could be processed twice if re-run)
- ShowMojo / Zillow / RentCafe portal-specific parsing
- Hourly scheduling (run manually)
- Gmail labeling (LUNA HANDLED etc.)

These can be added incrementally once the core loop is validated.

---

## Troubleshooting

**Error: "No module named 'anthropic'"**
```bash
pip install -r requirements.txt
```

**Error: "GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set"**
- Make sure `.env` file exists (not just `.env.example`)
- Make sure values are filled in correctly

**Error: "IMAP login failed"**
- Check your App Password is correct (no spaces)
- Make sure IMAP is enabled in Gmail settings
- Try re-generating the App Password

**No emails found**
- Send a test email to yourself first
- Make sure the email is unread in your inbox
- Run with `--max 20` to increase the limit

**Reply not sending**
- Check SMTP credentials are same as IMAP
- Gmail SMTP uses port 587 with STARTTLS (handled automatically)


---

## Testing & Validation

### Run the test suite:
```bash
python test_new_modes.py
```

This validates:
- ✓ Hard-stop keyword detection (ESCALATE mode)
- ✓ Unverified sensitive fact detection (DRAFT mode)
- ✓ Business hours checking (HOLD mode)

### Validate the implementation:
```bash
python validate_implementation.py
```

This checks:
- All required files are present
- Imports are working correctly
- Environment variables are configured
- Core functions are callable

### Test with real emails (safe mode):
```bash
python poc_pipeline.py --dry-run --max 5
```

This processes real emails but doesn't send any replies, allowing you to see what mode each email would trigger.

---

## New Modes Documentation

For detailed information about the 5 processing modes, see [MODES_DOCUMENTATION.md](MODES_DOCUMENTATION.md).

**Quick reference:**
- **SKIP** — noreply@ addresses, empty emails → no action
- **DRAFT** — mentions $rent without calling `get_unit_availability` → saved but not sent
- **ESCALATE** — contains "lawsuit", "application approved", "waive deposit" → manual review
- **HOLD** — outside 8 AM - 8 PM ET → saved for business hours
- **SENT** — verified reply with tools called → successfully sent

---

## Dashboard Statistics

The admin dashboard now tracks all 5 modes separately:

```json
{
  "total_emails": 100,
  "auto_sent": 65,       // SENT mode
  "drafts": 10,          // DRAFT mode  
  "on_hold": 8,          // HOLD mode
  "escalations": 12,     // ESCALATE mode
  "skipped": 5,          // SKIP mode
  "total_cost_usd": 2.45
}
```

Start the dashboard:
```bash
cd api
uvicorn main:app --reload --port 8000
```

View stats: http://localhost:8000/api/stats

---

## Configuration Updates

### Business Hours (.env)

Configure when emails should be sent (Eastern Time):

```env
SENDING_HOUR_START=8   # 8 AM ET (24-hour format: 0-23)
SENDING_HOUR_END=20    # 8 PM ET (24-hour format: 0-23)
```

Emails processed outside these hours will be saved with **HOLD** status.

### Hard-Stop Keywords

Edit `luna_agent.py` to customize which keywords trigger **ESCALATE** mode:

```python
HARD_STOP_KEYWORDS = [
    "lawsuit", "attorney", "legal notice",
    "application approved", "application denied",
    "waive deposit", "rent negotiation",
    # Add your custom keywords...
]
```

---

## Troubleshooting New Modes

**Issue: All emails going to DRAFT**
- The AI is mentioning rent/pricing without calling `get_unit_availability`
- This is correct behavior - it prevents sending unverified data
- Check Claude's prompts ensure tool usage instructions are clear

**Issue: HOLD not triggering**
- Verify `.env` has `SENDING_HOUR_START` and `SENDING_HOUR_END` set
- Check your system can detect Eastern Time (requires `zoneinfo` / `tzdata`)
- Run `python test_new_modes.py` to verify business hours logic

**Issue: ESCALATE too sensitive**
- Review `HARD_STOP_KEYWORDS` list in `luna_agent.py`
- Remove overly broad keywords that match normal inquiries
- Keywords are case-insensitive and match substrings

**Issue: Dashboard stats not updating**
- Restart FastAPI: `uvicorn api.main:app --reload --port 8000`
- Check `data/email_log.json` exists and is being written
- Clear browser cache and refresh

**Issue: "No module named 'zoneinfo'"**
- Windows Python < 3.9 may need: `pip install tzdata`
- Or update to Python 3.9+

