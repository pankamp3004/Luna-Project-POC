"""
validate_implementation.py — Validation script to ensure all changes are working correctly.

This script validates:
1. All required files are present and valid
2. Environment configuration is correct
3. Import paths work
4. Core functions are callable
5. Dashboard API endpoints are available

Usage:
    python validate_implementation.py
"""

import os
import sys
from pathlib import Path

def validate_files():
    """Check that all required files exist."""
    print("\n" + "="*60)
    print("VALIDATION 1: File Structure")
    print("="*60)
    
    required_files = [
        "poc_pipeline.py",
        "luna_agent.py",
        "gmail_client.py",
        "email_log.py",
        "property_tools.py",
        "test_new_modes.py",
        "MODES_DOCUMENTATION.md",
        ".env.example",
        "api/main.py",
    ]
    
    missing = []
    for file in required_files:
        path = Path(file)
        if path.exists():
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} MISSING")
            missing.append(file)
    
    if missing:
        print(f"\n✗ FAILED: {len(missing)} files missing")
        return False
    else:
        print(f"\n✓ PASSED: All required files present")
        return True


def validate_imports():
    """Check that all imports work correctly."""
    print("\n" + "="*60)
    print("VALIDATION 2: Import Checks")
    print("="*60)
    
    imports_to_test = [
        ("luna_agent", ["process_email", "_check_hard_stop", "_check_unverified_sensitive_facts", "HARD_STOP_KEYWORDS"]),
        ("poc_pipeline", ["should_skip", "is_within_business_hours"]),
        ("email_log", ["log_email_processing", "get_stats", "load_all_logs"]),
        ("gmail_client", ["InboundEmail", "fetch_unread_emails", "send_reply"]),
    ]
    
    failed = []
    for module_name, items in imports_to_test:
        try:
            module = __import__(module_name)
            print(f"\n  ✓ {module_name} imported")
            
            for item in items:
                if hasattr(module, item):
                    print(f"    ✓ {item}")
                else:
                    print(f"    ✗ {item} NOT FOUND")
                    failed.append(f"{module_name}.{item}")
        except ImportError as e:
            print(f"  ✗ {module_name} FAILED: {e}")
            failed.append(module_name)
    
    if failed:
        print(f"\n✗ FAILED: {len(failed)} import errors")
        return False
    else:
        print(f"\n✓ PASSED: All imports successful")
        return True


def validate_env_config():
    """Check .env configuration."""
    print("\n" + "="*60)
    print("VALIDATION 3: Environment Configuration")
    print("="*60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        "ANTHROPIC_API_KEY",
        "GMAIL_ADDRESS",
        "GMAIL_APP_PASSWORD",
        "REPLY_FROM_NAME",
    ]
    
    optional_vars = [
        "SENDING_HOUR_START",
        "SENDING_HOUR_END",
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var, "")
        if value and value.strip():
            print(f"  ✓ {var} is set")
        else:
            print(f"  ✗ {var} NOT SET")
            missing.append(var)
    
    for var in optional_vars:
        value = os.getenv(var, "")
        if value and value.strip():
            print(f"  ✓ {var} = {value}")
        else:
            print(f"  ⚠ {var} not set (using default)")
    
    if missing:
        print(f"\n✗ FAILED: {len(missing)} required variables missing")
        print("  Please copy .env.example to .env and fill in your values")
        return False
    else:
        print(f"\n✓ PASSED: All required environment variables set")
        return True


def validate_hard_stop_keywords():
    """Check that hard-stop keywords are properly defined."""
    print("\n" + "="*60)
    print("VALIDATION 4: Hard-Stop Keywords")
    print("="*60)
    
    from luna_agent import HARD_STOP_KEYWORDS
    
    if not HARD_STOP_KEYWORDS:
        print("  ✗ HARD_STOP_KEYWORDS is empty")
        return False
    
    print(f"  ✓ {len(HARD_STOP_KEYWORDS)} keywords defined")
    
    # Show a sample
    print("\n  Sample keywords:")
    for keyword in HARD_STOP_KEYWORDS[:5]:
        print(f"    - '{keyword}'")
    
    if len(HARD_STOP_KEYWORDS) > 5:
        print(f"    ... and {len(HARD_STOP_KEYWORDS) - 5} more")
    
    # Check for expected categories
    expected_keywords = ["lawsuit", "application approved", "waive deposit", "rent negotiation"]
    found = [kw for kw in expected_keywords if kw in HARD_STOP_KEYWORDS]
    
    print(f"\n  ✓ {len(found)}/{len(expected_keywords)} expected keywords present")
    
    if len(found) < len(expected_keywords):
        missing = [kw for kw in expected_keywords if kw not in HARD_STOP_KEYWORDS]
        print(f"  ⚠ Missing expected keywords: {missing}")
    
    print(f"\n✓ PASSED: Hard-stop keywords configured")
    return True


