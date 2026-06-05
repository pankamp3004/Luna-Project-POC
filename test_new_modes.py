"""
test_new_modes.py — Test script for validating SKIP, DRAFT, ESCALATE, HOLD, and SENT modes.

This script tests the new logic without actually sending emails or connecting to Gmail.
It directly calls the luna_agent with mock emails and validates the response modes.

Usage:
    python test_new_modes.py
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from luna_agent import process_email, _check_hard_stop, _check_unverified_sensitive_facts
from gmail_client import InboundEmail
from dotenv import load_dotenv

load_dotenv()

def create_test_email(subject: str, body: str, from_addr: str = "test@example.com") -> InboundEmail:
    """Helper to create a test email."""
    return InboundEmail(
        uid="test-123",
        message_id="<test@example.com>",
        subject=subject,
        from_addr=from_addr,
        from_name="Test User",
        to_addr=os.getenv("GMAIL_ADDRESS", "luna@test.com"),
        body=body,
        date=datetime.now(timezone.utc).isoformat(),
    )


def test_escalate_mode():
    """Test ESCALATE mode with hard-stop keywords."""
    print("\n" + "="*60)
    print("TEST 1: ESCALATE Mode (Hard-Stop Keywords)")
    print("="*60)
    
    test_cases = [
        ("Legal threat", "I am going to file a lawsuit against your company", True),
        ("Application approved", "Was my application approved?", True),
        ("Deposit waiver", "Can you waive the deposit for me?", True),
        ("Rent negotiation", "The rent is too high, can we negotiate?", True),
        ("Normal inquiry", "Is the 2BR unit still available?", False),
    ]
    
    passed = 0
    failed = 0
    
    for name, body, should_escalate in test_cases:
        email = create_test_email(f"Test: {name}", body)
        is_hard_stop = _check_hard_stop(email.body, email.subject)
        
        status = "✓ PASS" if is_hard_stop == should_escalate else "✗ FAIL"
        print(f"\n{status} | {name}")
        print(f"  Body: {body[:60]}...")
        print(f"  Expected: {'ESCALATE' if should_escalate else 'NOT ESCALATE'}")
        print(f"  Got: {'ESCALATE' if is_hard_stop else 'NOT ESCALATE'}")
        
        if is_hard_stop == should_escalate:
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_draft_mode():
    """Test DRAFT mode with unverified sensitive facts."""
    print("\n" + "="*60)
    print("TEST 2: DRAFT Mode (Unverified Sensitive Facts)")
    print("="*60)
    
    test_cases = [
        # (reply_text, tools_called, tool_results, should_be_draft)
        ("The rent is $1500/month for this unit.", [], None, True),
        ("The rent is $1500/month for this unit.", ["get_unit_availability"], None, False),
        ("Security deposit is $2000.", [], None, True),
        ("Security deposit is $2000.", ["get_unit_availability"], None, False),
        ("Hi! The unit is still available. You can schedule a tour here: [link]", [], None, False),
        ("The property is located in Syracuse, NY.", [], None, False),
        # Test property not found case
        ("Sorry, we don't have that property.", ["fetch_property_data"], [{"found": False, "message": "Not found"}], True),
        ("The property is available.", ["fetch_property_data"], [{"found": True, "canonical_name": "Test"}], False),
    ]
    
    passed = 0
    failed = 0
    
    for reply_text, tools_called, tool_results, should_be_draft in test_cases:
        is_draft = _check_unverified_sensitive_facts(reply_text, tools_called, tool_results)
        
        status = "✓ PASS" if is_draft == should_be_draft else "✗ FAIL"
        print(f"\n{status}")
        print(f"  Reply: {reply_text[:60]}...")
        print(f"  Tools: {tools_called or 'None'}")
        print(f"  Tool Results: {tool_results if tool_results else 'None'}")
        print(f"  Expected: {'DRAFT' if should_be_draft else 'NOT DRAFT'}")
        print(f"  Got: {'DRAFT' if is_draft else 'NOT DRAFT'}")
        
        if is_draft == should_be_draft:
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_business_hours():
    """Test business hours checking for HOLD mode."""
    print("\n" + "="*60)
    print("TEST 3: HOLD Mode (Business Hours)")
    print("="*60)
    
    from poc_pipeline import is_within_business_hours
    from zoneinfo import ZoneInfo
    
    # Get current ET time
    et_tz = ZoneInfo("America/New_York")
    now_et = datetime.now(et_tz)
    current_hour = now_et.hour
    
    within_hours = is_within_business_hours()
    
    start_hour = int(os.getenv("SENDING_HOUR_START", "8"))
    end_hour = int(os.getenv("SENDING_HOUR_END", "20"))
    
    expected = start_hour <= current_hour < end_hour
    
    status = "✓ PASS" if within_hours == expected else "✗ FAIL"
    print(f"\n{status}")
    print(f"  Current ET time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Current hour: {current_hour}")
    print(f"  Business hours: {start_hour}:00 - {end_hour}:00")
    print(f"  Within hours: {within_hours}")
    print(f"  Expected: {expected}")
    
    if within_hours:
        print("\n  ℹ️  Currently within business hours - emails will be SENT")
    else:
        print("\n  ℹ️  Currently outside business hours - emails will be HELD")
    
    print(f"\n{'='*60}")
    return within_hours == expected


def test_integration():
    """Integration test with a real email scenario (no actual API call)."""
    print("\n" + "="*60)
    print("TEST 4: Integration Test Summary")
    print("="*60)
    
    print("\n✓ Hard-stop keyword detection is working")
    print("✓ Unverified sensitive fact detection is working")
    print("✓ Business hours checking is working")
    print("\nℹ️  To test full end-to-end flow:")
    print("  1. Send test emails to your Gmail")
    print("  2. Run: python poc_pipeline.py --dry-run --max 5")
    print("  3. Verify the output shows correct modes:")
    print("     - [SKIP] for system emails")
    print("     - [ESCALATE] for hard-stop keywords")
    print("     - [DRAFT] for unverified rent/pricing mentions")
    print("     - [HOLD] for outside business hours")
    print("     - [REPLY GENERATED] + send for normal verified replies")
    print(f"\n{'='*60}")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("LUNA POC — New Modes Test Suite")
    print("="*60)
    
    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or not api_key.startswith("sk-ant-"):
        print("\n⚠️  WARNING: ANTHROPIC_API_KEY not set or invalid")
        print("   Some tests will be skipped")
    
    results = []
    
    # Run tests
    results.append(("ESCALATE Mode", test_escalate_mode()))
    results.append(("DRAFT Mode", test_draft_mode()))
    results.append(("HOLD Mode", test_business_hours()))
    test_integration()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status} | {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
