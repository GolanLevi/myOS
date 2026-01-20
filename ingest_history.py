import os.path
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from agents.information_agent import InformationAgent

# --- הגדרות ---
NUM_EMAILS = 100  # הגדלנו ל-100 מיילים אחרונים
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """Authentication and Gmail Service creation"""
    creds = None
    # בדיקה האם קיים טוקן
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception as e:
            print(f"⚠️ Warning: Failed to load token.json: {e}")
            creds = None
    
    # אם הטוקן לא תקין או לא קיים
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                print("❌ Token expired and cannot be refreshed. Please delete token.json and run again locally.")
                sys.exit(1)
        else:
            # בדוקר זה בעייתי לפתוח דפדפן, לכן אם אין טוקן - נעצור
            print("❌ No token.json found! Please run the auth script locally first to generate it.")
            sys.exit(1)

    return build('gmail', 'v1', credentials=creds)

def main():
    print(f"🚀 Starting Memory Backfill (Last {NUM_EMAILS} emails)...")
    
    try:
        service = get_gmail_service()
        agent = InformationAgent()
        
        print("📥 Connecting to Gmail...")
        results = service.users().messages().list(userId='me', maxResults=NUM_EMAILS, labelIds=['INBOX']).execute()
        messages = results.get('messages', [])

        if not messages:
            print("📭 No emails found.")
            return

        print(f"🧠 Processing {len(messages)} emails into Vector DB...")
        
        count = 0
        for i, msg in enumerate(messages):
            # מציג התקדמות כל 10 מיילים
            if i % 10 == 0:
                print(f"   Processing {i}/{len(messages)}...")

            try:
                msg_detail = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                payload = msg_detail.get('payload', {})
                headers = payload.get('headers', [])
                
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "(No Subject)")
                sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
                snippet = msg_detail.get('snippet', '')
                
                # יצירת הזיכרון
                memory_text = f"Email from {sender} | Subject: {subject} | Content: {snippet}"
                
                # שמירה
                agent.memorize(memory_text, source="gmail_history")
                count += 1
                
            except Exception as e:
                print(f"   ⚠️ Skipped email {i}: {e}")

        print(f"\n✅ SUCCESS: Successfully memorized {count} items into the Brain!")
        print("---------------------------------------------------------------")
        print("💡 You can now ask the agent questions about your recent history.")

    except Exception as e:
        print(f"\n❌ Critical Error: {e}")

if __name__ == '__main__':
    main()
