"""
Test that templates are called efficiently without unnecessary tool calls
"""

from luna_agent import draft_reply_with_claude

def test_template_efficiency():
    """Test that policy templates only call get_property_link, not other tools"""
    
    print("=" * 80)
    print("TEMPLATE EFFICIENCY TEST")
    print("Testing that policy templates minimize tool calls")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "6-month lease request",
            "subject": "Short term lease options?",
            "body": "Hello, Do you offer 6 month leases at Mountain View Apartments? I'm only looking for something temporary. Best, Michael Chen",
            "from_name": "Michael Chen",
            "from_email": "michael@example.com",
            "expected_template": "six_month_lease",
            "expected_tools": ["get_property_link", "use_template"],  # Should ONLY call these
        },
        {
            "name": "Application request",
            "subject": "Application for 508 W Brighton",
            "body": "Hi, can you send me an application for 508 W Brighton Ave? Thanks, Jessica",
            "from_name": "Jessica Miller",
            "from_email": "jessica@example.com",
            "expected_template": "apply_now",
            "expected_tools": ["get_property_link", "use_template"],
        },
        {
            "name": "Third-party funding",
            "subject": "Rental assistance question",
            "body": "My agency will be paying my rent. Is this okay at College Park Apartments? Sarah",
            "from_name": "Sarah Johnson",
            "from_email": "sarah@example.com",
            "expected_template": "third_party_funding",
            "expected_tools": ["get_property_link", "use_template"],
        },
        {
            "name": "Credit history (simple template)",
            "subject": "Credit question",
            "body": "I have some credit issues. Can I still apply? Thanks, John",
            "from_name": "John Doe",
            "from_email": "john@example.com",
            "expected_template": "credit",
            "expected_tools": ["use_template"],  # Should ONLY call this, no property tools
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n{'=' * 80}")
        print(f"Test: {test['name']}")
        print(f"{'=' * 80}")
        
        result = draft_reply_with_claude(
            inbound_subject=test["subject"],
            inbound_body=test["body"],
            from_email=test["from_email"],
            from_name=test["from_name"],
        )
        
        # Check template used
        template_used = result.get("template_used")
        tools_called = result.get("tools_called", [])
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        
        print(f"Template Used: {template_used}")
        print(f"Tools Called: {tools_called}")
        print(f"Input Tokens: {input_tokens:,}")
        print(f"Output Tokens: {output_tokens:,}")
        
        # Verify template
        template_match = template_used == test["expected_template"]
        
        # Verify tools (should only call expected tools, no extras)
        tools_match = set(tools_called) == set(test["expected_tools"])
        
        # Check for unnecessary tools
        unnecessary_tools = []
        if "fetch_property_data" in tools_called and "fetch_property_data" not in test["expected_tools"]:
            unnecessary_tools.append("fetch_property_data")
        if "get_unit_availability" in tools_called and "get_unit_availability" not in test["expected_tools"]:
            unnecessary_tools.append("get_unit_availability")
        if "check_property_status" in tools_called and "check_property_status" not in test["expected_tools"]:
            unnecessary_tools.append("check_property_status")
        
        # Results
        if template_match and tools_match and not unnecessary_tools:
            print(f"✓ PASS - Efficient template usage")
            passed += 1
        else:
            print(f"✗ FAIL")
            if not template_match:
                print(f"  - Expected template: {test['expected_template']}, got: {template_used}")
            if not tools_match:
                print(f"  - Expected tools: {test['expected_tools']}")
                print(f"  - Got tools: {tools_called}")
            if unnecessary_tools:
                print(f"  - Unnecessary tool calls: {unnecessary_tools}")
            failed += 1
        
        # Show reply preview
        reply_body = result.get("reply_body", "")
        if reply_body and len(reply_body) > 0:
            preview = reply_body[:150] + "..." if len(reply_body) > 150 else reply_body
            print(f"\nReply Preview:\n{preview}")
    
    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Passed: {passed}/{len(test_cases)}")
    print(f"Failed: {failed}/{len(test_cases)}")
    
    if failed == 0:
        print("\n✓ All templates are being called efficiently!")
    else:
        print(f"\n⚠ {failed} test(s) had inefficient tool usage")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    test_template_efficiency()
