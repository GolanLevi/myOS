import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from utils.logger import tool_logger

# --- Permissions: Gmail (read/write/send) + Calendar ---
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]


def _get_credentials():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            tool_logger.info("Refreshing expired Google token.")
            creds.refresh(Request())
        else:
            tool_logger.info("Starting a new Google login flow.")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)

        with open("token.json", "w") as token:
            token.write(creds.to_json())
        tool_logger.info("Saved Google token for future use.")

    return creds


def get_gmail_service():
    return build("gmail", "v1", credentials=_get_credentials())


def get_calendar_service():
    return build("calendar", "v3", credentials=_get_credentials())


if __name__ == "__main__":
    tool_logger.info("Testing Google connections.")
    try:
        gmail_service = get_gmail_service()
        profile = gmail_service.users().getProfile(userId="me").execute()
        tool_logger.info(f"Gmail connected: {profile['emailAddress']}")

        calendar_service = get_calendar_service()
        calendars = calendar_service.calendarList().list().execute()
        tool_logger.info(f"Calendar connected. Found {len(calendars['items'])} calendars.")

        tool_logger.info("Google services are active.")
    except Exception as exc:
        tool_logger.error(f"Google connection test failed: {exc}")
