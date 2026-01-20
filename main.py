from core.manager import AgentManager
from agents.secretariat_agent import SecretariatAgent
from agents.finance_agent import FinanceAgent
from agents.info_agent import InformationAgent
from utils.gmail_tools import fetch_recent_emails
# הייבוא החדש ליומן
from utils.calendar_tools import get_upcoming_events

def main():
    print("🚀 myOS: Inbox Triage Started...")
    
    # 1. אתחול
    manager = AgentManager()
    
    # רישום הסוכנים החדשים
    manager.register_agent(SecretariatAgent())
    manager.register_agent(FinanceAgent())
    manager.register_agent(InformationAgent())

    # 2. הבאת תמונת מצב מהיומן (7 ימים קדימה)
    # זה נותן ל-AI "עיניים" לראות אם אתה פנוי לפני שהוא קורא את המיילים
    try:
        calendar_context = get_upcoming_events(days=7)
    except Exception as e:
        print(f"⚠️ Calendar Error: {e}")
        calendar_context = "Calendar unavailable."

    # 3. הבאת המיילים האמיתיים
    emails = fetch_recent_emails(limit=3)
    
    # 4. המעבר על המיילים (The Loop)
    for email in emails:
        print(f"\n📧 Processing email from: {email['sender']}")
        
        # אנחנו בונים הקשר עשיר יותר: גם המייל וגם הלו"ז
        user_context = f"""
        --- INCOMING EMAIL ---
        Sender: {email['sender']}
        Subject: {email['subject']}
        Content: {email['snippet']}
        
        --- MY CALENDAR AVAILABILITY (Next 7 Days) ---
        {calendar_context}
        """
        
        # שליחה למנהל (הוא כבר יחליט למי להעביר)
        manager.process_incoming_request(
            user_input=user_context, 
            metadata={"email_id": email['id']}
        )

if __name__ == "__main__":
    main()