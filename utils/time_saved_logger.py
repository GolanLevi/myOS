import os
import time
from typing import Any

from pymongo import MongoClient

from utils.logger import server_logger

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")

TIME_SAVED_ESTIMATES: dict[str, int] = {
    "send_email": 5,
    "create_event": 3,
    "email_triage_ignore": 1,
    "email_triage_summary": 2,
    "draft_created": 8,
    "finance_parsed": 4,
    "daily_briefing": 10,
}

_client: MongoClient | None = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        _client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        _collection = _client["myos"]["time_saved_log"]
        _collection.create_index([("userId", 1), ("timestamp", -1)])
        _collection.create_index([("agent_name", 1), ("timestamp", -1)])
        _collection.create_index([("thread_id", 1), ("timestamp", -1)])
        _collection.create_index(
            [("dedupe_key", 1)],
            unique=True,
            partialFilterExpression={"dedupe_key": {"$type": "string"}},
        )
        return _collection
    except Exception as exc:
        server_logger.warning(f"Time saved logger unavailable: {exc}")
        _collection = None
        return None


def get_time_saved_estimate(action_type: str) -> int:
    return int(TIME_SAVED_ESTIMATES.get(action_type, 0))


def log_time_saved(
    *,
    user_id: str,
    agent_name: str,
    action_type: str,
    minutes_saved: int | None = None,
    thread_id: str | None = None,
    dedupe_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    collection = _get_collection()
    if collection is None:
        return

    resolved_minutes = int(minutes_saved if minutes_saved is not None else get_time_saved_estimate(action_type))
    if resolved_minutes <= 0:
        return

    doc = {
        "userId": user_id,
        "user_id": user_id,
        "agent_name": agent_name,
        "action_type": action_type,
        "minutes_saved": resolved_minutes,
        "metadata": metadata or {},
        "timestamp": time.time(),
    }
    if thread_id:
        doc["thread_id"] = thread_id
    if dedupe_key:
        doc["dedupe_key"] = dedupe_key

    try:
        if dedupe_key:
            collection.update_one(
                {"dedupe_key": dedupe_key},
                {"$setOnInsert": doc},
                upsert=True,
            )
        else:
            collection.insert_one(doc)
    except Exception as exc:
        server_logger.warning(f"Failed to write time saved log: {exc}")
