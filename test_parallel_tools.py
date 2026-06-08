"""
Quick test: verify parallel tool calling works correctly.
Tests 3 scenarios:
  1. Objection (short_term_lease) — was 3 iterations, should now be 2
  2. New lead pricing — still 2 iterations, tools called in parallel
  3. Rental assistance only — still 2 iterations, single tool
"""
from gmail_client import InboundEmail
from luna_agent import process_email


def run(label, subject, body):
    email = InboundEmail(
        uid="t1", message_id="<t@t.com>",
        from_name="Test User", from_addr="test@example.com",
        to_addr="leasing@tristarrei.com",
        subject=subject, body=body,
        date="Mon, 8 Jun 2026 10:00:00 +0000"
    )
    print(f"\n{'='*70}")
    print(f"TEST: {label}")
    print(f"{'='*70}")
    result = process_email(email)
    print(f"\n  tools_called  : {result['tools_called']}")
    print(f"  template_used : {result['template_used']}")
    print(f"  input_tokens  : {result['input_tokens']:,}")
    print(f"  reply preview : {(result['reply'] or '')[:120]}")
    return result


# Test 1: Objection — short term lease (was 18k tokens, should be ~12k now)
r1 = run(
    "OBJECTION — short-term lease (was 3 iter/18k tokens)",
    "Carly Griffin says: I would like to schedule a tour. Lease Length: 1 months. Property: 1913 S 20th St #4, Philadelphia, PA, 19145.",
    "Carly Griffin says: I would like to schedule a tour. Lease Length: 1 months. Income: . Number of Bedrooms: 1. Occupants: 1. Property: 1913 S 20th St #4, Philadelphia, PA, 19145."
)

# Test 2: New lead with pricing (parallel get_unit_availability + get_property_link)
r2 = run(
    "NEW LEAD — pricing question (parallel tools)",
    "Inquiry about 1913 South 20th Street",
    "Hi, I'm interested in 1913 South 20th Street. How much is rent? Thanks, Joanne"
)

# Test 3: Rental assistance only — single tool, no pricing
r3 = run(
    "RENTAL ASSISTANCE — no pricing (single tool)",
    "Do you accept Rapid Rehousing?",
    "Hi, I have a Rapid Rehousing voucher. Do you accept it at 1913 South 20th Street?"
)

print(f"\n{'='*70}")
print("SUMMARY — Token Savings:")
print(f"{'='*70}")
print(f"  Objection (short_term_lease) : {r1['input_tokens']:,} tokens  (was ~18,500 → saved ~{18500 - r1['input_tokens']:,})")
print(f"  New lead + pricing           : {r2['input_tokens']:,} tokens")
print(f"  Rental assistance only       : {r3['input_tokens']:,} tokens")

# Validations
errors = []
if "use_template" in r1["tools_called"] and "get_property_link" in r1["tools_called"]:
    print("\n  ✓ Objection: both tools called (parallel)")
else:
    errors.append("Objection: expected both get_property_link + use_template")

if r1["input_tokens"] < 15000:
    print(f"  ✓ Objection: tokens reduced below 15k ({r1['input_tokens']:,})")
else:
    errors.append(f"Objection: tokens still high ({r1['input_tokens']:,})")

if "get_unit_availability" not in r3["tools_called"]:
    print("  ✓ Rental assistance: get_unit_availability NOT called (correct)")
else:
    errors.append("Rental assistance: get_unit_availability should NOT be called")

if errors:
    print("\n  FAILURES:")
    for e in errors:
        print(f"    ✗ {e}")
else:
    print("\n  All checks passed ✓")