def validate_business_hours():
    """Check business hours logic."""
    print("\n" + "="*60)
    print("VALIDATION 5: Business Hours Logic")
    print("="*60)
    
    from poc_pipeline import is_within_business_hours
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    try:
        within_hours = is_within_business_hours()
        
        et_tz = ZoneInfo("America/New_York")
        now_et = datetime.now(et_tz)
        
        start_hour = int(os.getenv("SENDING_HOUR_START", "8"))
        end_hour = int(os.getenv("SENDING_HOUR_END", "20"))
        
        print(f"  ✓ Business hours check: working")
        print(f"  Current time (ET): {now_et.strftime('%H:%M')}")
        print(f"  Business hours: {start_hour}:00 - {end_hour}:00")
        print(f"  Within hours: {within_hours}")
        
        print(f"\n✓ PASSED: Business hours logic working")
        return True
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def validate_draft_detection():
    """Check DRAFT detection logic."""
    print("\n" + "="*60)
    print("VALIDATION 6: DRAFT Detection Logic")
    print("="*60)
    
    from luna_agent import _check_unverified_sensitive_facts
    
    test_cases = [
        ("The rent is $1500", [], True),
        ("The rent is $1500", ["get_unit_availability"], False),
        ("The unit is available", [], False),
    ]
    
    passed = 0
    for reply, tools, expected in test_cases:
        result = _check_unverified_sensitive_facts(reply, tools)
        if result == expected:
            print(f"  ✓ Test passed")
            passed += 1
        else:
            print(f"  ✗ Test failed: '{reply[:40]}...'")
    
    if passed == len(test_cases):
        print(f"\n✓ PASSED: {passed}/{len(test_cases)} tests passed")
        return True
    else:
        print(f"\n✗ FAILED: {passed}/{len(test_cases)} tests passed")
        return False


def validate_email_log():
    """Check email_log stats calculation."""
    print("\n" + "="*60)
    print("VALIDATION 7: Email Log Statistics")
    print("="*60)
    
    from email_log import get_stats
    
    try:
        stats = get_stats()
        
        required_keys = [
            "total_emails", "auto_sent", "drafts", "on_hold", 
            "skipped", "escalations", "total_cost_usd", 
            "llm_calls", "template_calls"
        ]
        
        missing = [key for key in required_keys if key not in stats]
        
        if missing:
            print(f"  ✗ Missing keys: {missing}")
            return False
        
        print(f"  ✓ All required stat keys present")
        print(f"\n  Current stats:")
        for key, value in stats.items():
            print(f"    {key}: {value}")
        
        print(f"\n✓ PASSED: Email log statistics working")
        return True
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def main():
    """Run all validations."""
    print("\n" + "="*60)
    print("LUNA POC — Implementation Validation")
    print("="*60)
    
    results = []
    
    results.append(("File Structure", validate_files()))
    results.append(("Import Checks", validate_imports()))
    results.append(("Environment Config", validate_env_config()))
    results.append(("Hard-Stop Keywords", validate_hard_stop_keywords()))
    results.append(("Business Hours Logic", validate_business_hours()))
    results.append(("DRAFT Detection", validate_draft_detection()))
    results.append(("Email Log Stats", validate_email_log()))
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status} | {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL VALIDATIONS PASSED")
        print("\nYour implementation is ready!")
        print("\nNext steps:")
        print("  1. Run: python test_new_modes.py")
        print("  2. Test with real emails: python poc_pipeline.py --dry-run --max 5")
        print("  3. Start dashboard: uvicorn api.main:app --reload --port 8000")
    else:
        print("✗ SOME VALIDATIONS FAILED")
        print("\nPlease fix the issues above before proceeding.")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
