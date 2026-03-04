"""
בדיקת פונקציית classify_user_response
מריצים ישירות את הפונקציה החדשה ובודקים שהסיווג נכון
"""
import sys
import os
# Fix encoding for Windows Hebrew terminals
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from agents.secretariat_agent import SecretariatAgent

def test_classification():
    agent = SecretariatAgent()
    
    # פעולה ממתינה לדוגמה (pending state)
    mock_pending = {
        "action": "schedule_event",
        "params": {
            "summary": "פגישה עם דנה קפלן",
            "start_time": "2026-02-27T20:00:00",
            "email": "dana@example.com"
        }
    }

    # רשימת תרחישים
    test_cases = [
        # --- אישורים (צפוי: approve) ---
        ("אשר", "approve"),
        ("כן", "approve"),
        ("תאשר את הפגישה", "approve"),
        ("לך על זה", "approve"),
        ("יאללה תבצע", "approve"),
        ("אשר את הפגישה עם דנה", "approve"),
        ("מאשר", "approve"),
        ("yes", "approve"),
        ("ok", "approve"),
        
        # --- דחיות (צפוי: reject) ---
        ("בטל", "reject"),
        ("לא", "reject"),
        ("לא רוצה", "reject"),
        ("cancel", "reject"),
        ("תבטל את זה", "reject"),
        
        # --- אחר (צפוי: other) ---
        ("מה יש לי מחר?", "other"),
        ("תקבע לי פגישה עם יוסי", "other"),
        ("שנה את השעה ל-15:00", "other"),
        ("תשלח מייל לגולן", "other"),
    ]

    print("TEST: classify_user_response\n")
    
    passed = 0
    failed = 0
    
    for user_text, expected in test_cases:
        result = agent.classify_user_response(user_text, mock_pending)
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] '{user_text}' -> {result} (expected: {expected})")
    
    print(f"\nResults: {passed}/{passed+failed} passed")
    if failed == 0:
        print("All tests passed!")
    else:
        print(f"{failed} tests failed")

if __name__ == "__main__":
    test_classification()
