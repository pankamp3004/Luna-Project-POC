"""
Debug: Shanae's RentCafe email — should NOT call get_unit_availability
Prospect message: "Hi, I found 1017 Pine Street on RentCafe and I really like it.
Please contact me to discuss details about moving here. Move-in: 6/12/2026."
"""
from gmail_client import InboundEmail
from luna_agent import process_email

email = InboundEmail(
    uid="shanae-test",
    message_id="<shanae@test.com>",
    from_name="Shanae Austin",
    from_addr="shanae.austin93@gmail.com",
    to_addr="leasing@tristarrei.com",
    subject="1017 Pine Street - Details and Tour Info",
    body="""Shanae Austin via RentCafe: Hi, I found 1017 Pine Street on RentCafe.com and I really like it. Please contact me to discuss details about moving here.
Move-in: 6/12/2026. Phone: 9373297760.""",
    date="Mon, 1 Jun 2026 21:08:00 +0000"
)

print("=" * 70)
print("TEST: Shanae RentCafe email — 'I like it, contact me, move-in 6/12'")
print("Expected: ONLY get_property_link (NOT get_unit_availability)")
print("=" * 70)

result = process_email(email)

print(f"\n  Tools called : {result['tools_called']}")
print(f"  Input tokens : {result['input_tokens']:,}")
print(f"\n  Reply:\n{result['reply']}")

print("\n" + "=" * 70)
if "get_unit_availability" not in result["tools_called"]:
    print("✓ PASSED")
else:
    print("✗ FAILED: get_unit_availability called — debugging needed")
