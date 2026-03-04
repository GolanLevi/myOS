import os
import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Define the scopes we need
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar"
]

def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    # Fix: Docker sometimes creates a directory named 'token.json' if mounted incorrectly.
    if os.path.exists("token.json"):
        if os.path.isdir("token.json"):
            import shutil
            shutil.rmtree("token.json")
            print("🗑️ Removed directory 'token.json' (Docker artifact).")
        else:
            os.remove("token.json") 
            print("🗑️ Old token.json deleted to force refresh.")

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                print("❌ Error: credentials.json not found! Please make sure you have it in this folder.")
                return
                
            print("🚀 Starting Login Flow (Local Server Mode)...")
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            # שימוש בשרת מקומי לאימות (פותח דפדפן אוטומטית)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            print("✅ Success! New 'token.json' created with correct scopes.")

if __name__ == "__main__":
    main()
