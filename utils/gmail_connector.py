import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- הרשאות: מייל (קריאה/כתיבה/שליחה) + יומן ---
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar"
]

def _get_credentials():
    creds = None
    
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🚀 Starting new login flow...")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            
            creds = flow.run_local_server(port=8080, open_browser=True)
        
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            print("✅ Token saved for future use.")
            
    return creds

def get_gmail_service():
    return build("gmail", "v1", credentials=_get_credentials())

def get_calendar_service():
    return build("calendar", "v3", credentials=_get_credentials())

if __name__ == "__main__":
    print("🧪 Testing Connections...")
    try:
        gmail_service = get_gmail_service()
        profile = gmail_service.users().getProfile(userId='me').execute()
        print(f"📧 Gmail Connected: {profile['emailAddress']}")

        calendar_service = get_calendar_service()
        calendars = calendar_service.calendarList().list().execute()
        print(f"📅 Calendar Connected! Found {len(calendars['items'])} calendars.")
        
        print("🎉 SUCCESS! Both services are active.")
    except Exception as e:
        print(f"❌ Error: {e}")