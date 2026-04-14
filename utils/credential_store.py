from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
from typing import Any, Optional

from google.oauth2.credentials import Credentials
from pymongo import MongoClient

from utils.logger import tool_logger


MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
GOOGLE_CREDENTIALS_KEY = os.getenv("MYOS_CREDENTIALS_KEY", "").strip()

_mongo_client: Optional[MongoClient] = None


def _get_client() -> MongoClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGODB_URL)
    return _mongo_client


def _get_collection():
    db = _get_client()["myos"]
    collection = db["connector_credentials"]
    collection.create_index([("user_id", 1), ("provider", 1)], unique=True)
    return collection


def _get_fernet():
    if not GOOGLE_CREDENTIALS_KEY:
        return None

    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError(
            "Encrypted credential storage requires the 'cryptography' package."
        ) from exc

    try:
        return Fernet(GOOGLE_CREDENTIALS_KEY.encode("utf-8"))
    except Exception:
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(GOOGLE_CREDENTIALS_KEY.encode("utf-8")).digest()
        )
        return Fernet(derived)


def encrypted_store_enabled() -> bool:
    return bool(GOOGLE_CREDENTIALS_KEY)


def load_google_credentials(user_id: str) -> Credentials | None:
    collection = _get_collection()
    doc = collection.find_one({"user_id": user_id, "provider": "google"})
    if not doc:
        return None

    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("MYOS_CREDENTIALS_KEY is required to load stored Google credentials.")

    payload = doc.get("payload")
    if not payload:
        return None

    decrypted = fernet.decrypt(payload.encode("utf-8")).decode("utf-8")
    data = json.loads(decrypted)
    return Credentials.from_authorized_user_info(data)


def save_google_credentials(
    user_id: str,
    creds: Credentials,
    *,
    account_email: Optional[str] = None,
    source: str = "runtime",
) -> None:
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("MYOS_CREDENTIALS_KEY is required to save Google credentials.")

    now = dt.datetime.utcnow()
    serialized = creds.to_json()
    encrypted = fernet.encrypt(serialized.encode("utf-8")).decode("utf-8")
    scopes = list(creds.scopes or [])

    expires_at = None
    if getattr(creds, "expiry", None) is not None:
        expires_at = creds.expiry

    _get_collection().update_one(
        {"user_id": user_id, "provider": "google"},
        {
            "$set": {
                "provider": "google",
                "user_id": user_id,
                "payload": encrypted,
                "account_email": account_email or "",
                "scopes": scopes,
                "updated_at": now,
                "expires_at": expires_at,
                "source": source,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )
    tool_logger.info(f"Saved encrypted Google credentials for user '{user_id}'.")


def delete_google_credentials(user_id: str) -> None:
    _get_collection().delete_one({"user_id": user_id, "provider": "google"})
    tool_logger.info(f"Deleted encrypted Google credentials for user '{user_id}'.")


def get_google_credential_metadata(user_id: str) -> dict[str, Any] | None:
    doc = _get_collection().find_one(
        {"user_id": user_id, "provider": "google"},
        {
            "_id": 0,
            "user_id": 1,
            "provider": 1,
            "account_email": 1,
            "scopes": 1,
            "updated_at": 1,
            "created_at": 1,
            "expires_at": 1,
            "source": 1,
        },
    )
    return doc
