# Decision-Status Mapping Reference

## Correct Mapping Table

| Mode | `decision` Field | `status` Field | When | Sent? |
|------|-----------------|----------------|------|-------|
| **SKIP** | `"SKIP"` | `"skipped"` | System email (noreply@, empty body) | No |
| **DRAFT** | `"DRAFT"` | `"draft"` | Unverified rent/pricing in reply | No |
| **ESCALATE** | `"ESCALATE"` | `"escalated"` | Hard-stop keywords detected | No |
| **HOLD** | `"HOLD"` | `"hold"` | Outside business hours (8 AM - 8 PM ET) | No |
| **SENT** | `"SEND"` | `"sent"` | Normal verified reply sent | Yes |
| **DRY-RUN** | `"SKIP"` | `"skipped"` | Dry-run mode (testing) | No |
| **ERROR** | `"SKIP"` or original | `"error"` | Processing failed | No |

## Dashboard Stats Calculation

```python
# From email_log.py get_stats()
auto_sent = sum(1 for r in records if r.get("status") == "sent")
drafts = sum(1 for r in records if r.get("status") == "draft" or r.get("decision") == "DRAFT")
on_hold = sum(1 for r in records if r.get("status") == "hold" or r.get("decision") == "HOLD")
skipped = sum(1 for r in records if r.get("status") == "skipped" and r.get("decision") == "SKIP")
escalations = sum(1 for r in records if r.get("status") == "escalated")
```

## Dashboard Filter Mapping

```python
# From api/main.py _filter_by_status()
if status_lower == "sent":
    return [r for r in records if r.get("status") == "sent"]
elif status_lower == "draft":
    return [r for r in records if r.get("status") == "draft" or r.get("decision") == "DRAFT"]
elif status_lower == "hold":
    return [r for r in records if r.get("status") == "hold" or r.get("decision") == "HOLD"]
elif status_lower == "skipped":
    return [r for r in records if r.get("status") == "skipped" and r.get("decision") == "SKIP"]
elif status_lower == "escalated":
    return [r for r in records if r.get("status") == "escalated"]
```

## Console Output Labels

| Mode | Console Output |
|------|---------------|
| SKIP | `[SKIP] System/automated sender -- no reply sent` |
| DRAFT | `[DRAFT] Reply contains unverified data - saved as draft` |
| ESCALATE | `[ESCALATE] Hard stop detected. Manual review required.` |
| HOLD | `[HOLD] Outside business hours - reply saved for later dispatch` |
| SENT | `✅ Reply sent to: prospect@email.com` |
| DRY-RUN | `[DRY RUN] Reply NOT sent (run without --dry-run to send)` |

## Validation Rules

### SKIP Mode
- ✅ System email detection (noreply@, empty body)
- ✅ `decision: "SKIP"`, `status: "skipped"`
- ✅ No LLM call, no reply generated

### DRAFT Mode
- ✅ Reply mentions rent/pricing WITHOUT calling `get_unit_availability`
- ✅ `decision: "DRAFT"`, `status: "draft"`
- ✅ Reply generated but NOT sent
- ✅ Full reply saved to `full_reply` field

### ESCALATE Mode
- ✅ Hard-stop keyword detected BEFORE LLM call
- ✅ `decision: "ESCALATE"`, `status: "escalated"`
- ✅ No reply generated (saves API cost)
- ✅ Manual review required

### HOLD Mode
- ✅ Reply ready to send but outside business hours
- ✅ `decision: "HOLD"`, `status: "hold"`
- ✅ Reply saved for later dispatch
- ✅ Full reply saved to `full_reply` field

### SENT Mode
- ✅ Normal verified reply
- ✅ `decision: "SEND"`, `status: "sent"`
- ✅ SMTP send successful
- ✅ Email marked as read

### DRY-RUN Mode
- ✅ Testing mode, no actual send
- ✅ `decision: "SKIP"`, `status: "skipped"`
- ✅ Reply generated and displayed but not sent
- ✅ Note shown: "DRY RUN - Reply NOT sent"

## Common Issues & Fixes

### Issue: Decision shows "SKIP" but status is "hold"
**Cause:** Inconsistent field assignment in pipeline code  
**Fix:** Ensure all log_email_processing calls use correct decision/status pairs

### Issue: Dashboard shows 0 for "Skipped"
**Cause:** Stats calculation not counting skipped correctly  
**Fix:** Verify `skipped` field is in API stats response and dashboard is reading it

### Issue: All emails going to DRAFT in dry-run
**Cause:** Dry-run was using `decision: "DRAFT"` instead of `decision: "SKIP"`  
**Fix:** Changed dry-run to use `decision: "SKIP"`, `status: "skipped"`

### Issue: HOLD not triggering
**Cause:** Business hours not configured or timezone issue  
**Fix:** Add `SENDING_HOUR_START` and `SENDING_HOUR_END` to `.env`

## Testing Checklist

- [ ] SKIP: Send from noreply@ address → Should skip
- [ ] DRAFT: Reply mentions rent without tool → Should draft
- [ ] ESCALATE: Email contains "lawsuit" → Should escalate
- [ ] HOLD: Run outside 8 AM - 8 PM ET → Should hold
- [ ] SENT: Normal email during business hours → Should send
- [ ] DRY-RUN: Run with `--dry-run` flag → Should skip with note
- [ ] Dashboard: All 7 cards showing (Total, Sent, Drafts, Hold, Escalations, Skipped, Cost)
- [ ] Dashboard: Filter by each status → Shows correct emails
- [ ] Dashboard: Stats add up correctly → Total = Sent + Drafts + Hold + Escalations + Skipped

## Code Locations

### Decision/Status Assignment
- `poc_pipeline.py` lines 180-480 (all log_email_processing calls)
- `luna_agent.py` lines 150-180 (ESCALATE check returns decision)

### Stats Calculation
- `email_log.py` lines 80-120 (get_stats function)
- `api/main.py` lines 50-100 (_filter_by_status function)

### Dashboard Display
- `dashboard/src/pages/Dashboard.jsx` lines 200-250 (StatsCard grid)
- `dashboard/src/components/StatsCard.jsx` (Card component)

## API Response Example

```json
{
  "total_emails": 100,
  "auto_sent": 60,      // status == "sent"
  "drafts": 12,         // status == "draft" OR decision == "DRAFT"
  "on_hold": 8,         // status == "hold" OR decision == "HOLD"
  "escalations": 10,    // status == "escalated"
  "skipped": 10,        // status == "skipped" AND decision == "SKIP"
  "total_cost_usd": 2.45,
  "llm_calls": 70,
  "template_calls": 20
}
```

Note: Total might not exactly equal the sum of mode counts if there are error records.
