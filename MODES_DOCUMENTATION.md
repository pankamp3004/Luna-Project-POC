# Luna POC — Email Processing Modes

## Overview

Luna POC now supports **5 distinct processing modes** to handle different email scenarios safely and intelligently:

1. **SKIP** — System/automated emails that should never receive a reply
2. **DRAFT** — Replies with unverified sensitive data (saved but not sent)
3. **ESCALATE** — Hard-stop situations requiring manual review
4. **HOLD** — Replies ready to send but outside business hours
5. **SENT** — Successfully verified and sent replies

---

## Mode Details

### 1. SKIP Mode

**When it triggers:**
- Email is from a no-reply address (noreply@, donotreply@, etc.)
- Email is from your own Gmail address
- Email body is empty
- Email is from system/automated senders

**What happens:**
- No reply is generated
- Email is marked as read
- Logged with `status: "skipped"` and `decision: "SKIP"`

**Example:**
```
From: noreply@showmojo.com
Subject: Showing Confirmation
→ [SKIP] System/automated sender -- no reply sent
```

---

### 2. DRAFT Mode

**When it triggers:**
- Reply mentions rent, pricing, or deposit amounts **without** calling `get_unit_availability` tool
- This prevents sending unverified sensitive information

**Detection logic:**
```python
# Triggers DRAFT if reply contains:
- Dollar amounts: $1500, $2000
- Rent mentions: "rent is", "monthly rent"
- Deposit mentions: "deposit is", "security deposit"
- Pricing: "price is", "costs"

# AND get_unit_availability was NOT called
```

**What happens:**
- Reply is generated and saved
- Email is marked as read
- Reply is NOT sent
- Logged with `status: "draft"` and `decision: "DRAFT"`
- Available in dashboard for manual review and send

**Example:**
```
Email: "How much is the rent for Unit 16?"
AI Reply: "The rent is $1500/month"  [no tool called]
→ [DRAFT] Reply contains unverified data - saved as draft
```

**Correct flow (NO DRAFT):**
```
Email: "How much is the rent for Unit 16?"
AI: calls get_unit_availability(property_query="...", unit="16")
AI Reply: "The rent is $1500/month"  [verified by tool]
→ [REPLY GENERATED] Ready to send
```

---

### 3. ESCALATE Mode

**When it triggers:**
- Email contains any hard-stop keyword (legal, financial, application outcome)
- Checked **before** calling the Claude API to save costs

**Hard-stop keywords:**
```python
# Legal/Safety
- "voice message", "voicemail", "eviction", "lawsuit", 
  "attorney", "legal notice", "discrimination", "fair housing"

# Application Outcomes  
- "application approved", "application denied", "was i approved",
  "approval status", "why was i denied"

# Financial Disputes
- "deposit refund", "waive deposit", "reduce deposit",
  "refund", "concession", "lower the rent", "negotiate the rent",
  "rent too high"

# Fee Waivers
- "waive the fee", "waive application fee", "first month free",
  "free month", "no deposit"

# Lease Changes
- "lease termination", "lease renewal"
```

**What happens:**
- No reply is generated
- Email is marked as read
- Logged with `status: "escalated"` and `decision: "ESCALATE"`
- Manual review required before responding

**Example:**
```
From: prospect@email.com
Subject: Application Status
Body: "Was my application approved?"
→ [ESCALATE] Hard stop detected. Manual review required.
     This email contains legal/financial/sensitive content.
```

---

### 4. HOLD Mode

**When it triggers:**
- Reply is ready to send
- Current time (Eastern Time) is **outside** business hours
- Business hours: 8 AM - 8 PM ET (configurable in `.env`)

**Configuration (.env):**
```env
SENDING_HOUR_START=8   # 8 AM Eastern Time
SENDING_HOUR_END=20    # 8 PM Eastern Time
```

**What happens:**
- Reply is generated and saved
- Email is marked as read
- Reply is NOT sent immediately
- Logged with `status: "hold"` and `decision: "HOLD"`
- Should be dispatched when business hours resume

**Example:**
```
Current time: 11:30 PM ET
Email: "Is the 2BR still available?"
Reply generated successfully
→ [HOLD] Outside business hours - reply saved for later dispatch
     Business hours: 8 AM - 8 PM ET
```

**Note:** Current POC implementation saves HOLD emails but does not auto-dispatch them when business hours resume. This would require a scheduler/cron job to be implemented separately.

---

### 5. SENT Mode

**When it triggers:**
- Reply is generated successfully
- No hard-stop keywords detected
- No unverified sensitive facts
- Within business hours (or dry-run mode bypasses this)
- SMTP send succeeds

**What happens:**
- Reply is sent via Gmail SMTP
- Email is marked as read
- Logged with `status: "sent"` and `decision: "SEND"`

**Example:**
```
Email: "Is Unit 3 still available?"
AI: calls get_unit_availability, get_property_link
AI Reply: "Hi! Yes, Unit 3 is available. Schedule a tour here: [link]"
→ [REPLY GENERATED]
→ ✅ Reply sent to: prospect@email.com
```

---

## Decision Flow

