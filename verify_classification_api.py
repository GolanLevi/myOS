
import requests
import json

URL = "http://localhost:8080/analyze_email"

test_cases = [
    {
        "name": "Meeting Request",
        "text": "Hi, let's meet tomorrow at 10:00 AM for a sync.",
        "expected_action": ["schedule_event", "update_event"]
    },
    {
        "name": "Action Required",
        "text": "Please sign the attached contract and send it back by EOD.",
        "expected_action": ["action_required"]
    },
    {
        "name": "Critical Update",
        "text": "URGENT: Your flight has been cancelled.",
        "expected_action": ["critical_info"]
    },
    {
        "name": "Low Priority Info",
        "text": "Here is the weekly newsletter.",
        "expected_action": ["log_info", "update", "info_update"]
    },
    {
        "name": "Spam",
        "text": "CONGRATULATIONS! You won a lottery. Click here to claim.",
        "expected_action": ["trash", "mark_as_spam"]
    }
]

print("🧪 Running Classification Tests...\n")

for test in test_cases:
    payload = {
        "text": test["text"],
        "source": "verification_script",
        "user_id": "verifier"
    }
    
    try:
        response = requests.post(URL, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # We don't see the internal action_type in the final response easily unless we debug logging
        # But we can check "action_needed"
        
        print(f"--- Test: {test['name']} ---")
        print(f"Input: {test['text']}")
        print(f"Response: {data}")
        
        if test["name"] == "Spam":
            if data.get("action_needed") is False:
                print("✅ Spam correctly silenced.")
            else:
                print("❌ Spam NOT silenced.")
        else:
             if data.get("action_needed") is True:
                print("✅ Action Needed: True")
             else:
                print("❌ Unexpected: Action Needed is False")
        
        print("-" * 30)

    except Exception as e:
        print(f"❌ Error testing {test['name']}: {e}")
