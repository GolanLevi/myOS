
from agents.secretariat_agent import SecretariatAgent

def test_formatting():
    agent = SecretariatAgent()
    
    # TC 1: Dangerous Characters
    print("🧪 Testing Dangerous Characters...")
    bad_input = {
        "action_type": "log_info",
        "payload": {
            "summary": "Title with <HTML> tags & ampersand",
            "message": "Content with <b>bold</b> and *markdown*",
            "email": "hacker <script>@alert.com"
        }
    }
    msg = agent._construct_message(bad_input)
    print(f"Output:\n{msg}\n")
    
    if "&lt;HTML&gt;" in msg and "&amp;" in msg:
        print("✅ Escaping worked!")
    else:
        print("❌ Escaping failed!")

    # TC 2: Event Logic
    print("\n🧪 Testing Schedule Event...")
    event_input = {
        "action_type": "schedule_event",
        "payload": {
            "summary": "Meeting with <VIP>",
            "start_time": "2024-01-30T10:00:00",
            "email": "vip@company.com"
        }
    }
    msg = agent._construct_message(event_input)
    print(f"Output:\n{msg}\n")
    
    if "<b>זמן:</b>" in msg:
        print("✅ HTML Tags present!")
    else:
        print("❌ HTML Tags missing!")

if __name__ == "__main__":
    test_formatting()
