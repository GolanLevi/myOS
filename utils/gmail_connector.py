from __future__ import annotations

import os
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from utils.credential_store import (
    get_google_credential_metadata,
    encrypted_store_enabled,
    load_google_credentials,
    save_google_credentials,
)
from utils.logger import tool_logger
from utils.request_context import get_current_user_id

# --- Permissions: Gmail (read/write/send) + Calendar ---
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]


def _resolve_user_id(user_id: Optional[str] = None) -> str:
    normalized = str(user_id or "").strip()
    if normalized:
        return normalized
    contextual = str(get_current_user_id("") or "").strip()
    return contextual or "admin"


def _load_legacy_credentials() -> Credentials | None:
    if os.path.exists("token.json"):
        return Credentials.from_authorized_user_file("token.json", SCOPES)
    return None


def _save_legacy_credentials(creds: Credentials) -> None:
    with open("token.json", "w", encoding="utf-8") as token:
        token.write(creds.to_json())


def _refresh_credentials(creds: Credentials) -> Credentials:
    if creds.expired and creds.refresh_token:
        tool_logger.info("Refreshing expired Google token.")
        creds.refresh(Request())
    return creds


def _start_local_google_flow() -> Credentials:
    tool_logger.info("Starting a new Google login flow.")
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    return flow.run_local_server(port=8080, open_browser=True)


def connect_google_account(user_id: str) -> dict[str, str]:
    resolved_user_id = _resolve_user_id(user_id)
    creds = _start_local_google_flow()

    profile_email = ""
    try:
        gmail_service = build("gmail", "v1", credentials=creds)
        profile = gmail_service.users().getProfile(userId="me").execute()
        profile_email = str(profile.get("emailAddress") or "")
    except Exception as exc:
        tool_logger.warning(f"Connected Google account but could not read Gmail profile: {exc}")

    if encrypted_store_enabled():
        save_google_credentials(
            resolved_user_id,
            creds,
            account_email=profile_email,
            source="interactive-connect",
        )

    if resolved_user_id == "admin":
        _save_legacy_credentials(creds)

    return {
        "user_id": resolved_user_id,
        "account_email": profile_email,
        "storage": "encrypted-store" if encrypted_store_enabled() else "legacy-token-file",
    }


def get_google_connection_status(user_id: str) -> dict[str, object]:
    resolved_user_id = _resolve_user_id(user_id)
    metadata = get_google_credential_metadata(resolved_user_id)
    return {
        "user_id": resolved_user_id,
        "encrypted_store_enabled": encrypted_store_enabled(),
        "connected": bool(metadata),
        "metadata": metadata or {},
        "legacy_admin_token_present": resolved_user_id == "admin" and os.path.exists("token.json"),
    }


def _get_credentials(user_id: Optional[str] = None) -> Credentials:
    resolved_user_id = _resolve_user_id(user_id)
    creds: Credentials | None = None

    if encrypted_store_enabled():
        try:
            creds = load_google_credentials(resolved_user_id)
        except Exception as exc:
            tool_logger.warning(
                f"Encrypted Google credential lookup failed for user '{resolved_user_id}': {exc}"
            )

    if creds is None and resolved_user_id == "admin":
        creds = _load_legacy_credentials()
        if creds and encrypted_store_enabled():
            try:
                save_google_credentials(resolved_user_id, creds, source="legacy-import")
                tool_logger.info("Imported legacy admin Google token into encrypted credential store.")
            except Exception as exc:
                tool_logger.warning(f"Failed to import legacy admin token into encrypted store: {exc}")

    if creds:
        creds = _refresh_credentials(creds)
        if encrypted_store_enabled():
            try:
                save_google_credentials(resolved_user_id, creds, source="refresh")
            except Exception as exc:
                tool_logger.warning(
                    f"Failed to persist refreshed Google credentials for user '{resolved_user_id}': {exc}"
                )
        elif resolved_user_id == "admin":
            _save_legacy_credentials(creds)

        if creds.valid:
            return creds

    if resolved_user_id != "admin":
        raise RuntimeError(
            f"No Google credentials are connected for user '{resolved_user_id}'. "
            "Complete per-user Google connection before using Gmail or Calendar tools."
        )

    creds = _start_local_google_flow()

    if encrypted_store_enabled():
        save_google_credentials(resolved_user_id, creds, source="interactive-login")
    _save_legacy_credentials(creds)
    tool_logger.info("Saved Google token for future use.")
    return creds


def get_gmail_service(user_id: Optional[str] = None):
    return build("gmail", "v1", credentials=_get_credentials(user_id))


def get_calendar_service(user_id: Optional[str] = None):
    return build("calendar", "v3", credentials=_get_credentials(user_id))


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