```
┌─────────────────────────┐
│  Email arrives          │
└───────────┬─────────────┘
            │
            ▼
  ┌─────────────────────┐
  │ System email?       │
  │ (noreply, empty)    │
  └─────────┬───────────┘
            │
         YES├──→ SKIP
            │
         NO │
            ▼
  ┌─────────────────────┐
  │ Hard-stop keyword?  │
  │ (legal, financial)  │
  └─────────┬───────────┘
            │
         YES├──→ ESCALATE
            │
         NO │
            ▼
  ┌─────────────────────┐
  │ Call Claude API     │
  │ Generate reply      │
  └─────────┬───────────┘
            │
            ▼
  ┌─────────────────────┐
  │ Reply has unverified│
  │ rent/pricing?       │
  └─────────┬───────────┘
            │
         YES├──→ DRAFT
            │
         NO │
            ▼
  ┌─────────────────────┐
  │ Within business hrs?│
  │ (8AM-8PM ET)        │
  └─────────┬───────────┘
            │
         NO ├──→ HOLD
            │
         YES│
            ▼
  ┌─────────────────────┐
  │ Send via SMTP       │
  └─────────┬───────────┘
            │
            ▼
          SENT
```

---

## Dashboard Statistics

The admin dashboard (`/api/stats`) now tracks all 5 modes:

```json
{
  "total_emails": 100,
  "auto_sent": 65,        // SENT mode
  "drafts": 10,           // DRAFT mode
  "on_hold": 8,           // HOLD mode
  "escalations": 12,      // ESCALATE mode
  "skipped": 5,           // SKIP mode
  "total_cost_usd": 2.45,
  "llm_calls": 85,
  "template_calls": 10
}
```

---

## Testing the New Modes

### 1. Run the test suite:
```bash
python test_new_modes.py
```

This validates:
- ✓ Hard-stop keyword detection
- ✓ Unverified sensitive fact detection  
- ✓ Business hours checking

### 2. Test with real emails (dry-run):
```bash
python poc_pipeline.py --dry-run --max 5
```

### 3. Test specific scenarios:

**Test ESCALATE:**
Send email with subject: "Was my application approved?"
Expected: `[ESCALATE] Hard stop detected`

**Test DRAFT:**
Send email: "How much is rent?"
If AI replies without calling get_unit_availability → DRAFT

**Test HOLD:**
Run pipeline outside 8AM-8PM ET
Expected: `[HOLD] Outside business hours`

**Test SENT:**
Send email: "Is Unit 3 available?"
Run during business hours with dry-run=False
Expected: `✅ Reply sent`

---

## Configuration

### Environment Variables (.env)

```env
# Business hours for HOLD mode
SENDING_HOUR_START=8   # 8 AM Eastern Time (24-hour format: 0-23)
SENDING_HOUR_END=20    # 8 PM Eastern Time (24-hour format: 0-23)

# Gmail credentials
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Reply sender info
REPLY_FROM_NAME=Luna
REPLY_FROM_EMAIL=your-email@gmail.com

# Claude API
ANTHROPIC_API_KEY=sk-ant-...
```

### Customizing Hard-Stop Keywords

Edit `luna_agent.py`:

```python
HARD_STOP_KEYWORDS = [
    # Add your custom keywords here
    "custom keyword",
    "another phrase",
    # ... existing keywords
]
```

---

## Dry-Run Mode

Dry-run mode processes emails and generates replies but **does not send** anything:

```bash
python poc_pipeline.py --dry-run --max 10
```

**Behavior in dry-run:**
- SKIP: still skipped
- ESCALATE: still escalated
- DRAFT: still drafted (not sent)
- HOLD: **bypassed** (shows reply but doesn't check hours)
- SENT: shows reply but doesn't actually send

All modes are logged to `data/email_log.json` for review.

---

## Implementation Notes

### Why check hard-stops BEFORE calling Claude?
- Saves API costs (no LLM call for escalated emails)
- Faster response time
- Guaranteed consistency (no AI hallucination on sensitive topics)

### Why DRAFT unverified pricing?
- Prevents sending incorrect rent amounts to prospects
- Forces the AI to call `get_unit_availability` for accurate data
- Reduces liability from misinformation

### Why HOLD outside business hours?
- Professional appearance (no 3 AM emails)
- Compliance with communication best practices
- Gives human oversight window for held replies

---

## Future Enhancements

1. **Auto-dispatch HOLD emails**: Add a scheduler to automatically send HOLD emails when business hours resume

2. **Manual DRAFT review**: Dashboard UI to review and manually send/edit drafted emails

3. **ESCALATE routing**: Auto-notify specific team members via Slack/email when escalations occur

4. **Smart DRAFT override**: Allow specific phrases to bypass DRAFT (e.g., "As discussed, the rent is...")

5. **Business hours by property**: Different hours for different properties/markets

6. **HOLD priority queue**: Prioritize certain emails for immediate send when hours resume

---

## Troubleshooting

**Issue: All emails going to DRAFT**
- Check if `get_unit_availability` tool is being called
- Review Claude's system prompt to ensure tool usage instructions are clear
- Test with a simpler query that explicitly asks about a unit number

**Issue: HOLD not triggering**
- Verify `.env` has `SENDING_HOUR_START` and `SENDING_HOUR_END`
- Check system timezone is correctly detecting Eastern Time
- Run `python test_new_modes.py` to verify business hours logic

**Issue: ESCALATE too aggressive**
- Review `HARD_STOP_KEYWORDS` list in `luna_agent.py`
- Remove overly broad keywords
- Consider context-aware detection (future enhancement)

**Issue: Dashboard stats not updating**
- Restart FastAPI server: `uvicorn api.main:app --reload --port 8000`
- Clear browser cache and refresh dashboard
- Check `data/email_log.json` to verify logs are being written

---

## Summary

The new 5-mode system provides:
- ✅ **Safety**: Hard-stops prevent risky auto-replies
- ✅ **Accuracy**: DRAFT mode ensures verified data
- ✅ **Professionalism**: HOLD mode respects business hours
- ✅ **Transparency**: All modes logged and visible in dashboard
- ✅ **Cost efficiency**: ESCALATE checked before API call

All existing functionality remains intact. The new modes layer on top of the existing system without breaking changes.
