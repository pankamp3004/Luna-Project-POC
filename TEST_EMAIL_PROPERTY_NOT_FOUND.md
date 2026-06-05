# Test Email - Property Not Found (DRAFT Mode)

## Test Email to Send

Send this email to your Gmail address to test the new DRAFT detection for non-existent properties:

---

**From:** Your personal email  
**To:** Your Luna Gmail (from `.env`)  
**Subject:** Inquiry about 999 Nonexistent Avenue

**Body:**
```
Hi Luna,

I saw a listing online for the apartment at 999 Nonexistent Avenue in Syracuse, NY.

Can you tell me if it's still available? What's the monthly rent and when can I move in?

I'm very interested and would like to schedule a tour this week.

Thanks,
Alex Johnson
```

---

## Expected Behavior

### 1. **AI Processing:**
- Claude reads the email
- Identifies property: "999 Nonexistent Avenue"
- Calls tool: `fetch_property_data("999 Nonexistent Avenue")`
- Tool returns: `{"found": False, "message": "No property found matching '999 Nonexistent Avenue'"}`

### 2. **AI Reply Generated:**
```
Hi Alex,

I appreciate your interest! However, I don't have any listing information for 
999 Nonexistent Avenue in our current portfolio. 

It's possible this property is no longer available, or there may be a different 
address. Could you double-check the address or let me know where you saw the listing?

I'd be happy to help you find a similar property in Syracuse that might work for you!

Luna, Tri Star Realty
```

### 3. **System Detection:**
```
[TOOL]  Claude calling: fetch_property_data({"property_query":"999 Nonexistent Avenue"})
[TOOL]  Result: {'found': False, 'message': "No property found matching '999 Nonexistent Avenue'"}
[DRAFT] Reply references property not found in our data
```

### 4. **Result:**
- ✅ Decision: **DRAFT**
- ✅ Status: `draft`
- ✅ Reply saved to `full_reply` field
- ❌ **NOT sent** to prospect

### 5. **Dashboard:**
- Decision column: **DRAFT** (yellow badge)
- Status: **Draft**
- Classification: LLM + Tools (Claude)
- Can be reviewed and manually sent after human verification

---

## How to Test

### Step 1: Send the test email
```bash
# Send from another email to your Luna Gmail address
```

### Step 2: Run the pipeline
```bash
python poc_pipeline.py --max 1
```

### Step 3: Check the console output
Look for:
```
[DRAFT] Reply references property not found in our data
```

### Step 4: Check the log file
```bash
# View the last entry
python -c "import json; lines = open('data/email_log.json').readlines(); print(json.dumps(json.loads(lines[-1]), indent=2))"
```

Expected fields:
```json
{
  "decision": "DRAFT",
  "status": "draft",
  "tools_called": ["fetch_property_data"],
  ...
}
```

### Step 5: Check the dashboard
```bash
# Start dashboard if not running
cd dashboard && npm run dev
```

Visit: http://localhost:3000/inbox

- Filter by: **Drafts**
- Find your test email
- Click to view details
- See the generated reply that was NOT sent

---

## Additional Test Cases

### Test 2: Wrong Property Name
**Subject:** Question about Main Street Property  
**Body:**
```
Hi, I'm interested in the apartment at "Main Street Building" in downtown.
What's available?
```

**Expected:**
- Tool returns: `found: False` (ambiguous/non-existent)
- Decision: **DRAFT**

---

### Test 3: Typo in Address
**Subject:** 50 W Brighton Ave inquiry  
**Body:**
```
Hi, I saw the listing for 50 W Brighton Ave (note: should be 508).
Is Unit 10 still available?
```

**Expected:**
- Tool returns: `found: False` (address doesn't match)
- Decision: **DRAFT**

---

### Test 4: Property Exists (Control Test)
**Subject:** Inquiry about 508 W Brighton Ave  
**Body:**
```
Hi, I'm interested in Unit 16 at 508 W Brighton Ave.
What's the rent and is it available?
```

**Expected:**
- Tool returns: `found: True` with actual data
- Decision: **SEND** (or HOLD if outside business hours)
- Reply includes verified rent information

---

## Comparison Table

| Property Query | Tool Result | Decision | Sent? |
|----------------|-------------|----------|-------|
| "999 Nonexistent Ave" | `found: False` | **DRAFT** | ❌ No |
| "Main Street Building" | `found: False` | **DRAFT** | ❌ No |
| "50 W Brighton" (typo) | `found: False` | **DRAFT** | ❌ No |
| "508 W Brighton Ave" | `found: True` | **SEND** | ✅ Yes |

---

## What Happens in DRAFT?

### 1. **Email Marked as Read**
- Original email is marked as read in Gmail
- Prevents duplicate processing

### 2. **Reply Saved**
- Full reply text saved to `full_reply` field in log
- Preview saved to `reply_preview` field

### 3. **Dashboard Shows Draft**
- Email appears in "Drafts" section
- Human can review the reply
- Option to manually send (future feature)

### 4. **No Auto-Send**
- Reply is NOT sent via SMTP
- No email reaches the prospect
- Human must manually send if appropriate

---

## Why This is Better

### Before This Enhancement:
1. Prospect asks about non-existent property
2. AI replies: "We don't have that property"
3. Reply is **auto-sent**
4. Prospect is confused (maybe they had wrong address)
5. Opportunity lost

### After This Enhancement:
1. Prospect asks about non-existent property
2. AI generates helpful reply
3. System detects `found: False`
4. Reply is **saved as DRAFT**
5. Human reviews and can:
   - Clarify the correct address
   - Suggest similar properties
   - Ask where they saw the listing
   - Provide better customer service

---

## Success Criteria

✅ Test email sent  
✅ Pipeline processes email  
✅ Tool returns `found: False`  
✅ Console shows: `[DRAFT] Reply references property not found in our data`  
✅ Log file shows: `"decision": "DRAFT", "status": "draft"`  
✅ Dashboard shows email in "Drafts" section  
✅ Reply NOT sent to prospect  
✅ Full reply text saved for human review  

---

**Ready to test! Send the email and run the pipeline.** 🚀
