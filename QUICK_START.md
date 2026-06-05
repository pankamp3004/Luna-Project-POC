# Luna POC — Quick Start Guide (New Modes)

## ✅ What's New

Your Luna POC now has **5 intelligent processing modes**:

| Mode | When It Triggers | What Happens |
|------|------------------|--------------|
| **SKIP** | System emails (noreply@) | No reply generated |
| **DRAFT** | Unverified rent/pricing | Reply saved but not sent |
| **ESCALATE** | Hard-stop keywords | Manual review required |
| **HOLD** | Outside business hours | Saved for business hours |
| **SENT** | Verified normal reply | Successfully sent |

---

## 🚀 Quick Setup (3 Steps)

### 1. Update your `.env` file (Optional)

Add business hours configuration:

```env
SENDING_HOUR_START=8   # 8 AM Eastern Time
SENDING_HOUR_END=20    # 8 PM Eastern Time
```

If you don't add these, the system uses defaults: 8 AM - 8 PM ET.

### 2. Verify Everything Works

```bash
python validate_implementation.py
```

Expected output: `✓ ALL VALIDATIONS PASSED`

### 3. Test It

```bash
python poc_pipeline.py --dry-run --max 5
```

This processes real emails without sending anything.

---

## 📊 What You'll See

### Example: Normal Email (SENT)
```
Email: "Is Unit 3 still available?"
→ [REPLY GENERATED]
→ ✅ Reply sent to: prospect@email.com
```

### Example: Pricing Question without Tool Call (DRAFT)
```
Email: "How much is rent?"
AI mentions rent without calling get_unit_availability
→ [DRAFT] Reply contains unverified data - saved as draft
```

### Example: Legal Threat (ESCALATE)
```
Email: "I'm going to file a lawsuit"
→ [ESCALATE] Hard stop detected. Manual review required.
```

### Example: Late Night Email (HOLD)
```
Email arrives at 11:30 PM ET
→ [HOLD] Outside business hours - reply saved for later dispatch
   Business hours: 8 AM - 8 PM ET
```

---

## 🧪 Test Each Mode

### Test ESCALATE Mode

Send yourself an email with subject: **"Was my application approved?"**

Run pipeline:
```bash
python poc_pipeline.py --dry-run --max 1
```

Expected: `[ESCALATE] Hard stop detected`

---

### Test DRAFT Mode

This requires testing with the actual AI, but here's what to look for:

Send email: **"How much is the rent for Unit 16?"**

If AI replies with a dollar amount without calling `get_unit_availability`:
```
→ [DRAFT] Reply contains unverified data - saved as draft
```

If AI correctly calls the tool first:
```
→ [REPLY GENERATED] ... (normal send)
```

---

### Test HOLD Mode

Run pipeline outside business hours (before 8 AM or after 8 PM ET):
```bash
python poc_pipeline.py --dry-run --max 1
```

Check the output for: `[HOLD] Outside business hours`

**Note:** Dry-run mode bypasses HOLD checking. To test HOLD, run without `--dry-run`.

---

### Test SENT Mode (Normal)

Send a normal inquiry email: **"Is the 2BR apartment still available?"**

Run during business hours:
```bash
python poc_pipeline.py --max 1
```

Expected: `✅ Reply sent to: your@email.com`

---

## 📈 Dashboard Stats

Start the dashboard:
```bash
cd api
uvicorn main:app --reload --port 8000
```

Visit: http://localhost:8000/api/stats

You'll see:
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

**Dashboard Cards:** You'll now see 7 stat cards:
1. Total Emails
2. Auto-Sent (green)
3. Drafts (yellow)
4. On Hold (orange)
5. Escalations (red)
6. Skipped (gray)
7. AI Cost Total (purple)

---

## 🔧 Customization

### Change Business Hours

Edit `.env`:
```env
SENDING_HOUR_START=9   # 9 AM
SENDING_HOUR_END=18    # 6 PM
```

### Add More Hard-Stop Keywords

Edit `luna_agent.py`:
```python
HARD_STOP_KEYWORDS = [
    # Your custom keywords
    "custom phrase",
    "another trigger",
    # ... existing keywords
]
```

### Adjust DRAFT Detection

Edit `luna_agent.py` function `_check_unverified_sensitive_facts()` to customize which patterns trigger DRAFT mode.

---

## 🆘 Troubleshooting

### "All emails going to DRAFT"

**This is correct behavior!** It means the AI is mentioning rent/pricing without calling the `get_unit_availability` tool.

**Fix:** The AI should learn to call the tool when prospects ask about pricing. Check your prompt in `luna_agent.py` ensures tool usage is emphasized.

---

### "HOLD not working"

1. Check `.env` has `SENDING_HOUR_START` and `SENDING_HOUR_END`
2. Verify you're NOT using `--dry-run` (dry-run bypasses HOLD)
3. Run: `python test_new_modes.py` to verify business hours logic

---

### "ESCALATE too sensitive"

Some keywords might be too broad. Edit `HARD_STOP_KEYWORDS` in `luna_agent.py` to remove overly aggressive keywords.

---

### "Dashboard not showing new stats"

1. Restart API: `uvicorn api.main:app --reload --port 8000`
2. Clear browser cache
3. Check `data/email_log.json` exists and has recent entries

---

## 📚 More Information

- **Detailed Guide**: See `MODES_DOCUMENTATION.md` (50+ pages)
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Main README**: See `README.md` (updated with new modes)

---

## ✅ Validation Checklist

Before using in production:

- [ ] Run `python validate_implementation.py` → all passing
- [ ] Run `python test_new_modes.py` → all passing
- [ ] Test with `--dry-run` on real emails → modes working correctly
- [ ] Send test email with hard-stop keyword → escalates properly
- [ ] Check dashboard stats → showing all 5 modes
- [ ] Verify business hours in `.env` → set to your preferences
- [ ] Test during and outside business hours → HOLD working

---

## 🎯 Key Points

1. **ESCALATE saves money** — hard-stops checked BEFORE calling Claude API
2. **DRAFT prevents mistakes** — won't send unverified rent amounts
3. **HOLD is professional** — no 3 AM emails to prospects
4. **All modes logged** — complete transparency in dashboard
5. **Backward compatible** — existing functionality unchanged

---

## 🚦 Production Ready

✅ All tests passing  
✅ All validations passing  
✅ Backward compatible  
✅ Comprehensive logging  
✅ Dashboard integration  

**Your Luna POC is ready to use with the new 5-mode system!**

---

## 💡 Quick Commands Reference

```bash
# Validate setup
python validate_implementation.py

# Run tests
python test_new_modes.py

# Test with real emails (safe)
python poc_pipeline.py --dry-run --max 5

# Production mode
python poc_pipeline.py --max 10

# Start dashboard
cd api && uvicorn main:app --reload --port 8000

# View stats
curl http://localhost:8000/api/stats
```

---

**Questions?** Check `MODES_DOCUMENTATION.md` for detailed explanations of each mode.
