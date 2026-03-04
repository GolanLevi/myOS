
from agents.secretariat_agent import SecretariatAgent

def test_templates():
    agent = SecretariatAgent()
    
    print("🧪 --- TEST START: Notification Templates ---\n")

    # 1. Meeting
    msg1 = agent._construct_message({
        "action_type": "schedule_event",
        "payload": {
            "summary": "פגישה עם גולן",
            "sender_name": "Golan Levi",
            "email": "golan@example.com",
            "start_time": "2026-02-05T10:00:00",
            "link": "http://meet.google.com/abc",
            "link_explanation": "קישור לשיחת וידאו",
            "conflict_note": "יש התנגשות חלקית עם ארוחת צהריים",
            "draft": "Hi Golan, 10am works for me."
        }
    })
    print(f"--- [Meeting] Output: ---\n{msg1}\n")

    # 2. Action Required
    msg2 = agent._construct_message({
        "action_type": "action_required",
        "payload": {
            "summary": "חתימה על מסמך סודיות",
            "sender_name": "Legal Dept",
            "email": "legal@corp.com",
            "deadline": "יום חמישי 17:00",
            "message": "נדרשת חתימתך על טופס NDA לקראת הפרויקט החדש.",
            "draft": "Confirmed. Signed copy attached."
        }
    })
    print(f"--- [Action] Output: ---\n{msg2}\n")

    # 3. Critical Info
    msg3 = agent._construct_message({
        "action_type": "critical_info",
        "payload": {
            "summary": "שינוי שער המניה",
            "sender_name": "Finance Alert",
            "email": "alert@bank.com",
            "message": "המניה ירדה ב-5% בעקבות החדשות.",
            "link": "http://finance.yahoo.com",
            "suggested_action": "לבדוק תיק השקעות"
        }
    })
    print(f"--- [Critical] Output: ---\n{msg3}\n")

    # 4. Spam
    msg4 = agent._construct_message({
        "action_type": "trash",
        "payload": {
            "summary": "מבצעי סוף עונה",
            "sender_name": "ShopIL",
            "email": "deals@shop.co.il",
            "unsubscribe_offered": True
        }
    })
    print(f"--- [Spam] Output: ---\n{msg4}\n")

if __name__ == "__main__":
    test_templates()
