import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# רשימת ההרשאות המלאה - חובה שתהיה זהה למה שיש בקוד השרת!
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',  # גישה למייל
    'https://www.googleapis.com/auth/calendar'       # גישה ליומן
]

def main():
    print("🌍 Opening browser for authentication...")
    
    # וידוא הריגה לקובץ הישן
    if os.path.exists('token.json'):
        os.remove('token.json')
        
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    
    # פורט 0 נותן למערכת למצוא פורט פנוי אוטומטית
    creds = flow.run_local_server(port=0)
    
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    print("✅ SUCCESS! New token created with Calendar & Gmail access.")

if __name__ == '__main__':
    main()