"""
test_decision_status_consistency.py — Test decision/status field consistency.

This script validates that all modes have consistent decision/status field mappings.
"""

import json
from pathlib import Path

# Expected mappings
EXPECTED_MAPPINGS = {
    "SKIP": {"status": "skipped", "decision": "SKIP"},
    "DRAFT": {"status": "draft", "decision": "DRAFT"},
    "ESCALATE": {"status": "escalated", "decision": "ESCALATE"},
    "HOLD": {"status": "hold", "decision": "HOLD"},
    "SEND": {"status": "sent", "decision": "SEND"},
}

def test_log_consistency():
    """Check email_log.json for decision/status consistency."""
    print("\n" + "="*60)
    print("DECISION/STATUS CONSISTENCY TEST")
    print("="*60)
    
    log_file = Path("data/email_log.json")
    
    if not log_file.exists():
        print("\n⚠️  No email_log.json found. Run the pipeline first.")
        return True
    
    records = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    if not records:
        print("\n⚠️  No records in email_log.json")
        return True
    
    print(f"\n✓ Found {len(records)} records in email_log.json")
    
    # Check each record
    inconsistencies = []
    mode_counts = {}
    
    for i, record in enumerate(records):
        status = record.get("status", "")
        decision = record.get("decision", "")
        
        # Count modes
        mode_key = f"{decision}/{status}"
        mode_counts[mode_key] = mode_counts.get(mode_key, 0) + 1
        
        # Check consistency
        is_consistent = False
        
        # SKIP mode
        if decision == "SKIP" and status == "skipped":
            is_consistent = True
        # DRAFT mode
        elif decision == "DRAFT" and status == "draft":
            is_consistent = True
        # ESCALATE mode
        elif decision == "ESCALATE" and status == "escalated":
            is_consistent = True
        # HOLD mode
        elif decision == "HOLD" and status == "hold":
            is_consistent = True
        # SEND mode
        elif decision == "SEND" and status == "sent":
            is_consistent = True
        # ERROR mode (allowed inconsistency)
        elif status == "error":
            is_consistent = True
        
        if not is_consistent:
            inconsistencies.append({
                "index": i,
                "id": record.get("id", "unknown"),
                "from": record.get("from_addr", "unknown"),
                "subject": record.get("subject", "")[:50],
                "decision": decision,
                "status": status,
            })
    
    # Print mode distribution
    print("\n" + "-"*60)
    print("MODE DISTRIBUTION")
    print("-"*60)
    for mode, count in sorted(mode_counts.items()):
        print(f"  {mode:20} : {count}")
    
    # Print inconsistencies
    if inconsistencies:
        print("\n" + "-"*60)
        print(f"❌ INCONSISTENCIES FOUND: {len(inconsistencies)}")
        print("-"*60)
        for inc in inconsistencies[:5]:  # Show first 5
            print(f"\n  Record #{inc['index']}:")
            print(f"    From    : {inc['from']}")
            print(f"    Subject : {inc['subject']}")
            print(f"    Decision: {inc['decision']}")
            print(f"    Status  : {inc['status']}")
            print(f"    ❌ MISMATCH")
        
        if len(inconsistencies) > 5:
            print(f"\n  ... and {len(inconsistencies) - 5} more")
        
        print("\n" + "="*60)
        print("❌ TEST FAILED - Inconsistencies detected")
        print("="*60)
        return False
    else:
        print("\n" + "="*60)
        print("✅ ALL RECORDS CONSISTENT")
        print("="*60)
        return True


def test_expected_mappings():
    """Display expected decision/status mappings."""
    print("\n" + "="*60)
    print("EXPECTED DECISION/STATUS MAPPINGS")
    print("="*60)
    
    print("\n{:<15} {:<15} {:<15}".format("MODE", "DECISION", "STATUS"))
    print("-"*60)
    
    for mode, mapping in EXPECTED_MAPPINGS.items():
        print("{:<15} {:<15} {:<15}".format(
            mode,
            f'"{mapping["decision"]}"',
            f'"{mapping["status"]}"'
        ))
    
    print("\n" + "="*60)
    return True


def main():
    """Run all consistency tests."""
    print("\n" + "="*60)
    print("LUNA POC — Decision/Status Consistency Tests")
    print("="*60)
    
    results = []
    
    # Test 1: Expected mappings
    results.append(("Expected Mappings", test_expected_mappings()))
    
    # Test 2: Log consistency
    results.append(("Log Consistency", test_log_consistency()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} | {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("\nYour decision/status fields are consistent!")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nPlease fix the inconsistencies above.")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
