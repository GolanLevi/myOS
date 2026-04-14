from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any
import uvicorn
import os
from dotenv import load_dotenv
load_dotenv()
import re
import asyncio
import datetime
from collections import Counter

from pymongo import MongoClient
from bson import ObjectId
from langgraph.checkpoint.mongodb import MongoDBSaver

# ייבוא הסוכנים והכלים
from agents.information_agent import KnowledgeAgent
from core.state_manager import WorkflowStateStore
from utils.calendar_tools import get_upcoming_events, get_events_for_date, normalize_event_summary
from utils.gmail_tools import fetch_email_by_id, send_email as gmail_send_email
from utils.request_context import active_user_context

# ייבוא הגרף החדש
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage, BaseMessage
from agents.secretariat_graph import build_secretariat_graph

from utils.logger import server_logger, memory_logger
from utils.time_saved_logger import log_time_saved
import threading
import time
from bot.message_formatter import (
    MANUAL_OVERRIDE_BASE_TEXT,
    _callback_source_text,
    _decorate_button_text,
    fallback_buttons_for_text,
    parse_button_marker,
)

try:
    from bot.telegram_bot import TelegramNativeBot
except Exception as exc:  # pragma: no cover - only used when bot dependencies are unavailable
    TelegramNativeBot = None  # type: ignore[assignment]
    _telegram_bot_import_error = exc
else:
    _telegram_bot_import_error = None

# app = FastAPI() is defined below

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    server_logger.error(f"❌ Unhandled Exception: {str(exc)}")
    
    # Check for specific AI errors
    err_msg = str(exc).lower()
    friendly_msg = "⚠️ שגיאה פנימית במערכת. אנא נסה שוב מאוחר יותר."
    
    if "resource_exhausted" in err_msg or "429" in err_msg:
        friendly_msg = "⚠️ המכסה החינמית של ה-AI הסתיימה זמנית (Rate Limit). אנא המתן דקה ונסה שוב."
    elif "contents are required" in err_msg:
        friendly_msg = "⚠️ שגיאת תוכן ב-AI (ייתכן שהבקשה ארוכה מדי או חסרה מזהה). המערכת מתאוששת..."
    
    return JSONResponse(
        status_code=200,
        content=_build_response(
            answer=friendly_msg,
            internal_id="",
            is_paused=False,
            status="error",
        )
    )

# Global lock for processing emails sequentially to avoid Gemini 429 errors
email_processing_lock = threading.Lock()

server_logger.info("👔 Manager: Initializing MyOS Team (LangGraph Edition)...")
knowledge_agent = KnowledgeAgent()
workflow_state_store = WorkflowStateStore() # נשתמש בו רק לטובת עדכון אנשי קשר ומיפוי Telegram IDs

# אתחול חיבור MongoDB לטובת LangGraph
mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
try:
    mongo_client = MongoClient(mongo_url)
    checkpoint_collection = mongo_client["myos_langgraph"]["checkpoints"]
    checkpointer = MongoDBSaver(checkpoint_collection)
    graph = build_secretariat_graph(checkpointer)
    server_logger.info("✅ Manager: LangGraph and Memory initialized!")
except Exception as e:
    server_logger.error(f"❌ LangGraph setup Error: {e}")
    graph = None

telegram_bot_instance: "TelegramNativeBot | None" = None
telegram_bot_init_failed = False


def set_telegram_bot(bot: "TelegramNativeBot | None") -> None:
    global telegram_bot_instance
    telegram_bot_instance = bot


def get_telegram_bot() -> "TelegramNativeBot | None":
    global telegram_bot_instance, telegram_bot_init_failed
    if telegram_bot_instance is not None:
        return telegram_bot_instance
    if telegram_bot_init_failed:
        return None
    if TelegramNativeBot is None:
        telegram_bot_init_failed = True
        if _telegram_bot_import_error is not None:
            server_logger.warning(f"⚠️ Telegram bot import failed: {_telegram_bot_import_error}")
        return None
    try:
        telegram_bot_instance = TelegramNativeBot()
        return telegram_bot_instance
    except Exception as exc:
        telegram_bot_init_failed = True
        server_logger.warning(f"⚠️ Telegram bot init failed: {exc}")
        return None


def send_via_bot(response: dict, chat_id: Optional[int] = None) -> bool:
    bot = get_telegram_bot()
    if bot is None:
        return False

    target_chat_id = chat_id if chat_id is not None else bot.default_chat_id
    if target_chat_id is None:
        server_logger.warning("⚠️ Telegram bot is configured without TELEGRAM_CHAT_ID. Skipping outbound send.")
        return False

    bot.send_server_response_sync(chat_id=target_chat_id, response=response)
    return True


def _get_dashboard_db():
    return mongo_client["myos"]


def _get_langgraph_db():
    return mongo_client["myos_langgraph"]


def _iso_z(dt: datetime.datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_datetime(value: Any) -> datetime.datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, ObjectId):
        return value.generation_time
    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            return None
    return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime.datetime):
        return _iso_z(value)
    return value


def _to_public_doc(doc: dict[str, Any]) -> dict[str, Any]:
    public = _json_safe(doc)
    if "_id" in public:
        public["_id"] = str(public["_id"])
    return public


def _safe_collection_count(db, name: str) -> int:
    try:
        return int(db[name].count_documents({}))
    except Exception:
        return 0


def _dashboard_user_match(user_id: str) -> dict[str, Any]:
    return {"$or": [{"userId": user_id}, {"user_id": user_id}]}


def _dashboard_since_match(since: datetime.datetime | None) -> dict[str, Any]:
    if since is None:
        return {}
    since_utc = since.astimezone(datetime.timezone.utc) if since.tzinfo else since.replace(tzinfo=datetime.timezone.utc)
    since_ts = since_utc.timestamp()
    return {
        "$or": [
            {"timestamp": {"$gte": since_ts}},
            {"timestamp": {"$gte": since_utc}},
            {"date": {"$gte": since_utc}},
            {"createdAt": {"$gte": since_utc}},
            {"created_at": {"$gte": since_utc}},
        ]
    }


def _dashboard_match(user_id: str, since: datetime.datetime | None = None) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = [_dashboard_user_match(user_id)]
    since_clause = _dashboard_since_match(since)
    if since_clause:
        clauses.append(since_clause)
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _start_of_local_day() -> datetime.datetime:
    now = datetime.datetime.now().astimezone()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_local_week() -> datetime.datetime:
    start_of_day = _start_of_local_day()
    return start_of_day - datetime.timedelta(days=start_of_day.weekday())


def _local_now() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


def _priority_from_bucket(bucket: str) -> str:
    if bucket == "needs_decision_now":
        return "high"
    if bucket == "today":
        return "medium"
    return "low"


def _extract_due_datetime(params: dict[str, Any]) -> datetime.datetime | None:
    for key in (
        "event_start",
        "start_time",
        "new_start_time",
        "due_at",
        "due_date",
        "deadline",
        "scheduled_for",
    ):
        candidate = _coerce_datetime((params or {}).get(key))
        if candidate is not None:
            return candidate
    return None


def _hours_until(value: datetime.datetime | None) -> float | None:
    if value is None:
        return None
    reference = _local_now().astimezone(datetime.timezone.utc)
    target = value.astimezone(datetime.timezone.utc) if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
    return (target - reference).total_seconds() / 3600.0


def _urgency_meta(
    *,
    action: str,
    status: str,
    params: dict[str, Any],
    created_at: datetime.datetime | None,
    severity: str | None = None,
) -> dict[str, Any]:
    normalized_action = str((params or {}).get("approval_type") or action or "").strip() or "action"
    normalized_status = str(status or "pending").strip() or "pending"
    normalized_severity = severity or _status_severity(action, normalized_status)
    confidence = _confidence_for_action(normalized_action, params)
    due_at = _extract_due_datetime(params)
    hours_until_due = _hours_until(due_at)
    age_hours = 0.0
    if created_at is not None:
        created_utc = created_at.astimezone(datetime.timezone.utc) if created_at.tzinfo else created_at.replace(tzinfo=datetime.timezone.utc)
        age_hours = max(0.0, (_local_now().astimezone(datetime.timezone.utc) - created_utc).total_seconds() / 3600.0)

    score = {
        "low": 24,
        "medium": 48,
        "high": 72,
        "critical": 88,
    }.get(normalized_severity, 40)

    if normalized_status == "pending":
        score += 18
    elif normalized_status == "processing":
        score += 10
    elif normalized_status == "error":
        score += 20
    elif normalized_status in {"approved", "rejected", "completed"}:
        score -= 18

    if normalized_action in {"send_email", "create_event", "update_event_time", "multi_step"}:
        score += 12
    elif normalized_action in {"create_draft", "incoming_email"}:
        score += 8
    elif normalized_action in {"trash_email", "delete_event"}:
        score += 10

    if confidence >= 85:
        score += 4
    elif confidence < 60:
        score -= 4

    if age_hours >= 24:
        score += 10
    elif age_hours >= 6:
        score += 5

    if hours_until_due is not None:
        if hours_until_due <= 0:
            score += 24
        elif hours_until_due <= 6:
            score += 20
        elif hours_until_due <= 24:
            score += 12
        elif hours_until_due <= 48:
            score += 6
        else:
            score -= 4

    score = max(0, min(100, int(round(score))))
    is_actionable = normalized_status == "pending"
    freshness_boost = 0
    if normalized_status == "pending":
        if age_hours <= 3:
            freshness_boost = 64
        elif age_hours <= 12:
            freshness_boost = 48
        elif age_hours <= 24:
            freshness_boost = 36
        elif age_hours <= 72:
            freshness_boost = 18
        elif age_hours >= 24 * 14:
            freshness_boost = -16
        elif age_hours >= 24 * 7:
            freshness_boost = -8
    elif normalized_status in {"approved", "rejected", "completed", "ignored", "expired"}:
        if age_hours <= 12:
            freshness_boost = 16
        elif age_hours <= 24:
            freshness_boost = 8

    if is_actionable or normalized_severity == "critical" or (hours_until_due is not None and hours_until_due <= 6) or score >= 80:
        due_bucket = "needs_decision_now"
    elif normalized_severity in {"high", "medium"} or (hours_until_due is not None and hours_until_due <= 24) or score >= 52:
        due_bucket = "today"
    else:
        due_bucket = "can_wait"

    return {
        "urgencyScore": score,
        "urgencyLabel": {
            "needs_decision_now": "דורש החלטה עכשיו",
            "today": "להיום",
            "can_wait": "אפשר לחכות",
        }[due_bucket],
        "dueBucket": due_bucket,
        "isActionable": is_actionable,
        "dueAt": _iso_z(due_at),
        "priority": _priority_from_bucket(due_bucket),
        "freshnessBoost": freshness_boost,
        "sortRank": score + freshness_boost,
    }


def _load_workflow_actions(user_id: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    try:
        if workflow_state_store.actions is not None:
            cursor = workflow_state_store.actions.find({"user_id": user_id}).sort("created_at", -1)
            actions.extend(list(cursor))
        else:
            actions.extend(
                [
                    doc
                    for doc in getattr(workflow_state_store, "_memory_actions", {}).values()
                    if doc.get("user_id") == user_id
                ]
            )
    except Exception as exc:
        server_logger.warning(f"⚠️ Dashboard action load failed: {exc}")
    return actions


def _dashboard_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str, int]:
    due_bucket = str(item.get("dueBucket") or "")
    due_bucket_weight = {
        "needs_decision_now": 3,
        "today": 2,
        "can_wait": 1,
    }.get(due_bucket, 0)
    return (
        1 if item.get("isActionable") else 0,
        1 if int(item.get("freshnessBoost") or 0) > 0 else 0,
        due_bucket_weight,
        str(item.get("createdAt") or ""),
        int(item.get("sortRank") or item.get("urgencyScore") or 0),
    )


def _load_checkpoint_writes(limit: int = 50) -> list[dict[str, Any]]:
    try:
        db = _get_langgraph_db()
        coll = db["checkpoints.checkpointing_db.checkpoint_writes"]
        return list(coll.find({}).sort([("_id", -1)]).limit(limit))
    except Exception as exc:
        server_logger.warning(f"⚠️ Dashboard checkpoint load failed: {exc}")
        return []


def _latest_checkpoint_error(thread_id: str) -> str:
    try:
        db = _get_langgraph_db()
        coll = db["checkpoints.checkpointing_db.checkpoint_writes"]
        doc = coll.find_one(
            {"thread_id": thread_id, "channel": "__error__"},
            sort=[("_id", -1)],
        )
    except Exception as exc:
        server_logger.warning(f"Dashboard checkpoint error lookup failed: {exc}")
        return ""

    if not doc:
        return ""

    raw_value = doc.get("value")
    if isinstance(raw_value, bytes):
        text = raw_value.decode("utf-8", errors="ignore")
    else:
        text = str(raw_value or "")

    match = re.search(r"(UnicodeEncodeError\(.+?\))", text)
    if match:
        return match.group(1)
    return text.strip()


def _compact_text(value: Any, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _strip_summary_noise(text: str) -> str:
    cleaned = _strip_nested_email_metadata(text or "")
    cleaned, _ = parse_button_marker(cleaned)
    cleaned = re.sub(r"^(?:re|fw|fwd)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\[[^\]]+\]\s*", "", cleaned)
    cleaned = re.sub(r"^(?:היי|שלום|hi|hello|dear)\s+[^,\n]+,\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:היי|שלום|hi|hello|dear)\s*,\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?\b", "", cleaned)
    cleaned = re.sub(r"^(?:summary|subject|content)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -:,.")


def _looks_generic_summary(text: str) -> bool:
    normalized = _strip_summary_noise(text).lower()
    if not normalized:
        return True
    generic_values = {
        "no subject",
        "subject",
        "message",
        "email",
        "update",
        "question",
        "reply",
        "hello",
        "hi",
        "שלום",
        "היי",
        "עדכון",
        "שאלה",
        "תגובה",
    }
    return normalized in generic_values


def _first_summary_clause(text: str) -> str:
    candidate = _strip_summary_noise(text)
    if not candidate:
        return ""
    parts = re.split(r"\n+|\s+\|\s+|[.!?]\s+|;\s+", candidate, maxsplit=1)
    return parts[0].strip(" -:,.")


def _compress_summary_phrase(text: str, *, limit: int = 72, max_words: int = 8) -> str:
    clause = _first_summary_clause(text)
    if not clause:
        return ""
    words = clause.split()
    if len(words) > max_words:
        clause = " ".join(words[:max_words]).rstrip(",;:-") + "…"
    return _compact_text(clause, limit=limit)


def _build_email_context_summary(
    *,
    subject: str = "",
    body: str = "",
    ai_summary: str = "",
    limit: int = 72,
) -> str:
    candidates = [
        _compress_summary_phrase(subject, limit=limit, max_words=8),
        _compress_summary_phrase(ai_summary, limit=limit, max_words=9),
        _compress_summary_phrase(body, limit=limit, max_words=9),
    ]
    for candidate in candidates:
        if candidate and not _looks_broken_summary(candidate) and not _looks_generic_summary(candidate):
            return candidate

    fallback = _compact_text(_first_summary_clause(subject or ai_summary or body), limit=limit)
    return fallback if fallback else _compact_text(subject or ai_summary or body, limit=limit)


def _looks_broken_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return text.count("?") >= 4 or text.count("�") >= 2


def _preview_title_candidate(value: Any) -> str:
    for raw_line in str(value or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[^\w\u0590-\u05FF\u0600-\u06FF]+", "", line).strip()
        if line:
            return line
    return ""


def _incoming_email_title(params: dict[str, Any]) -> str:
    subject = str((params or {}).get("subject") or "").strip()
    approval_type = str((params or {}).get("approval_type") or "").strip()
    if _looks_broken_text(subject):
        for key in ("event_title", "draft_subject", "title"):
            candidate = str((params or {}).get(key) or "").strip()
            if candidate and not _looks_broken_text(candidate):
                subject = candidate
                break
        else:
            preview_candidate = _preview_title_candidate((params or {}).get("preview"))
            if preview_candidate and not _looks_broken_text(preview_candidate):
                subject = preview_candidate
    if subject:
        if approval_type in {"create_event", "update_event_time"}:
            return f"Meeting: {subject}"
        if approval_type in {"create_draft", "send_email"}:
            return f"Reply Needed: {subject}"
        return subject
    if approval_type in {"create_event", "update_event_time"}:
        return "Meeting Request"
    return "Incoming Email"


def _incoming_email_description(params: dict[str, Any]) -> str:
    sender = str((params or {}).get("sender") or "").strip()
    summary = str((params or {}).get("summary") or "").strip()
    preview = str((params or {}).get("preview") or "").strip()
    error = str((params or {}).get("error") or "").strip()
    pieces: list[str] = []
    if sender:
        pieces.append(f"from {_format_sender_for_card(sender)}")
    if summary and not _looks_broken_text(summary):
        pieces.append(_compact_text(summary, limit=72))
    elif preview:
        pieces.append(_compress_summary_phrase(preview, limit=72, max_words=9) or _compact_text(preview, limit=72))
    if error:
        pieces.append(_compact_text(error, limit=72))
    if not pieces:
        return "Pending incoming email"
    return " | ".join(pieces)


def _strip_leading_symbols(text: Any) -> str:
    return re.sub(r"^[^0-9A-Za-z\u0590-\u05FF\u0600-\u06FF]+", "", str(text or "")).strip()


def _clean_subject_for_card(subject: Any) -> str:
    cleaned = _strip_summary_noise(str(subject or ""))
    if not cleaned:
        cleaned = str(subject or "").strip()
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -")
    return _compact_text(cleaned, limit=120)


def _looks_low_signal_headline(text: Any) -> bool:
    normalized = _strip_summary_noise(str(text or "")).strip().lower()
    if not normalized:
        return True
    return normalized in {
        "פגישה",
        "meeting",
        "meeting request",
        "reply needed",
        "reply",
        "email",
        "incoming email",
        "draft",
        "טיוטה",
        "message",
        "מייל",
    }


def _card_kind_label(action_type: str) -> str:
    return {
        "incoming_email": "מייל",
        "send_email": "תשובה",
        "create_draft": "טיוטת תשובה",
        "create_event": "פגישה",
        "update_event_time": "שינוי פגישה",
        "delete_event": "מחיקת פגישה",
        "trash_email": "מחיקת מייל",
        "multi_step": "כמה פעולות",
    }.get(str(action_type or ""), "פעולה")


def _recommended_outcome_line(action_type: str) -> str:
    return {
        "send_email": "באישור, הסוכן ישלח את התשובה.",
        "create_draft": "באישור, הסוכן ישלח את התשובה.",
        "create_event": "באישור, הסוכן יקבע את הפגישה ביומן.",
        "update_event_time": "באישור, הסוכן יעדכן את מועד הפגישה ביומן.",
        "delete_event": "באישור, הסוכן ימחק את האירוע מהיומן.",
        "trash_email": "באישור, הסוכן יסיר את ההודעה.",
        "multi_step": "באישור, הסוכן יבצע את רצף הפעולות המוצע.",
    }.get(str(action_type or ""), "באישור, הסוכן יבצע את הפעולה.")


def _primary_action_label(actions: list[dict[str, Any]]) -> str:
    for action in actions:
        if str(action.get("variant") or "") == "primary":
            return _strip_leading_symbols(action.get("label"))
    for action in actions:
        label = _strip_leading_symbols(action.get("label"))
        if label:
            return label
    return ""


def _sender_line_for_card(params: dict[str, Any]) -> str:
    sender_value = str((params or {}).get("sender") or "").strip()
    if not sender_value:
        return ""
    return _format_sender_for_card(sender_value)


def _summary_line_for_card(action: str, params: dict[str, Any]) -> str:
    subject = str((params or {}).get("subject") or (params or {}).get("draft_subject") or (params or {}).get("title") or "")
    ai_summary = str((params or {}).get("summary") or "")
    draft_preview = str((params or {}).get("draft_preview") or "")
    preview = str((params or {}).get("preview") or "")
    candidate = _build_email_context_summary(
        subject=subject,
        ai_summary=ai_summary,
        body=draft_preview or preview,
        limit=96,
    )
    if candidate and not _looks_generic_summary(candidate) and not _looks_low_signal_headline(candidate):
        return candidate
    event_title = _clean_subject_for_card((params or {}).get("event_title"))
    if event_title and not _looks_low_signal_headline(event_title):
        return event_title
    fallback = _action_description(action, params)
    return _compact_text(fallback, limit=96)


def _split_heading_block(block: str) -> tuple[str, str]:
    text = str(block or "").strip()
    if not text:
        return "", ""
    lines = [line.rstrip() for line in text.splitlines()]
    first_line = _strip_leading_symbols(lines[0])
    if len(lines) > 1 and (first_line.endswith(":") or ":" in first_line):
        heading = first_line.rstrip(":").strip()
        body = "\n".join(line.strip() for line in lines[1:]).strip()
        if not body and ":" in first_line:
            head, inline_body = first_line.split(":", 1)
            return head.strip(), inline_body.strip()
        return heading, body
    if len(lines) == 1 and ":" in first_line:
        heading, body = first_line.split(":", 1)
        return heading.strip(), body.strip()
    return "", text


def _approval_preview_sections(action_type: str, params: dict[str, Any]) -> dict[str, Any]:
    preview_text, _ = parse_button_marker(str((params or {}).get("preview") or ""))
    context_lines: list[str] = []
    draft_title = ""
    draft_text = str((params or {}).get("draft_text") or (params or {}).get("draft_preview") or "").strip()
    translation_note = ""
    recommendation = ""

    draft_lines: list[str] = []
    translation_lines: list[str] = []
    recommendation_lines: list[str] = []
    current_section = "context"

    for raw_line in preview_text.splitlines():
        line = raw_line.rstrip()
        normalized = _strip_leading_symbols(line)
        lowered = normalized.lower()

        if not normalized:
            if current_section == "draft" and draft_lines and draft_lines[-1] != "":
                draft_lines.append("")
            elif current_section == "translation" and translation_lines and translation_lines[-1] != "":
                translation_lines.append("")
            continue

        if normalized.startswith("טיוטת") or normalized.startswith("טיוטה") or lowered.startswith("draft"):
            heading, body = _split_heading_block(line)
            draft_title = _strip_leading_symbols(heading) or draft_title or "טיוטה מוצעת"
            current_section = "draft"
            if body:
                draft_lines.append(body)
            continue

        if normalized.startswith("תרגום לעברית") or lowered.startswith("translation"):
            heading, body = _split_heading_block(line)
            current_section = "translation"
            if body:
                translation_lines.append(body)
            continue

        if normalized.startswith("הצעה לפעולה") or lowered.startswith("recommended action") or lowered.startswith("suggested action"):
            heading, body = _split_heading_block(line)
            current_section = "recommendation"
            if body:
                recommendation_lines.append(body)
            continue

        if current_section == "draft":
            draft_lines.append(line.strip())
        elif current_section == "translation":
            translation_lines.append(line.strip())
        elif current_section == "recommendation":
            recommendation_lines.append(line.strip())
        else:
            context_lines.append(normalized)

    if draft_lines:
        parsed_draft = "\n".join(draft_lines).strip()
        if len(parsed_draft) >= len(draft_text):
            draft_text = parsed_draft

    if translation_lines:
        translation_note = "\n".join(translation_lines).strip()

    if recommendation_lines:
        recommendation = " ".join(part.strip() for part in recommendation_lines if part.strip()).strip()

    if not draft_title and draft_text:
        draft_title = "טיוטה מוצעת"

    if not recommendation:
        recommendation = _recommended_outcome_line(action_type)

    deduped_context: list[str] = []
    seen_context: set[str] = set()
    for line in context_lines:
        normalized_line = re.sub(r"\s+", " ", line).strip()
        if not normalized_line or normalized_line in seen_context:
            continue
        seen_context.add(normalized_line)
        deduped_context.append(normalized_line)

    return {
        "contextLines": deduped_context[:4],
        "draftTitle": draft_title,
        "draftText": draft_text,
        "translationNote": translation_note,
        "recommendation": recommendation,
    }


def _decision_subject_summary(action: str, params: dict[str, Any]) -> str:
    summary = _summary_line_for_card(action, params)
    if summary:
        return _compact_text(summary, limit=96)
    return _compact_text(_action_title(action, params), limit=96)


def _decision_meeting_time_label(params: dict[str, Any]) -> tuple[str, str]:
    due_at = _extract_due_datetime(params)
    due_at_iso = _iso_z(due_at)
    if not due_at_iso:
        return "", ""
    return due_at_iso, _format_datetime_for_user(due_at_iso)


def _build_decision_data(
    *,
    action: str,
    approval_action: str,
    params: dict[str, Any],
    actions: list[dict[str, Any]],
    urgency: dict[str, Any],
    confidence: int,
    preview_sections: dict[str, Any],
) -> dict[str, Any]:
    sender_raw = str((params or {}).get("sender") or "").strip()
    sender_display_name = _display_name_from_sender(sender_raw) if sender_raw else ""
    sender_short_name = _sender_name_first_last(sender_display_name)
    sender_email = _extract_sender_email(sender_raw)
    sender_identifier = sender_email or sender_display_name or sender_raw
    meeting_time, meeting_time_label = _decision_meeting_time_label(params)
    subject_summary = _decision_subject_summary(action, params)
    draft_text = str(
        (preview_sections or {}).get("draftText")
        or (params or {}).get("draft_text")
        or (params or {}).get("draft_preview")
        or ""
    ).strip()

    return {
        "urgencyLevel": str(urgency.get("priority") or _priority_from_bucket(str(urgency.get("dueBucket") or "today"))),
        "urgencyBucket": str(urgency.get("dueBucket") or ""),
        "urgencyLabel": str(urgency.get("urgencyLabel") or ""),
        "urgencyScore": int(urgency.get("urgencyScore") or 0),
        "confidence": confidence,
        "senderShortName": sender_short_name or sender_display_name or sender_identifier,
        "senderDisplayName": sender_display_name,
        "senderEmail": sender_email,
        "senderIdentifier": sender_identifier,
        "senderRaw": sender_raw,
        "isMeeting": bool(
            approval_action in {"create_event", "update_event_time", "multi_step"}
            or (params or {}).get("event_start")
            or (params or {}).get("start_time")
            or (params or {}).get("new_start_time")
        ),
        "meetingTime": meeting_time,
        "meetingTimeLabel": meeting_time_label,
        "subjectSummary": subject_summary,
        "draftTitle": str((preview_sections or {}).get("draftTitle") or "").strip(),
        "draftText": draft_text,
        "suggestedAction": _primary_action_label(actions),
        "buttons": [
            {
                "id": str(action_item.get("id") or ""),
                "label": str(action_item.get("label") or ""),
                "variant": str(action_item.get("variant") or ""),
                "requiresInput": bool(action_item.get("requiresInput")),
                "callbackText": str(action_item.get("callbackText") or ""),
            }
            for action_item in actions
        ],
    }


def _approval_card_presentation(action: str, approval_action: str, params: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    headline_candidates = [
        (params or {}).get("subject"),
        (params or {}).get("event_title"),
        (params or {}).get("title"),
        (params or {}).get("draft_subject"),
        (params or {}).get("summary"),
        _preview_title_candidate((params or {}).get("preview")),
        _action_title(action, params),
    ]
    subject = ""
    for candidate in headline_candidates:
        cleaned_candidate = _clean_subject_for_card(candidate)
        if cleaned_candidate and not _looks_low_signal_headline(cleaned_candidate):
            subject = cleaned_candidate
            break
        if not subject and cleaned_candidate:
            subject = cleaned_candidate
    summary_line = _summary_line_for_card(action, params)
    sender_line = _sender_line_for_card(params)
    primary_action = _primary_action_label(actions)
    preview_sections = _approval_preview_sections(approval_action, params)
    draft_excerpt = _compact_text(preview_sections.get("draftText") or "", limit=240)

    return {
        "headline": subject or _action_title(action, params),
        "kindLabel": _card_kind_label(approval_action),
        "summaryLine": summary_line,
        "senderLine": sender_line,
        "nextStepLine": primary_action,
        "outcomeLine": _recommended_outcome_line(approval_action),
        "draftExcerpt": draft_excerpt,
        "previewSections": preview_sections,
    }


def _action_title(action: str, params: dict[str, Any]) -> str:
    subject = (params or {}).get("subject") or (params or {}).get("title") or ""
    if action == "incoming_email":
        return _incoming_email_title(params)
    if action == "send_email":
        return f"Send email{f': {subject}' if subject else ''}"
    if action == "create_draft":
        return f"Draft email{f': {subject}' if subject else ''}"
    if action == "create_event":
        return f"Create event{f': {subject}' if subject else ''}"
    if action == "update_event_time":
        return f"Reschedule event{f': {subject}' if subject else ''}"
    if action == "delete_event":
        return f"Delete event{f': {subject}' if subject else ''}"
    if action == "trash_email":
        return f"Trash email{f': {subject}' if subject else ''}"
    return action.replace("_", " ").title()


def _action_description(action: str, params: dict[str, Any]) -> str:
    if action == "incoming_email":
        return _incoming_email_description(params)
    pieces: list[str] = []
    for key in ("to_email", "email", "summary", "subject", "thread_id"):
        value = (params or {}).get(key)
        if value:
            pieces.append(f"{key.replace('_', ' ')}: {value}")
    if not pieces and params:
        pieces.append(", ".join(f"{k}: {v}" for k, v in list(params.items())[:3]))
    if not pieces:
        pieces.append(f"Pending {action.replace('_', ' ')}")
    return " | ".join(pieces)


def _confidence_for_action(action: str, params: dict[str, Any]) -> int:
    if action == "incoming_email":
        approval_type = str((params or {}).get("approval_type") or "")
        if approval_type in {"create_event", "send_email"}:
            return 86
        if approval_type in {"create_draft", "update_event_time"}:
            return 78
        if (params or {}).get("error"):
            return 35
        return 60 if params else 50
    if action in {"send_email", "create_event"}:
        return 88
    if action in {"create_draft", "update_event_time"}:
        return 80
    if action in {"trash_email", "delete_event"}:
        return 72
    return 65 if params else 50


def _status_severity(action: str, status: str) -> str:
    if action == "incoming_email":
        if status == "error":
            return "critical"
        if status == "pending":
            return "medium"
        return "low"
    if status in {"critical", "high"}:
        return "critical"
    if action in {"send_email", "delete_event", "trash_email"}:
        return "high"
    if action in {"create_event", "update_event_time", "create_draft"}:
        return "medium"
    return "low"


def _dashboard_preview_is_suppressed(params: dict[str, Any]) -> bool:
    preview = str((params or {}).get("preview") or "").strip().lower()
    if not preview:
        return False
    suppressed_markers = {
        "[ignore_email]",
        "low-value-notification",
        "empty-email",
    }
    return any(marker in preview for marker in suppressed_markers)


def _dashboard_action_has_hitl_intent(action: str, params: dict[str, Any]) -> bool:
    approval_action = str((params or {}).get("approval_type") or action or "").strip()
    tool_names = {str(name).strip() for name in ((params or {}).get("tool_names") or []) if str(name).strip()}
    hitl_actions = {"send_email", "create_draft", "create_event", "update_event_time", "delete_event", "trash_email", "multi_step"}
    return approval_action in hitl_actions or bool(tool_names & hitl_actions)


def _dashboard_should_surface_action(doc: dict[str, Any], *, include_resolved: bool = True) -> bool:
    status = str(doc.get("status") or "pending").strip().lower()
    if status in {"ignored", "dismissed", "expired"}:
        return False
    if not include_resolved and status in {"approved", "rejected", "completed"}:
        return False

    params = doc.get("params") or {}
    if bool(params.get("dismissed")):
        return False
    if _dashboard_preview_is_suppressed(params):
        return False

    action = str(doc.get("action") or "").strip()
    if action == "incoming_email":
        return _dashboard_action_has_hitl_intent(action, params)

    return True


def _dashboard_should_surface_summary(doc: dict[str, Any]) -> bool:
    if not _dashboard_should_surface_action(doc):
        return False

    action = str(doc.get("action") or "action")
    status = str(doc.get("status") or "")
    params = doc.get("params") or {}
    approval_action = str(params.get("approval_type") or action)
    created_at = _coerce_datetime(doc.get("created_at"))
    urgency = _urgency_meta(
        action=approval_action,
        status=status,
        params=params,
        created_at=created_at,
    )
    return str(urgency.get("priority") or "").strip().lower() != "low"


def _build_notification_cards(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    visible_actions = [
        doc
        for doc in actions
        if str(doc.get("status") or "pending") in {"error"}
        and _dashboard_should_surface_action(doc, include_resolved=False)
    ]
    for doc in visible_actions:
        action = str(doc.get("action") or "action")
        params = doc.get("params") or {}
        created_at = _coerce_datetime(doc.get("created_at"))
        status = str(doc.get("status") or "pending")
        severity = _status_severity(action, status)
        urgency = _urgency_meta(
            action=action,
            status=status,
            params=params,
            created_at=created_at,
            severity=severity,
        )
        cards.append(
            {
                "_id": str(doc.get("_id")),
                "title": _action_title(action, params),
                "body": _action_description(action, params),
                "source": str(doc.get("agent") or "LangGraph"),
                "severity": severity,
                "createdAt": _iso_z(created_at) or _iso_z(datetime.datetime.now(datetime.timezone.utc)),
                "dismissed": False,
                **urgency,
            }
        )
    cards.sort(key=_dashboard_sort_key, reverse=True)
    return cards[:10]


def _approval_actions_for_card(action_type: str, params: dict[str, Any], status: str) -> list[dict[str, Any]]:
    if status != "pending":
        return []

    preview_seed = str(
        (params or {}).get("preview")
        or (params or {}).get("draft")
        or (params or {}).get("answer")
        or _action_description(action_type, params)
    ).strip()
    cleaned_preview, marker_buttons = parse_button_marker(preview_seed)
    fallback_seed = cleaned_preview or _action_title(action_type, params) or preview_seed
    normalized_action = str(action_type or "").strip()
    tool_names = [str(name) for name in (params or {}).get("tool_names", []) if name]
    is_meeting = normalized_action in {"create_event", "update_event_time", "multi_step"} or "create_event" in tool_names
    is_draft = normalized_action in {"send_email", "create_draft"} or any(name in {"send_email", "create_draft"} for name in tool_names)

    if marker_buttons:
        raw_buttons = marker_buttons
    elif is_meeting:
        raw_buttons = ["אשר וסנכרן ליומן", "דחה בנימוס", MANUAL_OVERRIDE_BASE_TEXT]
    elif is_draft:
        raw_buttons = ["אשר ושלח", "דחה בנימוס", MANUAL_OVERRIDE_BASE_TEXT]
    else:
        raw_buttons = fallback_buttons_for_text(fallback_seed, is_paused=True)
    manual_callback = _callback_source_text(MANUAL_OVERRIDE_BASE_TEXT)
    primary_callbacks = {
        "אשר",
        "אשר ושלח",
        "אשר וסנכרן ליומן",
        "אשר טיוטה",
        "שלח עכשיו",
        "בצע פעולה",
    }
    ghost_callbacks = {"בטל", "מחק הודעה"}
    secondary_callbacks = {"דחה בנימוס", "דחה למחר", "הזכר לי מחר", "תזכיר לי לבדוק מחר"}

    actions: list[dict[str, Any]] = []
    seen_callbacks: set[str] = set()
    callback_id_map = {
        "אשר": "approve",
        "אשר ושלח": "approve-send",
        "אשר וסנכרן ליומן": "approve-calendar",
        "אשר טיוטה": "approve-draft",
        "שלח עכשיו": "send-now",
        "ערוך טיוטה": "edit-draft",
        "בצע פעולה": "execute-action",
        "בטל": "cancel",
        "דחה בנימוס": "decline-politely",
        "דחה למחר": "defer-tomorrow",
        "הזכר לי מחר": "remind-tomorrow",
        "תזכיר לי לבדוק מחר": "review-tomorrow",
        "תייק למועד מאוחר": "file-later",
        "תייק בארכיון": "archive",
        "מחק הודעה": "delete-message",
        manual_callback: "manual",
    }

    for raw_button in raw_buttons:
        callback_text = _callback_source_text(raw_button)
        if not callback_text or callback_text in seen_callbacks:
            continue
        seen_callbacks.add(callback_text)

        requires_input = callback_text == manual_callback
        variant = "secondary"
        if callback_text in primary_callbacks:
            variant = "primary"
        elif callback_text in ghost_callbacks:
            variant = "ghost"
        elif callback_text in secondary_callbacks:
            variant = "secondary"

        actions.append(
            {
                "id": callback_id_map.get(callback_text, re.sub(r"[^a-z0-9]+", "-", callback_text.encode("ascii", "ignore").decode("ascii").lower()).strip("-") or "action"),
                "label": _decorate_button_text(raw_button),
                "callbackText": callback_text,
                "variant": variant,
                "requiresInput": requires_input,
            }
        )

    return actions


def _build_approval_cards(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    visible_actions = [doc for doc in actions if _dashboard_should_surface_action(doc)]
    for doc in visible_actions:
        action = str(doc.get("action") or "action")
        params = doc.get("params") or {}
        approval_action = str(params.get("approval_type") or action)
        created_at = _coerce_datetime(doc.get("created_at"))
        status = str(doc.get("status") or "pending")
        content_text, _ = parse_button_marker(str(params.get("preview") or _action_description(action, params)))
        card_actions = _approval_actions_for_card(approval_action, params, status)
        presentation = _approval_card_presentation(action, approval_action, params, card_actions)
        confidence = _confidence_for_action(approval_action, params)
        urgency = _urgency_meta(
            action=approval_action,
            status=status,
            params=params,
            created_at=created_at,
        )
        decision_data = _build_decision_data(
            action=action,
            approval_action=approval_action,
            params=params,
            actions=card_actions,
            urgency=urgency,
            confidence=confidence,
            preview_sections=presentation.get("previewSections") or {},
        )
        cards.append(
            {
                "_id": str(doc.get("_id")),
                "agentName": str(doc.get("agent") or "LangGraph"),
                "actionType": approval_action,
                "title": _action_title(action, params),
                "description": _action_description(action, params),
                "content": content_text,
                "confidence": confidence,
                "status": status,
                "senderName": _format_sender_for_card(params.get("sender") or ""),
                "senderEmail": _extract_sender_email(params.get("sender") or ""),
                "summary": str(params.get("summary") or ""),
                "createdAt": _iso_z(created_at) or _iso_z(datetime.datetime.now(datetime.timezone.utc)),
                "resolvedAt": _iso_z(_coerce_datetime(doc.get("updated_at"))) if status in {"approved", "rejected", "completed", "dismissed"} else None,
                "actions": card_actions,
                "payload": _json_safe(params),
                "decisionData": decision_data,
                "threadId": str(doc.get("_id")),
                **presentation,
                **urgency,
            }
        )
    cards.sort(key=_dashboard_sort_key, reverse=True)
    return cards[:25]


def _build_activity_rows(user_id: str, limit: int = 50, page: int = 1) -> dict[str, Any]:
    actions = _load_workflow_actions(user_id)
    start_of_day = _start_of_local_day()
    start_of_week = _start_of_local_week()
    hours_saved_today = round(_sum_time_saved_minutes(user_id, since=start_of_day) / 60, 1)
    hours_saved_week = round(_sum_time_saved_minutes(user_id, since=start_of_week) / 60, 1)
    minutes_by_thread = _load_time_saved_minutes_by_thread(user_id)
    items: list[dict[str, Any]] = []
    if actions:
        for doc in actions:
            thread_id = str(doc.get("_id") or "")
            created_at = _coerce_datetime(doc.get("created_at"))
            minutes_saved = round(float(minutes_by_thread.get(thread_id, 0.0)), 1)
            items.append(
                {
                    "_id": thread_id,
                    "agentName": str(doc.get("agent") or "LangGraph"),
                    "action": str(doc.get("action") or "checkpoint"),
                    "description": _action_description(str(doc.get("action") or "checkpoint"), doc.get("params") or {}),
                    "status": str(doc.get("status") or "success"),
                    "minutesSaved": minutes_saved,
                    "createdAt": _iso_z(created_at) or _iso_z(datetime.datetime.now(datetime.timezone.utc)),
                }
            )
        total = len(items)
        start = max(0, (page - 1) * limit)
        page_items = items[start : start + limit]
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "pages": max(1, (total + limit - 1) // limit) if total else 1,
            "hoursSaved": hours_saved_today,
            "hoursSavedToday": hours_saved_today,
            "hoursSavedWeek": hours_saved_week,
        }

    writes = _load_checkpoint_writes(limit=max(limit * page, limit))
    grouped: dict[str, dict[str, Any]] = {}
    for doc in writes:
        thread_id = str(doc.get("thread_id") or "langgraph")
        created_at = _coerce_datetime(doc.get("_id"))
        existing = grouped.get(thread_id)
        if existing is None or (created_at and created_at > _coerce_datetime(existing.get("_created"))):
            grouped[thread_id] = {
                "_created": created_at,
                "_id": str(doc.get("_id")),
                "agentName": "LangGraph",
                "action": str(doc.get("channel") or "checkpoint"),
                "description": f"Checkpoint updated for {thread_id}",
                "status": "success",
                "minutesSaved": round(float(minutes_by_thread.get(thread_id, 0.0)), 1),
                "createdAt": _iso_z(created_at) or _iso_z(datetime.datetime.now(datetime.timezone.utc)),
            }

    all_items = list(grouped.values())
    all_items.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
    total = len(all_items)
    start = max(0, (page - 1) * limit)
    page_items = all_items[start : start + limit]
    return {
        "items": page_items,
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit) if total else 1,
        "hoursSaved": hours_saved_today,
        "hoursSavedToday": hours_saved_today,
        "hoursSavedWeek": hours_saved_week,
    }


def _build_agent_rows(user_id: str) -> list[dict[str, Any]]:
    actions = _load_workflow_actions(user_id)
    writes = _load_checkpoint_writes(limit=200)
    total_actions = len(actions) + len(writes)
    recent_time = max(
        [(_coerce_datetime(doc.get("created_at")) or _coerce_datetime(doc.get("_id")) or datetime.datetime.now(datetime.timezone.utc)) for doc in actions[:10]]
        + [(_coerce_datetime(doc.get("_id")) or datetime.datetime.now(datetime.timezone.utc)) for doc in writes[:10]],
        default=datetime.datetime.now(datetime.timezone.utc),
    )
    secretariat_count = sum(1 for doc in actions if str(doc.get("agent")) == "langgraph") or len(actions)
    knowledge_count = len(writes)
    today_cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    today_actions = sum(1 for doc in actions if (_coerce_datetime(doc.get("created_at")) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)) >= today_cutoff)
    today_writes = sum(1 for doc in writes if (_coerce_datetime(doc.get("_id")) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)) >= today_cutoff)

    return [
        {
            "_id": "secretariat-agent",
            "name": "Secretariat",
            "type": "SecretariatAgent",
            "description": "Email triage and calendar management",
            "status": "active" if actions else "idle",
            "color": "#6366f1",
            "lastAction": "LangGraph orchestration ready" if not actions else _action_title(str(actions[0].get("action") or "action"), actions[0].get("params") or {}),
            "lastRun": _iso_z(_coerce_datetime(actions[0].get("created_at")) if actions else recent_time),
            "actionsToday": today_actions,
            "totalActions": secretariat_count,
            "costToday": 0.0,
        },
        {
            "_id": "knowledge-agent",
            "name": "Knowledge",
            "type": "KnowledgeAgent",
            "description": "RAG memory and notes",
            "status": "active" if writes else "idle",
            "color": "#8b5cf6",
            "lastAction": "Checkpoint stream active" if not writes else f"Checkpoint {writes[0].get('channel')}",
            "lastRun": _iso_z(_coerce_datetime(writes[0].get("_id")) if writes else recent_time),
            "actionsToday": today_writes,
            "totalActions": knowledge_count,
            "costToday": 0.0,
        },
    ]


def _build_agent_stats(user_id: str) -> dict[str, int]:
    agents = _build_agent_rows(user_id)
    counts = Counter(agent.get("status", "idle") for agent in agents)
    return {
        "total": len(agents),
        "active": counts.get("active", 0),
        "paused": counts.get("paused", 0),
        "error": counts.get("error", 0),
    }


def _build_summaries(user_id: str, source: Optional[str] = None, unread: Optional[bool] = None) -> list[dict[str, Any]]:
    actions = _load_workflow_actions(user_id)
    if actions:
        visible_actions = [
            doc
            for doc in actions
            if str(doc.get("status") or "") != "processing"
            and _dashboard_should_surface_summary(doc)
        ]
        summaries: list[dict[str, Any]] = []
        for doc in visible_actions:
            action = str(doc.get("action") or "action")
            status = str(doc.get("status") or "")
            params = doc.get("params") or {}
            approval_action = str(params.get("approval_type") or action)
            preview_text = str(params.get("preview") or _action_description(action, params))
            cleaned_content, _ = parse_button_marker(preview_text)
            created_at = _coerce_datetime(doc.get("created_at"))
            summary_actions = _approval_actions_for_card(approval_action, params, status)
            preview_sections = _approval_preview_sections(approval_action, params)
            urgency = _urgency_meta(
                action=approval_action,
                status=status,
                params=params,
                created_at=created_at,
            )
            confidence = _confidence_for_action(approval_action, params)
            decision_data = _build_decision_data(
                action=action,
                approval_action=approval_action,
                params=params,
                actions=summary_actions,
                urgency=urgency,
                confidence=confidence,
                preview_sections=preview_sections,
            )
            summaries.append(
                {
                    "_id": str(doc.get("_id")),
                    "agentName": str(doc.get("agent") or "LangGraph"),
                    "source": str(params.get("source") or "langgraph"),
                    "title": _action_title(action, params),
                    "content": cleaned_content,
                    "senderName": _format_sender_for_card(params.get("sender") or ""),
                    "senderEmail": _extract_sender_email(params.get("sender") or ""),
                    "summary": str(params.get("summary") or ""),
                    "sentiment": "neutral",
                    "tags": ["dashboard", "preview"],
                    "priority": urgency["priority"],
                    "confidence": confidence,
                    "read": False if unread is None else not unread,
                    "createdAt": _iso_z(created_at) or _iso_z(datetime.datetime.now(datetime.timezone.utc)),
                    "status": status,
                    "threadId": str(doc.get("_id")),
                    "actions": summary_actions,
                    "decisionData": decision_data,
                    **urgency,
                }
            )
        if source:
            summaries = [item for item in summaries if item.get("source") == source]
        if unread is True:
            summaries = [item for item in summaries if not item.get("read")]
        if unread is False:
            summaries = [item for item in summaries if item.get("read")]
        summaries.sort(key=_dashboard_sort_key, reverse=True)
        return summaries[:50]

    writes = _load_checkpoint_writes(limit=100)
    grouped: dict[str, dict[str, Any]] = {}
    for doc in writes:
        thread_id = str(doc.get("thread_id") or "langgraph")
        created_at = _coerce_datetime(doc.get("_id"))
        existing = grouped.get(thread_id)
        if existing is None or (created_at and created_at > _coerce_datetime(existing.get("_created"))):
            grouped[thread_id] = {
                "_created": created_at,
                "_id": thread_id,
                "agentName": "LangGraph",
                "source": source or "langgraph",
                "title": f"Checkpoint thread {thread_id[:8]}",
                "content": f"Latest checkpoint activity recorded for thread {thread_id}.",
                "sentiment": "neutral",
                "tags": ["checkpoint", "langgraph"],
                "priority": "medium",
                "read": False if unread is None else not unread,
                "createdAt": _iso_z(created_at) or _iso_z(datetime.datetime.now(datetime.timezone.utc)),
                "urgencyScore": 40,
                "urgencyLabel": "Can Wait",
                "dueBucket": "can_wait",
                "isActionable": False,
                "dueAt": None,
            }
    summaries = list(grouped.values())
    summaries.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
    if source:
        summaries = [item for item in summaries if item.get("source") == source]
    if unread is True:
        summaries = [item for item in summaries if not item.get("read")]
    if unread is False:
        summaries = [item for item in summaries if item.get("read")]
    return summaries[:50]


def _sum_collection_value(
    collection,
    *,
    user_id: str,
    fields: list[str],
    since: datetime.datetime | None = None,
) -> float:
    match = _dashboard_match(user_id, since=since)
    total = 0.0
    for field in fields:
        try:
            pipeline = [{"$match": match}, {"$group": {"_id": None, "total": {"$sum": f"${field}"}}}]
            result = list(collection.aggregate(pipeline))
            if result:
                total = float(result[0].get("total") or 0.0)
                if total:
                    return total
        except Exception:
            continue
    return total


def _count_collection_for_user(collection, user_id: str, since: datetime.datetime | None = None) -> int:
    try:
        return int(collection.count_documents(_dashboard_match(user_id, since=since)))
    except Exception:
        return 0


def _load_time_saved_minutes_by_thread(user_id: str) -> dict[str, float]:
    try:
        docs = list(_get_dashboard_db()["time_saved_log"].find(_dashboard_match(user_id)))
    except Exception as exc:
        server_logger.warning(f"Time saved thread aggregation failed: {exc}")
        return {}

    minutes_by_thread: dict[str, float] = {}
    for doc in docs:
        thread_id = str(doc.get("thread_id") or "")
        if not thread_id:
            continue
        minutes_by_thread[thread_id] = minutes_by_thread.get(thread_id, 0.0) + float(doc.get("minutes_saved") or 0.0)
    return minutes_by_thread


def _sum_time_saved_minutes(user_id: str, since: datetime.datetime | None = None) -> float:
    try:
        return _sum_collection_value(
            _get_dashboard_db()["time_saved_log"],
            user_id=user_id,
            fields=["minutes_saved"],
            since=since,
        )
    except Exception as exc:
        server_logger.warning(f"Time saved aggregation failed: {exc}")
        return 0.0


def _build_finance_stats(user_id: str) -> dict[str, Any]:
    try:
        db = _get_dashboard_db()
        cost_log = db["cost_log"]
        fallback_collections = [db["finance"], db["finances"]]
        start_of_day = _start_of_local_day()
        now_local = datetime.datetime.now().astimezone()
        start_of_month = start_of_day.replace(day=1)

        has_real_cost_logs = _count_collection_for_user(cost_log, user_id) > 0
        if has_real_cost_logs:
            today_total = _sum_collection_value(
                cost_log,
                user_id=user_id,
                fields=["estimated_cost_usd", "amount", "cost"],
                since=start_of_day,
            )
            month_total = _sum_collection_value(
                cost_log,
                user_id=user_id,
                fields=["estimated_cost_usd", "amount", "cost"],
                since=start_of_month,
            )
            count = _count_collection_for_user(cost_log, user_id, since=start_of_month)
        else:
            today_total = 0.0
            month_total = 0.0
            count = 0
            for collection in fallback_collections:
                today_total += _sum_collection_value(
                    collection,
                    user_id=user_id,
                    fields=["estimated_cost_usd", "amount", "cost"],
                    since=start_of_day,
                )
                month_total += _sum_collection_value(
                    collection,
                    user_id=user_id,
                    fields=["estimated_cost_usd", "amount", "cost"],
                    since=start_of_month,
                )
                count += _count_collection_for_user(collection, user_id, since=start_of_month)

        monthly_budget = 50.0
        return {
            "todayCost": round(today_total, 4),
            "monthCost": round(month_total, 4),
            "monthlyBudget": monthly_budget,
            "budgetUsedPct": int(round((month_total / monthly_budget) * 100)) if monthly_budget else 0,
            "count": count,
            "source": "cost_log" if has_real_cost_logs else "fallback",
            "asOf": _iso_z(now_local.astimezone(datetime.timezone.utc)),
        }
    except Exception as exc:
        server_logger.warning(f"⚠️ Dashboard finance stats fallback used: {exc}")
        return {
            "todayCost": 0.0,
            "monthCost": 0.0,
            "monthlyBudget": 50.0,
            "budgetUsedPct": 0,
            "count": 0,
            "source": "fallback",
        }

# --- מודלים ---
def _count_action_history(user_id: str) -> int:
    try:
        if workflow_state_store.history is not None:
            return int(workflow_state_store.history.count_documents({"user_id": user_id}))
    except Exception as exc:
        server_logger.warning(f"Dashboard history count failed: {exc}")
    return len([doc for doc in getattr(workflow_state_store, "_memory_history", []) if doc.get("user_id") == user_id])


def _build_history_rows(user_id: str, limit: int = 50, page: int = 1) -> dict[str, Any]:
    rows = workflow_state_store.list_history(user_id=user_id, limit=limit, page=page)
    items = [
        {
            "_id": str(doc.get("_id") or f"{doc.get('action_id')}:{doc.get('timestamp')}"),
            "actionId": str(doc.get("action_id") or ""),
            "threadId": str(doc.get("thread_id") or doc.get("action_id") or ""),
            "agentName": str(doc.get("agent") or "LangGraph"),
            "action": str(doc.get("action") or "action"),
            "eventType": str(doc.get("event_type") or "updated"),
            "description": _action_description(str(doc.get("action") or "action"), doc.get("params") or {}),
            "status": str(doc.get("status") or doc.get("event_type") or "updated"),
            "minutesSaved": 0,
            "createdAt": _iso_z(_coerce_datetime(doc.get("timestamp"))) or _iso_z(datetime.datetime.now(datetime.timezone.utc)),
            "payload": _json_safe(doc.get("params") or {}),
        }
        for doc in rows
    ]
    total = _count_action_history(user_id)
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit) if total else 1,
    }


def _last_ai_with_visible_content(messages: list[BaseMessage]) -> AIMessage | None:
    return next(
        (
            msg
            for msg in reversed(messages)
            if isinstance(msg, AIMessage) and extract_text(msg.content).strip()
        ),
        None,
    )


def _collect_action_runtime_state(action_id: str, *, fallback_answer: str = "") -> dict[str, Any]:
    if not graph:
        return {
            "is_paused": False,
            "error": "Graph unavailable",
            "preview": fallback_answer.strip(),
            "tool_payload": {},
        }

    config = {"configurable": {"thread_id": action_id}}
    state = graph.get_state(config)
    messages = list(state.values.get("messages", [])) if state and state.values else []
    is_paused = bool(state.next and any("sensitive" in step for step in state.next))
    latest_error = _latest_checkpoint_error(action_id)
    pending_ai = _last_unresolved_ai_with_tools(messages)
    last_ai_with_content = _last_ai_with_visible_content(messages)
    preview = fallback_answer.strip()
    tool_payload: dict[str, Any] = {}

    if pending_ai and getattr(pending_ai, "tool_calls", None):
        tool_payload = _extract_action_payload_from_tool_calls(list(getattr(pending_ai, "tool_calls", []) or []))
        preview = _render_pending_approval(
            list(getattr(pending_ai, "tool_calls", []) or []),
            messages,
            extract_text(last_ai_with_content.content) if last_ai_with_content else preview,
        ).strip()
    elif not preview:
        preview = (
            _extract_success_message_from_state(messages)
            or (extract_text(last_ai_with_content.content) if last_ai_with_content else "")
        ).strip()

    return {
        "is_paused": is_paused,
        "error": latest_error.strip(),
        "preview": preview,
        "tool_payload": tool_payload,
    }


def _log_time_saved_outcome(
    *,
    user_id: str,
    thread_id: str,
    action_type: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        log_time_saved(
            user_id=user_id,
            agent_name="SecretariatAgent",
            action_type=action_type,
            thread_id=thread_id,
            dedupe_key=f"{thread_id}:{action_type}",
            metadata=metadata or {},
        )
    except Exception as exc:
        server_logger.warning(f"Time saved logging failed for {action_type}: {exc}")


def _log_post_execution_time_saved(
    *,
    user_id: str,
    thread_id: str,
    successful_tool_names: set[str],
    metadata: dict[str, Any] | None = None,
) -> None:
    if "send_email" in successful_tool_names:
        _log_time_saved_outcome(
            user_id=user_id,
            thread_id=thread_id,
            action_type="send_email",
            metadata=metadata,
        )
    elif "create_draft" in successful_tool_names:
        _log_time_saved_outcome(
            user_id=user_id,
            thread_id=thread_id,
            action_type="draft_created",
            metadata=metadata,
        )

    if "create_event" in successful_tool_names:
        _log_time_saved_outcome(
            user_id=user_id,
            thread_id=thread_id,
            action_type="create_event",
            metadata=metadata,
        )


def _require_action_doc(action_id: str, user_id: str) -> dict[str, Any]:
    doc = workflow_state_store.get_action(action_id)
    if not doc or str(doc.get("user_id") or "admin") != user_id:
        raise HTTPException(status_code=404, detail="Action not found")
    return doc


def _resolve_dashboard_hitl_action(action_id: str, *, callback_text: str, user_id: str) -> dict[str, Any]:
    _require_action_doc(action_id, user_id=user_id)
    response = ask_brain(
        RequestModel(
            text=f"{callback_text}::{action_id}",
            source="dashboard",
            user_id=user_id,
            thread_id=action_id,
        )
    )
    runtime = _collect_action_runtime_state(action_id, fallback_answer=str(response.get("answer") or ""))
    merge_params = {
        "preview": runtime["preview"],
        "resolution_source": "dashboard",
    }
    merge_params.update(runtime["tool_payload"])
    if runtime["error"]:
        merge_params["error"] = runtime["error"]

    if callback_text == "בטל":
        next_status = "rejected"
    elif runtime["error"] or response.get("status") == "error":
        next_status = "error"
    elif response.get("is_paused"):
        next_status = "pending"
    else:
        next_status = "approved"

    workflow_state_store.update_action(action_id, status=next_status, merge_params=merge_params)
    updated_doc = workflow_state_store.get_action(action_id) or {}
    action_cards = _build_approval_cards([updated_doc]) if updated_doc else []
    return {
        "response": response,
        "action": action_cards[0] if action_cards else _to_public_doc(updated_doc),
    }


def _resolve_dashboard_feedback(action_id: str, *, feedback_text: str, user_id: str) -> dict[str, Any]:
    _require_action_doc(action_id, user_id=user_id)
    response = ask_brain(
        RequestModel(
            text=feedback_text,
            source="dashboard",
            user_id=user_id,
            thread_id=action_id,
        )
    )
    runtime = _collect_action_runtime_state(action_id, fallback_answer=str(response.get("answer") or ""))
    merge_params = {
        "preview": runtime["preview"],
        "resolution_source": "dashboard",
        "latest_feedback": feedback_text.strip(),
    }
    merge_params.update(runtime["tool_payload"])
    if runtime["error"]:
        merge_params["error"] = runtime["error"]

    next_status = "error" if runtime["error"] or response.get("status") == "error" else ("pending" if response.get("is_paused") else "approved")
    workflow_state_store.update_action(action_id, status=next_status, merge_params=merge_params)
    updated_doc = workflow_state_store.get_action(action_id) or {}
    action_cards = _build_approval_cards([updated_doc]) if updated_doc else []
    return {
        "response": response,
        "action": action_cards[0] if action_cards else _to_public_doc(updated_doc),
    }


class RequestModel(BaseModel):
    text: str
    source: str = "telegram"
    user_id: Optional[str] = None
    email_id: Optional[str] = None 
    images: Optional[List[str]] = None
    reply_to_message_id: Optional[int] = None 
    thread_id: Optional[str] = None

class ExecutionRequest(BaseModel):
    action: str
    params: dict


class DashboardFeedbackRequest(BaseModel):
    text: str
    user_id: Optional[str] = None


class DashboardCallbackRequest(BaseModel):
    callback_text: str
    user_id: Optional[str] = None


def _require_dashboard_user_id(user_id: Optional[str]) -> str:
    normalized = str(user_id or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="user_id is required")
    return normalized


def _resolve_request_user_id(payload: RequestModel) -> str:
    normalized = str(payload.user_id or "").strip()
    if normalized:
        return normalized

    if str(payload.source or "").strip().lower() == "dashboard":
        raise HTTPException(status_code=400, detail="user_id is required for dashboard requests")

    return "admin"


def _graph_invoke_as_user(user_id: str, payload: Any, config: dict[str, Any]):
    with active_user_context(user_id):
        return graph.invoke(payload, config)


def _graph_stream_as_user(user_id: str, payload: Any, config: dict[str, Any], *, stream_mode: str = "values"):
    with active_user_context(user_id):
        for event in graph.stream(payload, config, stream_mode=stream_mode):
            yield event


def _gmail_send_email_as_user(user_id: str, *args, **kwargs):
    with active_user_context(user_id):
        return gmail_send_email(*args, **kwargs)


@app.get("/")
def home():
    return {"status": "online", "message": "MyOS Manager (LangGraph) is running"}

# --- 1. זיכרון (RAG) ---
@app.post("/memorize")
def memorize_info(payload: RequestModel):
    knowledge_agent.memorize(payload.text, source=payload.source)
    msg = "Saved to memory"
    return {"status": "success", "message": msg, "answer": msg, "draft": msg}

# --- פונקציות עזר לבדיקת אישור ---
@app.get("/dashboard/notifications")
def dashboard_notifications(user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    actions = _load_workflow_actions(user_id)
    cards = _build_notification_cards(actions)
    return cards


@app.get("/dashboard/approvals")
def dashboard_approvals(status: str = "pending", user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    cards = _build_approval_cards(_load_workflow_actions(user_id))
    if status:
        cards = [card for card in cards if card.get("status") == status]
    return cards


@app.get("/dashboard/actions/{action_id}/decision-data")
def dashboard_action_decision_data(action_id: str, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    doc = _require_action_doc(action_id, user_id=user_id)
    cards = _build_approval_cards([doc])
    if not cards:
        raise HTTPException(status_code=404, detail="Decision data not found")
    card = cards[0]
    return {
        "actionId": action_id,
        "status": card.get("status"),
        "createdAt": card.get("createdAt"),
        "decisionData": card.get("decisionData") or {},
    }


@app.patch("/dashboard/approvals/{action_id}/approve")
def dashboard_approve_action(action_id: str, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    return _resolve_dashboard_hitl_action(action_id, callback_text="אשר", user_id=user_id)


@app.patch("/dashboard/approvals/{action_id}/action/{action_name}")
def dashboard_approval_action(action_id: str, action_name: str, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    callback_map = {
        "approve": "אשר",
        "send": "אשר ושלח",
        "schedule": "אשר וסנכרן ליומן",
        "polite-decline": "דחה בנימוס",
        "reject": "בטל",
    }
    callback_text = callback_map.get(action_name)
    if not callback_text:
        raise HTTPException(status_code=404, detail="Approval action not found")
    return _resolve_dashboard_hitl_action(action_id, callback_text=callback_text, user_id=user_id)


@app.patch("/dashboard/approvals/{action_id}/callback")
def dashboard_approval_callback(action_id: str, payload: DashboardCallbackRequest):
    callback_text = str(payload.callback_text or "").strip()
    if not callback_text:
        raise HTTPException(status_code=400, detail="callback_text is required")
    user_id = _require_dashboard_user_id(payload.user_id)
    return _resolve_dashboard_hitl_action(action_id, callback_text=callback_text, user_id=user_id)


@app.patch("/dashboard/approvals/{action_id}/feedback")
def dashboard_approval_feedback(action_id: str, payload: DashboardFeedbackRequest):
    user_id = _require_dashboard_user_id(payload.user_id)
    return _resolve_dashboard_feedback(action_id, feedback_text=payload.text, user_id=user_id)


@app.patch("/dashboard/approvals/{action_id}/reject")
def dashboard_reject_action(action_id: str, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    return _resolve_dashboard_hitl_action(action_id, callback_text="בטל", user_id=user_id)


@app.delete("/dashboard/approvals/{action_id}")
def dashboard_dismiss_action(action_id: str, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    _require_action_doc(action_id, user_id=user_id)
    updated = workflow_state_store.update_action(
        action_id,
        status="dismissed",
        merge_params={
            "dismissed": True,
            "resolution_source": "dashboard",
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Action not found")

    updated_doc = workflow_state_store.get_action(action_id) or {}
    action_cards = _build_approval_cards([updated_doc]) if updated_doc else []
    return {
        "success": True,
        "action": action_cards[0] if action_cards else _to_public_doc(updated_doc),
    }


@app.delete("/dashboard/notifications/{action_id}")
def dashboard_dismiss_notification(action_id: str, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    _require_action_doc(action_id, user_id=user_id)
    updated = workflow_state_store.update_action(
        action_id,
        status="dismissed",
        merge_params={
            "dismissed": True,
            "resolution_source": "dashboard",
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@app.delete("/dashboard/summaries/{action_id}")
def dashboard_dismiss_summary(action_id: str, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    _require_action_doc(action_id, user_id=user_id)
    updated = workflow_state_store.update_action(
        action_id,
        status="dismissed",
        merge_params={
            "dismissed": True,
            "resolution_source": "dashboard_inbox",
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"success": True}


@app.get("/dashboard/activity")
def dashboard_activity(limit: int = 50, page: int = 1, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    return _build_activity_rows(user_id=user_id, limit=limit, page=page)


@app.get("/dashboard/history")
def dashboard_history(limit: int = 50, page: int = 1, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    return _build_history_rows(user_id=user_id, limit=limit, page=page)


@app.get("/dashboard/agents")
def dashboard_agents(user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    return _build_agent_rows(user_id=user_id)


@app.get("/dashboard/agents/stats")
def dashboard_agents_stats(user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    return _build_agent_stats(user_id=user_id)


@app.get("/dashboard/finances/stats")
def dashboard_finances_stats(user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    return _build_finance_stats(user_id=user_id)


@app.get("/dashboard/summaries")
def dashboard_summaries(source: Optional[str] = None, unread: Optional[bool] = None, user_id: Optional[str] = None):
    user_id = _require_dashboard_user_id(user_id)
    return _build_summaries(user_id=user_id, source=source, unread=unread)


def is_approval(text: str) -> bool:
    """Detects if the user text is an approval command, including button callback data."""
    affirmative = {
        "כן", "מאושר", "אשר", "שלח", "קבע", "יאללה", "סבבה", "אישור",
        "אשר וסנכרן ליומן", "אשר ושלח", "שלח עכשיו", "בצע פעולה",
        "approve", "confirm", "send it", "do it",
    }
    normalized = " ".join(text.lower().replace("_", " ").split())
    words = normalized.split()
    if normalized in affirmative:
        return True
    if len(words) <= 4:
        return any(
            phrase in normalized
            for phrase in affirmative
            if len(phrase) > 1
        )
    return False


def is_send_style_approval(text: str) -> bool:
    normalized = " ".join(text.lower().replace("_", " ").split())
    return normalized in {"אשר ושלח", "שלח עכשיו", "שלח", "send it", "send now"}


def is_rejection(text: str) -> bool:
    negative = {"לא", "בטל", "ביטול", "עזוב", "אל תשלח", "אל תקבע"}
    normalized = " ".join(text.lower().replace("_", " ").split())
    words = normalized.split()
    if normalized in negative:
        return True
    if len(words) <= 4:
        return any(phrase in normalized for phrase in negative if len(phrase) > 1)
    return False


def is_polite_decline_request(text: str) -> bool:
    normalized = text.lower().replace("_", " ")
    return "\u05d3\u05d7\u05d4 \u05d1\u05e0\u05d9\u05de\u05d5\u05e1" in normalized or "polite decline" in normalized


def is_manual_override(text: str) -> bool:
    normalized = text.lower().replace("_", " ")
    return "אגיב ידנית" in normalized or "אתן הכוונה" in normalized or "manual" in normalized

def extract_text(content) -> str:
    """Safely extracts a string from message content, whether it's a str or list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and "text" in part:
                texts.append(part["text"])
            elif hasattr(part, "get") and part.get("text"):
                texts.append(part.get("text"))
            elif hasattr(part, "text") and isinstance(part.text, str):
                texts.append(part.text)
        return "".join(texts)
    return ""


def _display_name_from_sender(raw_sender: str) -> str:
    sender = (raw_sender or "").strip()
    if not sender:
        return "לא ידוע"
    email_part = re.search(r"<(.+?)>", sender)
    if email_part:
        name_part = sender.replace(email_part.group(0), "").strip().strip('"')
        return name_part or email_part.group(1).split("@")[0]
    return sender.split("@")[0] if "@" in sender else sender.strip('"')


def _extract_email_context_from_messages(messages: list[BaseMessage]) -> dict[str, str]:
    context = {
        "sender": "",
        "subject": "",
        "content": "",
        "when_hint": "",
        "reply_possible": "",
        "sender_type": "",
        "attachments_verified": "",
        "attachment_names": "",
        "has_calendar_invite": "",
    }
    for msg in reversed(messages):
        if not isinstance(msg, HumanMessage):
            continue
        text = extract_text(msg.content)
        if "Email Content:" not in text:
            continue

        line_flags = re.MULTILINE
        sender_match = re.search(r"^From:\s*(.+)$", text, line_flags)
        subject_match = re.search(r"^Subject:\s*(.+)$", text, line_flags)
        reply_possible_match = re.search(r"^Reply-Possible:\s*(.+)$", text, line_flags)
        sender_type_match = re.search(r"^Sender-Type:\s*(.+)$", text, line_flags)
        attachments_verified_match = re.search(r"^Attachments-Verified:\s*(.+)$", text, line_flags)
        attachment_names_match = re.search(r"^Attachment-Names:\s*(.+)$", text, line_flags)
        calendar_invite_match = re.search(r"^Has-Calendar-Invite:\s*(.+)$", text, line_flags)
        content_match = re.search(r"^Content:\s*(.+)", text, re.MULTILINE | re.DOTALL)
        lower_text = text.lower()

        context["sender"] = sender_match.group(1).strip() if sender_match else ""
        context["subject"] = subject_match.group(1).strip() if subject_match else ""
        context["reply_possible"] = reply_possible_match.group(1).strip().lower() if reply_possible_match else ""
        context["sender_type"] = sender_type_match.group(1).strip().lower() if sender_type_match else ""
        context["attachments_verified"] = attachments_verified_match.group(1).strip().lower() if attachments_verified_match else ""
        context["attachment_names"] = attachment_names_match.group(1).strip() if attachment_names_match else ""
        context["has_calendar_invite"] = calendar_invite_match.group(1).strip().lower() if calendar_invite_match else ""
        context["content"] = _strip_nested_email_metadata(content_match.group(1).strip()) if content_match else ""

        if "tomorrow morning" in lower_text or "מחר בבוקר" in text:
            context["when_hint"] = "מחר בבוקר"
        elif "tomorrow" in lower_text or "מחר" in text:
            context["when_hint"] = "מחר"
        break
    return context


def _format_datetime_for_user(value: str | None) -> str:
    if not value:
        return "לא צוין"

    raw = value.strip()
    if not raw:
        return "לא צוין"

    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(normalized)
    except ValueError:
        return raw

    hebrew_days = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    day_name = hebrew_days[dt.weekday()]
    return f"יום {day_name}, {dt.strftime('%d.%m.%Y')} בשעה {dt.strftime('%H:%M')}"


def _extract_sender_email(raw_sender: str) -> str:
    sender = (raw_sender or "").strip()
    if not sender:
        return ""
    email_part = re.search(r"<(.+?)>", sender)
    if email_part:
        return email_part.group(1).strip()
    if "@" in sender:
        return sender.strip('"')
    return ""


def _format_sender_for_card(raw_sender: str) -> str:
    name = _display_name_from_sender(raw_sender)
    email = _extract_sender_email(raw_sender)
    if email and email.lower() != name.lower():
        return f"{name} ({email})"
    return name


def _sender_name_first_last(raw_name: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(raw_name or "").replace('"', "").strip())
    if not cleaned:
        return ""

    tokens = [token for token in cleaned.split(" ") if token]
    if len(tokens) >= 2:
        return f"{tokens[0]} {tokens[-1]}"
    return tokens[0] if tokens else ""


def _summarize_text(text: str, limit: int = 110) -> str:
    cleaned = _strip_nested_email_metadata(text or "")
    cleaned = re.sub(r"^(?:היי|שלום)\s+[^,\n]+,\s*", "", cleaned)
    cleaned = re.sub(r"^(?:hi|hello|dear)\s+[^,\n]+,\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.split(r"\n\s*(?:תודה|בברכה|thanks|best|regards)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = " ".join(cleaned.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _strip_nested_email_metadata(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    nested_prefix = re.compile(
        r"^(?:Date:\s*[^\n]+\n)?(?:From:\s*[^\n]+\n)?(?:Subject:\s*[^\n]+\n)?Content:\s*",
        re.IGNORECASE,
    )
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = nested_prefix.sub("", cleaned).strip()

    cleaned = re.sub(r"\b(?:From|Subject|Content):\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bNo Subject\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" -:\n")


def _safe_date_iso(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return dt.date().isoformat()


def _render_daily_agenda_for_card(start_time: str | None) -> str:
    date_iso = _safe_date_iso(start_time)
    if not date_iso:
        return ""

    try:
        agenda_text = get_events_for_date(date_iso)
    except Exception:
        return ""

    if not agenda_text or agenda_text.startswith("No events") or agenda_text.startswith("Error"):
        return ""

    lines: list[str] = []
    for raw_line in agenda_text.splitlines():
        clean_line = raw_line.strip()
        if not clean_line:
            continue
        clean_line = re.sub(r"^\[([^\]]+)\]\s*", r"\1 - ", clean_line)
        clean_line = re.sub(r"\s*\(ID:\s*[^)]+\)", "", clean_line, flags=re.IGNORECASE)
        lines.append(clean_line if clean_line.startswith("•") else f"• {clean_line}")

    if not lines:
        return ""

    return "📆 המשך הלוז לאותו יום:\n" + "\n".join(lines)


def _detect_draft_language(text: str) -> str:
    has_hebrew = bool(re.search(r"[א-ת]", text))
    has_latin = bool(re.search(r"[A-Za-z]", text))
    if has_hebrew:
        return "עברית"
    if has_latin:
        return "English"
    return "Mixed"


def _contains_hebrew(text: str) -> bool:
    return bool(re.search(r"[א-ת]", text or ""))


def _meeting_summary_line(content_summary: str, meeting_title: str) -> str:
    summary = _build_email_context_summary(
        subject=meeting_title,
        body=content_summary,
        limit=72,
    )
    if summary and _contains_hebrew(summary):
        return summary
    topic = (meeting_title or "").strip() or "הפגישה"
    return f"בקשה לתאם שיחה קצרה בנושא {topic} ולשלוח אישור חזרה."


def _attachment_summary_line(email_context: dict[str, str]) -> str:
    if email_context.get("attachments_verified") != "yes":
        return ""
    names = (email_context.get("attachment_names") or "").strip()
    if not names or names == "None":
        return "📎 קבצים מצורפים: קיים קובץ מצורף מאומת"
    return f"📎 קבצים מצורפים: {names}"


def _reply_possible_from_context(email_context: dict[str, str]) -> bool:
    return email_context.get("reply_possible") == "yes"


def _sender_type_from_context(email_context: dict[str, str]) -> str:
    return (email_context.get("sender_type") or "").strip().lower()


def _looks_like_low_value_notification(messages: list[BaseMessage]) -> bool:
    email_context = _extract_email_context_from_messages(messages)
    sender_type = _sender_type_from_context(email_context)
    if sender_type != "no-reply":
        return False

    haystack = f"{email_context.get('subject', '')} {email_context.get('content', '')}".lower()
    low_value_markers = [
        "linkedin",
        "notification",
        "posted:",
        "product update",
        "newsletter",
        "marketing",
        "office hours",
        "unsubscribe",
        "view in browser",
        "base44",
        "ludeo",
    ]
    return any(marker in haystack for marker in low_value_markers)


def _extract_translation_block(ai_text: str) -> str:
    text = (ai_text or "").strip()
    if not text:
        return ""

    match = re.search(
        r"(?:\*+)?׳×׳¨׳’׳•׳ ׳׳¢׳‘׳¨׳™׳×(?:\*+)?:?\s*(.+?)(?:\n\s*\n|$)",
        text,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return ""


def _strip_internal_approval_sections(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    headings = [
        "נ“… ׳™׳¦׳™׳¨׳× ׳׳™׳¨׳•׳¢ ׳׳׳™׳©׳•׳¨׳",
        "Create event for approval",
        "Email approval details",
    ]
    for heading in headings:
        idx = cleaned.find(heading)
        if idx > 0:
            cleaned = cleaned[:idx].rstrip()
            break

    iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?")
    cleaned = iso_pattern.sub(lambda match: _format_datetime_for_user(match.group(0)), cleaned)
    return cleaned.strip()


def _looks_like_user_ready_approval_text(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    return any(token in normalized for token in ["נ“…", "נ“§", "נ“", "גן¸", "[[BUTTONS:"])


def _extract_translation_block_safe(ai_text: str) -> str:
    text = (ai_text or "").strip()
    if not text:
        return ""

    match = re.search(
        r"(?:\*+)?\u05ea\u05e8\u05d2\u05d5\u05dd \u05dc\u05e2\u05d1\u05e8\u05d9\u05ea(?:\*+)?:?\s*(.+?)(?:\n\s*\n|$)",
        text,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return ""


def _strip_internal_approval_sections_safe(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    raw_approval_block = re.search(
        r"\n{2,}(?:\U0001F4C5|\U0001F4E7).+?(?:\n(?:Title|Start|End|Attendees|Location|"
        r"\u05db\u05d5\u05ea\u05e8\u05ea|\u05d4\u05ea\u05d7\u05dc\u05d4|"
        r"\u05e1\u05d9\u05d5\u05dd|\u05de\u05d5\u05d6\u05de\u05e0\u05d9\u05dd|"
        r"\u05de\u05d9\u05e7\u05d5\u05dd):.*){2,}[\s\S]*$",
        cleaned,
    )
    if raw_approval_block:
        cleaned = cleaned[: raw_approval_block.start()].rstrip()

    iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?")
    cleaned = iso_pattern.sub(lambda match: _format_datetime_for_user(match.group(0)), cleaned)
    return cleaned.strip()


def _looks_like_user_ready_approval_text_safe(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    return any(token in normalized for token in ["\U0001F4C5", "\U0001F4E7", "\U0001F4CC", "\u270D\uFE0F", "[[BUTTONS:"])


def _looks_like_residual_action_card(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    card_tokens = [
        "[[BUTTONS:",
        "הצעה לפעולה",
        "טיוטת מענה",
        "מועד מבוקש",
    ]
    return any(token in normalized for token in card_tokens)


def _extract_meeting_explanation(ai_text: str) -> str:
    cleaned = _strip_internal_approval_sections_safe(ai_text)
    if not cleaned:
        return ""

    explanation_lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[[BUTTONS:"):
            continue
        if any(
            token in line
            for token in [
                "טיוטת מענה",
                "תרגום לעברית",
                "הצעה לפעולה",
                "מועד מבוקש",
                "שולח:",
                "מאת:",
                "📅",
                "📧",
                "✍️",
                "📌",
                "👤",
                "⏰",
                "📆",
                "💡",
            ]
        ):
            continue
        explanation_lines.append(line)

    if not explanation_lines:
        return ""
    return "\n".join(explanation_lines[:3])


def _extract_summary_from_recent_ai_messages(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        text = _strip_internal_approval_sections_safe(extract_text(msg.content))
        if not text:
            continue
        match = re.search(r"^📌\s*(.+)$", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


def _looks_broken_summary(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return True
    return normalized.count("?") >= 6 or normalized.count("�") >= 2


def _render_meeting_approval_card(
    *,
    email_context: dict[str, str],
    meeting_title: str,
    when_label: str,
    meeting_summary: str,
    agenda_start_time: str | None,
    draft_text: str = "",
    draft_language: str = "",
    translation_block: str = "",
    action_suggestion: str,
    explanation_text: str = "",
) -> str:
    compact_lines = [
        f"📅 {meeting_title}",
        f"👤 שולח: {_format_sender_for_card(email_context.get('sender', ''))}",
    ]
    if when_label and when_label != "לא צוין":
        compact_lines.append(f"⏰ מועד מבוקש: {when_label}")
    compact_lines.extend(
        [
            f"📌 {meeting_summary}",
        ]
    )
    if explanation_text:
        compact_lines.extend(["", explanation_text])
    if draft_text:
        compact_lines.extend(
            [
                "",
                f"✍️ טיוטת מענה ({draft_language or _detect_draft_language(draft_text)}):",
                draft_text,
            ]
        )
        if (draft_language or _detect_draft_language(draft_text)) != "עברית":
            compact_lines.extend(
                [
                    "",
                    "תרגום לעברית:",
                    translation_block or "התרגום לעברית לא סופק אוטומטית בטיוטה הזו עדיין.",
                ]
            )
    compact_lines.extend(["", f"💡 הצעה לפעולה: {action_suggestion}"])
    agenda_block = _render_daily_agenda_for_card(agenda_start_time)
    if agenda_block:
        compact_lines.extend(["", agenda_block])
    return "\n".join(compact_lines)


def _extract_success_message_from_state(messages: list[BaseMessage]) -> str | None:
    last_sensitive_ai: AIMessage | None = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            if any(tc.get("name") in {"create_event", "update_event_time", "delete_event", "send_email", "trash_email"} for tc in msg.tool_calls):
                last_sensitive_ai = msg
                break

    if last_sensitive_ai is None:
        return None

    successful_tool_messages: list[ToolMessage] = []
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            content = extract_text(msg.content)
            if "successfully" in content.lower() or "created" in content.lower() or "sent" in content.lower():
                successful_tool_messages.append(msg)
            elif successful_tool_messages:
                break

    tool_args = {
        tc.get("name"): tc.get("args", {})
        for tc in getattr(last_sensitive_ai, "tool_calls", [])
        if tc.get("name")
    }

    successful_tool_names = {msg.name for msg in successful_tool_messages if getattr(msg, "name", None)}

    if "create_event" in successful_tool_names and "send_email" in successful_tool_names:
        args = tool_args.get("create_event", {})
        start_label = _format_datetime_for_user(args.get("start_time"))
        return "\n".join(
            [
                "✅ המייל נשלח והפגישה נוספה ליומן.",
                f"📅 {start_label}",
            ]
        )

    if "create_draft" in successful_tool_names and "send_email" in successful_tool_names:
        return "✅ הטיוטה אושרה והמייל נשלח בהצלחה."

    if "create_event" in successful_tool_names and "create_draft" in successful_tool_names:
        args = tool_args.get("create_event", {})
        start_label = _format_datetime_for_user(args.get("start_time"))
        return "\n".join(
            [
                "✅ נוצרה טיוטה והמועד נוסף ליומן.",
                f"📅 {start_label}",
            ]
        )

    if "create_draft" in successful_tool_names:
        return "✅ הטיוטה נוצרה בהצלחה."

    if "create_event" in tool_args:
        args = tool_args["create_event"]
        start_label = _format_datetime_for_user(args.get("start_time"))
        return "\n".join(
            [
                "✅ הפגישה נקבעה בהצלחה!",
                f"📅 תאריך: {start_label.split(' בשעה ')[0] if ' בשעה ' in start_label else start_label}",
                f"⏰ שעה: {start_label.split(' בשעה ')[1] if ' בשעה ' in start_label else 'לא צוין'}",
            ]
        )

    if "update_event_time" in tool_args:
        args = tool_args["update_event_time"]
        start_label = _format_datetime_for_user(args.get("new_start_time"))
        return "\n".join(
            [
                "✅ הפגישה עודכנה בהצלחה!",
                f"📅 תאריך: {start_label.split(' בשעה ')[0] if ' בשעה ' in start_label else start_label}",
                f"⏰ שעה: {start_label.split(' בשעה ')[1] if ' בשעה ' in start_label else 'לא צוין'}",
            ]
        )

    if "send_email" in tool_args:
        return "✅ המייל נשלח בהצלחה!"

    if "delete_event" in tool_args:
        return "✅ האירוע בוטל בהצלחה."

    if "trash_email" in tool_args:
        return "✅ ההודעה הועברה לאשפה."

    if successful_tool_messages:
        return "✅ הפעולה בוצעה בהצלחה."

    return None


def _context_looks_like_meeting(messages: list[BaseMessage]) -> bool:
    email_context = _extract_email_context_from_messages(messages)
    haystack = f"{email_context.get('subject', '')} {email_context.get('content', '')}"
    async_task_patterns = [
        r"one-way",
        r"assessment",
        r"deadline",
        r"submit by",
        r"complete your",
        r"record your answers",
        r"take-home",
        r"קוד אימות",
        r"דדליין",
        r"עד ל",
        r"להשלים עד",
        r"משימה",
    ]
    if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in async_task_patterns):
        return False

    meeting_patterns = [
        r"meeting",
        r"appointment",
        r"calendar invite",
        r"reschedul",
        r"availability",
        r"zoom",
        r"google meet",
        r"teams",
        r"phone call",
        r"\bcall\b",
        r"sync",
        r"let'?s meet",
        r"book a time",
        r"פגישה",
        r"זום",
        r"סינק",
        r"יומן",
        r"להיפגש",
        r"לתאם",
        r"ראיון בזום",
        r"ראיון טלפוני",
    ]
    if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in meeting_patterns):
        return True

    scheduling_patterns = [
        r"לקבוע .*שיחה",
        r"לקבוע .*פגישה",
        r"לתאם .*שיחה",
        r"לתאם .*פגישה",
        r"שיחה (טלפונית|קצרה|ביום|מחר|בשעה|בין)",
        r"מתי נוח",
        r"זמין(?:ה|ים)?",
        r"חלון זמן",
    ]
    return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in scheduling_patterns)


def _context_looks_like_deadline_task(messages: list[BaseMessage]) -> bool:
    email_context = _extract_email_context_from_messages(messages)
    haystack = f"{email_context.get('subject', '')} {email_context.get('content', '')}"
    deadline_patterns = [
        r"deadline",
        r"due by",
        r"submit by",
        r"complete by",
        r"one-way video interview",
        r"assessment",
        r"record your answers",
        r"view invite",
        r"document",
        r"invoice",
        r"receipt",
        r"דדליין",
        r"עד ל",
        r"להגיש עד",
        r"להשלים עד",
        r"מסמך",
        r"קבלה",
        r"חשבונית",
    ]
    return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in deadline_patterns)


def _context_looks_like_reply_request(messages: list[BaseMessage]) -> bool:
    email_context = _extract_email_context_from_messages(messages)
    haystack = f"{email_context.get('subject', '')} {email_context.get('content', '')}"
    no_reply_patterns = [
        r"no reply needed",
        r"for your information only",
        r"\bfyi\b",
        r"אין צורך (?:ב)?תשובה",
        r"אין צורך (?:ב)?מענה",
        r"לא צריך לענות",
        r"לעיונך בלבד",
        r"לעדכונך בלבד",
    ]
    if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in no_reply_patterns):
        return False

    reply_patterns = [
        r"reply",
        r"respond",
        r"response",
        r"write back",
        r"draft a reply",
        r"תשובה",
        r"מענה",
        r"להשיב",
        r"לענות",
        r"להגיב",
        r"מבקש(?:ת)? תשובה",
        r"נדרשת תשובה",
        r"נדרש מענה",
    ]
    return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in reply_patterns)


def _create_event_is_unsolicited_for_context(tool_calls: list[dict], messages: list[BaseMessage]) -> bool:
    tool_names = {tc.get("name") for tc in tool_calls if tc.get("name")}
    if "create_event" not in tool_names:
        return False
    if _context_looks_like_meeting(messages):
        return False
    return _context_looks_like_deadline_task(messages)


def _build_actionable_email_correction(messages: list[BaseMessage]) -> str | None:
    if _context_looks_like_meeting(messages):
        return (
            "This email is clearly a real scheduling or meeting request. "
            "Do NOT conclude that no action is needed. "
            "Use safe tools if useful, then build exactly one concise HITL approval card with the meeting context "
            "and any proposed reply. Wait for approval."
        )

    if _context_looks_like_reply_request(messages):
        return (
            "This email clearly requires a reply. "
            "Do NOT conclude that no action is needed. "
            "Draft a concise reply in the sender's language, keep the explanation in Hebrew, and wait for approval."
        )

    if _context_looks_like_deadline_task(messages):
        return (
            "This email contains a concrete task or deadline. "
            "Do NOT conclude that no action is needed. "
            "Summarize the task briefly and, if useful, draft a concise reply or recommendation that waits for approval."
        )

    return None


def _last_pending_ai_with_tools(messages: list[BaseMessage]) -> AIMessage | None:
    return next(
        (m for m in reversed(messages) if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)),
        None,
    )


def _last_unresolved_ai_with_tools(messages: list[BaseMessage]) -> AIMessage | None:
    for index in range(len(messages) - 1, -1, -1):
        msg = messages[index]
        if not isinstance(msg, AIMessage) or not getattr(msg, "tool_calls", None):
            continue

        unresolved_tool_call_ids = {
            tc.get("id")
            for tc in msg.tool_calls
            if tc.get("id")
        }
        if not unresolved_tool_call_ids:
            continue

        for followup in messages[index + 1 :]:
            if not isinstance(followup, ToolMessage):
                continue
            tool_call_id = getattr(followup, "tool_call_id", None)
            if tool_call_id in unresolved_tool_call_ids:
                unresolved_tool_call_ids.discard(tool_call_id)
            if not unresolved_tool_call_ids:
                break

        if unresolved_tool_call_ids:
            return msg

    return None


def _render_pending_approval(
    tool_calls: list[dict],
    messages: list[BaseMessage],
    ai_text: str = "",
) -> str:
    cleaned_ai_text = _strip_internal_approval_sections_safe(ai_text)

    email_context = _extract_email_context_from_messages(messages)
    sender_name = _display_name_from_sender(email_context.get("sender", ""))
    subject = email_context.get("subject", "")
    content_summary = _build_email_context_summary(
        subject=subject,
        body=email_context.get("content", ""),
        ai_summary=_extract_summary_from_recent_ai_messages(messages),
        limit=72,
    )
    if _looks_broken_summary(content_summary):
        content_summary = _compress_summary_phrase(subject, limit=72, max_words=8)
    translation_block = _extract_translation_block_safe(cleaned_ai_text)

    send_email_call = next((tc for tc in tool_calls if tc.get("name") == "send_email"), None)
    create_draft_call = next((tc for tc in tool_calls if tc.get("name") == "create_draft"), None)
    create_event_call = next((tc for tc in tool_calls if tc.get("name") == "create_event"), None)
    update_event_call = next((tc for tc in tool_calls if tc.get("name") == "update_event_time"), None)
    delete_event_call = next((tc for tc in tool_calls if tc.get("name") == "delete_event"), None)
    draft_call = send_email_call or create_draft_call

    if draft_call:
        args = draft_call.get("args", {})
        draft_text = (args.get("body") or "").strip() or "לא סופקה טיוטה."
        draft_language = _detect_draft_language(draft_text)
        meeting_like = bool(create_event_call or _context_looks_like_meeting(messages))

        if meeting_like:
            meeting_title = (
                normalize_event_summary((create_event_call or {}).get("args", {}).get("summary", ""))
                or subject
                or "פגישה מוצעת"
            )
            meeting_summary = _meeting_summary_line(content_summary, meeting_title)
            when_label = _format_datetime_for_user(
                (create_event_call or {}).get("args", {}).get("start_time")
            )
            if when_label == "לא צוין":
                when_label = email_context.get("when_hint") or "לא צוין"
            action_suggestion = "לאשר יצירת אירוע ביומן"
            if create_event_call and draft_call:
                action_suggestion = "לאשר יצירת אירוע ביומן ואת הטיוטה המוצעת"
            elif draft_call:
                action_suggestion = "לאשר את הטיוטה ולשלוח תשובה"
            return _render_meeting_approval_card(
                email_context=email_context,
                meeting_title=meeting_title,
                when_label=when_label,
                meeting_summary=meeting_summary,
                agenda_start_time=(create_event_call or {}).get("args", {}).get("start_time"),
                draft_text=draft_text,
                draft_language=draft_language,
                translation_block=translation_block,
                action_suggestion=action_suggestion,
                explanation_text=_extract_meeting_explanation(cleaned_ai_text),
            )

        timing = email_context.get("when_hint")
        title = "דחיית בקשה" if re.search(r"(tomorrow|urgent|מחר|דחוף)", f"{subject} {content_summary}", re.IGNORECASE) else "טיוטת מענה"
        lines = [f"📧 {title}"]
        lines.append(f"👤 שולח: {_format_sender_for_card(email_context.get('sender', ''))}")
        if timing:
            lines.append(f"⏰ מועד: {timing}")
        attachment_line = _attachment_summary_line(email_context)
        if attachment_line:
            lines.append(attachment_line)
        if not _reply_possible_from_context(email_context):
            lines.append("ℹ️ אי אפשר להשיב ישירות לכתובת הזו במייל.")
        lines.extend(
            [
                f"📌 {content_summary or subject or 'בקשה כללית לעדכון או תגובה.'}",
                "",
                f"✍️ טיוטת מענה ({draft_language}):",
                draft_text,
            ]
        )
        if draft_language != "עברית":
            lines.extend(
                [
                    "",
                    "תרגום לעברית:",
                    translation_block or "התרגום לעברית לא סופק אוטומטית בטיוטה הזו עדיין.",
                ]
            )
        lines.extend(
            [
                "",
                "💡 הצעה לפעולה: לאשר את הטיוטה ולשלוח, לדחות בנימוס, או לתת לי הכוונה מדויקת יותר.",
            ]
        )
        return "\n".join(lines)

    if create_event_call:
        args = create_event_call.get("args", {})
        meeting_title = normalize_event_summary(args.get("summary", "אירוע חדש"))
        meeting_summary = _meeting_summary_line(content_summary, meeting_title)
        when_label = _format_datetime_for_user(args.get("start_time"))
        return _render_meeting_approval_card(
            email_context=email_context,
            meeting_title=meeting_title,
            when_label=when_label,
            meeting_summary=meeting_summary,
            agenda_start_time=args.get("start_time"),
            action_suggestion="לאשר יצירת אירוע ביומן",
            explanation_text=_extract_meeting_explanation(cleaned_ai_text) or "זיהיתי שמדובר בבקשת פגישה ולכן הכנתי אירוע ביומן עם הפרטים שמצאתי.",
        )

    if update_event_call:
        args = update_event_call.get("args", {})
        return "\n".join(
            [
                "🔄 עדכון אירוע",
                f"👤 שולח: {_format_sender_for_card(email_context.get('sender', ''))}",
                f"⏰ מועד חדש: {_format_datetime_for_user(args.get('new_start_time'))}",
                "",
                "💡 הצעה לפעולה: לאשר את שינוי המועד.",
            ]
        )

    if delete_event_call:
        args = delete_event_call.get("args", {})
        return "\n".join(
            [
                "🗑️ ביטול אירוע",
                f"📌 {content_summary or 'המערכת הכינה ביטול אירוע לאישורך.'}",
                "",
                "💡 הצעה לפעולה: לאשר את ביטול האירוע.",
            ]
        )

    return "⏳ ממתין לאישורך לביצוע הפעולה."

def _extract_header_value(text: str, header_name: str) -> str:
    pattern = rf"^{re.escape(header_name)}:\s*(.+)$"
    match = re.search(pattern, text or "", re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_action_payload_from_tool_calls(tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    names = [str(tc.get("name")) for tc in tool_calls if tc.get("name")]
    details: dict[str, Any] = {
        "tool_names": names,
        "approval_type": names[0] if len(names) == 1 else ("multi_step" if names else ""),
    }

    draft_call = next((tc for tc in tool_calls if tc.get("name") in {"send_email", "create_draft"}), None)
    if draft_call:
        args = draft_call.get("args", {}) or {}
        draft_body = str(args.get("body") or "").strip()
        details.update(
            {
                "draft_to": args.get("to_email"),
                "draft_subject": args.get("subject"),
                "draft_preview": _compact_text(draft_body, limit=220) if draft_body else "",
                "draft_text": draft_body,
            }
        )

    event_call = next((tc for tc in tool_calls if tc.get("name") in {"create_event", "update_event_time"}), None)
    if event_call:
        args = event_call.get("args", {}) or {}
        details.update(
            {
                "event_title": args.get("summary"),
                "event_start": args.get("start_time") or args.get("new_start_time"),
                "event_end": args.get("end_time") or args.get("new_end_time"),
                "event_location": args.get("location"),
            }
        )

    return {
        key: value
        for key, value in details.items()
        if value is not None and value != "" and value != []
    }



def _extract_summary_line(text: str) -> str:
    """Extracts the '📌 סיכום:' line from LLM output, or falls back to first sentence."""
    if not text:
        return ""
    lines = text.split('\n')
    for line in lines:
        if '📌' in line or 'סיכום:' in line:
            clean = line.replace('📌', '').replace('סיכום:', '').strip()
            if clean:
                return clean[:150]
    for line in lines:
        line = line.strip()
        if len(line) > 10 and not line.startswith(('👤', '⏰', '[[', '📅', '✅', '❌')):
            return line[:150]
    return text[:150]


def _build_incoming_email_action_params(
    *,
    payload: "RequestModel",
    enriched_text: str,
    response_preview: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    error: str = "",
) -> dict[str, Any]:
    sender = _extract_header_value(enriched_text, "From") or _extract_header_value(payload.text, "From")
    subject = _extract_header_value(enriched_text, "Subject") or _extract_header_value(payload.text, "Subject")
    body = _extract_header_value(enriched_text, "Content") or enriched_text or payload.text
    summary = _build_email_context_summary(
        subject=subject,
        body=body or payload.text,
        limit=72,
    )

    if _looks_broken_text(subject):
        fallback_subject = _compress_summary_phrase(body, limit=72, max_words=8)
        if fallback_subject and not _looks_broken_text(fallback_subject):
            subject = fallback_subject

    if _looks_broken_text(summary):
        fallback_summary = _compress_summary_phrase(response_preview or body, limit=72, max_words=9)
        if fallback_summary and not _looks_broken_text(fallback_summary):
            summary = fallback_summary

    ai_summary = _extract_summary_line(response_preview)

    params: dict[str, Any] = {
        "source": payload.source,
        "email_id": payload.email_id or "",
        "sender": sender,
        "subject": subject,
        "summary": ai_summary or summary,
        "preview": response_preview.strip(),
    }
    if tool_calls:
        params.update(_extract_action_payload_from_tool_calls(tool_calls))
    if error:
        params["error"] = error.strip()
    return {
        key: value
        for key, value in params.items()
        if value is not None and value != ""
    }


def _build_response(
    *,
    answer: str,
    internal_id: str,
    is_paused: bool = False,
    status: str = "success",
) -> dict:
    return {
        "status": status,
        "answer": answer,
        "internal_id": internal_id,
        "is_paused": is_paused,
    }

# --- 2. המוח המרכזי באמצעות LangGraph ---
@app.post("/ask")
def ask_brain(payload: RequestModel):
    # Normalize input: Button callbacks use underscores instead of spaces
    raw_text = payload.text.strip()
    user_id = _resolve_request_user_id(payload)
    
    # 🔑 Decode thread_id from button callback_data (format: "ACTION_TEXT::THREAD_ID")
    embedded_thread_id = None
    if "::" in raw_text:
        parts = raw_text.split("::", 1)
        action_part = parts[0].replace("_", " ")
        embedded_thread_id = parts[1].strip()
        user_text = action_part.strip()
        server_logger.info(f"🔑 Decoded button callback: action='{user_text}', thread='{embedded_thread_id}'")
    else:
        user_text = raw_text.replace("_", " ")
    
    # 🔍 Thread Resolution Priority:
    # 1. Embedded thread_id from button callback_data (most reliable)
    # 2. reply_to_message_id → MongoDB/memory mapping
    # 3. Default: user_id (new conversation)
    thread_id = user_id
    
    if embedded_thread_id:
        # Button click with embedded thread — use it directly. No lookup needed.
        thread_id = embedded_thread_id
        server_logger.info(f"🔑 Using embedded thread_id from button: {thread_id}")
        
    elif payload.thread_id:
        thread_id = payload.thread_id.strip()
        server_logger.info(f"Using explicit thread_id from payload: {thread_id}")
    elif payload.reply_to_message_id:
        mapping_found = False
        if workflow_state_store.messages is not None:
            mapping = workflow_state_store.messages.find_one({"telegram_id": str(payload.reply_to_message_id)})
            if mapping:
                thread_id = mapping.get("action_id", user_id)
                mapping_found = True
                server_logger.info(f"🔗 Context Match: Found action_id {thread_id} for Telegram message {payload.reply_to_message_id}")
        else:
             thread_id_fallback = workflow_state_store._memory_messages.get(str(payload.reply_to_message_id))
             if thread_id_fallback:
                 thread_id = thread_id_fallback
                 mapping_found = True
                 server_logger.info(f"🔗 Context Match (Memory): Found thread {thread_id} for Telegram message {payload.reply_to_message_id}")
        
        if not mapping_found:
             server_logger.warning(f"⚠️ Context Lost: Could not find mapping for Telegram message {payload.reply_to_message_id}. Using default thread {user_id}")
             msg = "⚠️ שגיאה מערכתית: לא מצאתי את ההקשר של ההודעה אליה הגבת (ייתכן שהשרת הופעל מחדש). אנא כתוב מחדש מה תרצה לעשות."
             return _build_response(answer=msg, internal_id=user_id, is_paused=False)
             
    server_logger.info(f"❓ User ({user_id}) asks: {user_text} [Thread: {thread_id}]")
    
    config = {"configurable": {"thread_id": thread_id}}

    if not graph:
        msg = "❌ מערכת הגרף אינה זמינה (שגיאת התחברות למונגו)."
        return _build_response(answer=msg, internal_id=thread_id, is_paused=False, status="error")

    # בדיקה האם המשתמש מספק כתובת אימייל ישירה (שמירת איש קשר)
    if "@" in user_text and " " not in user_text.strip():
        # Heuristic - if it's just an email, let's save it to workflow_state_store contacts for good measure.
        # But we also just pass it to the Graph to handle.
        pass

    # נבדוק את הסטייט הנוכחי של הגרף
    state = graph.get_state(config)
    
    # 🌟 מנגנון Human-in-the-Loop 🌟 
    # אם אנחנו ממתינים לאישור ממש לפני כלים רגישים
    if state.next and "sensitive_tools" in state.next:
        server_logger.info("💡 Graph is paused before sensitive execution.")
        
        last_msg = state.values["messages"][-1]
        tool_calls = last_msg.tool_calls if hasattr(last_msg, "tool_calls") else []
        
        if not tool_calls:
             pass
        else:
            if is_manual_override(user_text):
                server_logger.info("📝 User chose manual guidance mode.")
                msg = "👍 הבנתי. כתוב לי עכשיו איך לנסח, מה הטון שאתה רוצה, או איך בדיוק לפעול, ואני אעדכן את הטיוטה בלי לבצע עדיין."
                msg = "כתוב לי בהודעה הבאה איך לנסח, מה הטון שאתה רוצה, או איך בדיוק לפעול, ואני אעדכן את הטיוטה בלי לבצע עדיין."
                return _build_response(answer=msg, internal_id=thread_id, is_paused=False)

            if is_polite_decline_request(user_text):
                server_logger.info("User requested a polite decline rewrite.")
                messages_to_add = []
                for tc in tool_calls:
                    messages_to_add.append(ToolMessage(
                        tool_call_id=tc['id'],
                        content="User chose a polite decline. Do NOT execute this call. Draft a polite decline in the original sender language, keep explanations in Hebrew, and wait for approval again.",
                        name=tc['name'],
                        status="error"
                    ))
                graph.update_state(config, {"messages": messages_to_add})
                user_text = "נסח דחייה מנומסת בשפת המקור של הפונה, שמור את ההסבר והממשק בעברית, ואל תבצע עדיין."

            if is_approval(user_text):
                server_logger.info("🚀 User Approved! Resuming graph execution...")
                approval_targets_draft = any(
                    tc.get("name") in {"create_draft", "send_email"} for tc in tool_calls
                )
                approval_requests_send = is_send_style_approval(user_text) or approval_targets_draft
                approval_context_is_meeting = _context_looks_like_meeting(state.values.get("messages", []))
                # הזרמת None תשחרר את הברקס ותריץ את הכלים
                _graph_invoke_as_user(user_id, None, config)
                post_state = graph.get_state(config)
                auto_resume_budget = 3
                while auto_resume_budget > 0:
                    post_messages = post_state.values.get("messages", [])
                    pending_ai = _last_unresolved_ai_with_tools(post_messages)
                    pending_tool_calls = list(getattr(pending_ai, "tool_calls", []) or [])
                    pending_tool_names = {tc.get("name") for tc in pending_tool_calls if tc.get("name")}
                    has_pending_sensitive_step = bool(
                        pending_tool_names.intersection(
                            {"create_draft", "create_event", "update_event_time", "delete_event", "send_email", "trash_email"}
                        )
                    ) or bool(post_state.next and any("sensitive" in step for step in post_state.next))
                    if not has_pending_sensitive_step:
                        break

                    pending_tool_calls = list(getattr(pending_ai, "tool_calls", []) or [])
                    should_block_unsolicited_reminder = (
                        approval_requests_send
                        and not approval_context_is_meeting
                        and pending_tool_names == {"create_event"}
                    )
                    if should_block_unsolicited_reminder:
                        server_logger.info(
                            "Blocking unsolicited calendar event in approved draft flow; steering graph to send email only."
                        )
                        graph.update_state(
                            config,
                            {
                                "messages": [
                                    ToolMessage(
                                        tool_call_id=tc["id"],
                                        content=(
                                            "User approved the draft for sending. Do NOT create a calendar event, "
                                            "reminder, or follow-up task here unless the user explicitly asked for it. "
                                            "Send the approved email now and then stop."
                                        ),
                                        name=tc["name"],
                                        status="error",
                                    )
                                    for tc in pending_tool_calls
                                ]
                            },
                        )
                        _graph_invoke_as_user(user_id, None, config)
                        post_state = graph.get_state(config)
                        auto_resume_budget -= 1
                        continue
                    server_logger.info("🔁 Continuing approved flow through an additional sensitive step.")
                    _graph_invoke_as_user(user_id, None, config)
                    post_state = graph.get_state(config)
                    auto_resume_budget -= 1
                post_messages = post_state.values.get("messages", [])
                post_is_paused = bool(post_state.next and any("sensitive" in step for step in post_state.next))
                successful_tool_names = {
                    getattr(msg, "name", None)
                    for msg in post_messages
                    if isinstance(msg, ToolMessage)
                    and (
                        "successfully" in extract_text(msg.content).lower()
                        or "created" in extract_text(msg.content).lower()
                        or "sent" in extract_text(msg.content).lower()
                    )
                    and getattr(msg, "name", None)
                }

                if approval_requests_send and "create_draft" in successful_tool_names and "send_email" not in successful_tool_names:
                    last_draft_ai = next(
                        (
                            m for m in reversed(post_messages)
                            if isinstance(m, AIMessage)
                            and any(tc.get("name") == "create_draft" for tc in getattr(m, "tool_calls", []) or [])
                        ),
                        None,
                    )
                    if last_draft_ai is not None:
                        draft_call = next(
                            (tc for tc in getattr(last_draft_ai, "tool_calls", []) if tc.get("name") == "create_draft"),
                            None,
                        )
                        draft_args = (draft_call or {}).get("args", {})
                        if draft_args.get("to_email") and draft_args.get("subject") and draft_args.get("body"):
                            sent_id = _gmail_send_email_as_user(
                                user_id,
                                draft_args["to_email"],
                                draft_args["subject"],
                                draft_args["body"],
                                thread_id=draft_args.get("thread_id"),
                            )
                            if sent_id:
                                server_logger.info("Sent approved draft immediately after create_draft fallback.")
                                successful_tool_names.add("send_email")
                                post_is_paused = False

                final_answer = ""
                for msg in reversed(post_messages):
                    if not isinstance(msg, AIMessage):
                        continue
                    content_text = extract_text(msg.content)
                    if content_text.strip():
                        final_answer = content_text
                        break
                if _looks_like_residual_action_card(final_answer):
                    success_override = _extract_success_message_from_state(post_messages)
                    if success_override:
                        final_answer = success_override
                if approval_requests_send and "create_draft" in successful_tool_names and "send_email" in successful_tool_names:
                    final_answer = "✅ הטיוטה אושרה והמייל נשלח בהצלחה."
                elif approval_requests_send and "create_event" in successful_tool_names and "send_email" in successful_tool_names:
                    create_event_ai = next(
                        (
                            m for m in reversed(post_messages)
                            if isinstance(m, AIMessage)
                            and any(tc.get("name") == "create_event" for tc in getattr(m, "tool_calls", []) or [])
                        ),
                        None,
                    )
                    create_event_call = next(
                        (tc for tc in getattr(create_event_ai, "tool_calls", []) if tc.get("name") == "create_event"),
                        None,
                    ) if create_event_ai else None
                    start_label = _format_datetime_for_user(((create_event_call or {}).get("args") or {}).get("start_time"))
                    final_answer = "\n".join(
                        [
                            "✅ המייל נשלח והפגישה נוספה ליומן.",
                            f"📅 {start_label}",
                        ]
                    ) if start_label != "לא צוין" else "✅ המייל נשלח והפגישה נוספה ליומן."
                elif post_is_paused:
                    pending_ai = next(
                        (m for m in reversed(post_messages) if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)),
                        None,
                    )
                    if pending_ai:
                        final_answer = _render_pending_approval(pending_ai.tool_calls, post_messages, final_answer)

                msg = (final_answer if final_answer else "✅ הפעולה בוצעה בהצלחה.").strip()
                if not post_is_paused:
                    _log_post_execution_time_saved(
                        user_id=user_id,
                        thread_id=thread_id,
                        successful_tool_names=successful_tool_names,
                        metadata={"tools": sorted(successful_tool_names)},
                    )

                return _build_response(
                    answer=msg,
                    internal_id=thread_id,
                    is_paused=post_is_paused,
                )
            
            elif is_rejection(user_text):
                server_logger.warning("⛔ User Rejected. Canceling execution...")
                # נשלח הודעת כלי (ToolMessage) שתודיע על ביטול לכל הכלים הממתינים
                messages_to_add = []
                for tc in tool_calls:
                     messages_to_add.append(ToolMessage(
                         tool_call_id=tc['id'], 
                         content="המשתמש ביטל את הפעולה הזו. אל תבצע אותה.", 
                         name=tc['name'], 
                         status="error"
                     ))
                events = _graph_stream_as_user(user_id, {"messages": messages_to_add}, config, stream_mode="values")
                for event in events: pass # run to completion
                msg = "❌ הפעולה בוטלה."
                return _build_response(answer=msg, internal_id=thread_id, is_paused=False)
            
            else:
                server_logger.info(f"🔄 User provided feedback/changes on the draft: '{user_text}'")
                # נודיע למודל על הערת המשתמש ועל ביטול הפעולה הקודמת
                messages_to_add = []
                for tc in tool_calls:
                     messages_to_add.append(ToolMessage(
                         tool_call_id=tc['id'], 
                         content=(
                             f"User feedback/change requested on this draft: {user_text}. "
                             "Do NOT execute this call. Provide an updated draft only. "
                             "Do NOT send anything and do NOT create calendar events/reminders. Wait for approval again."
                         ), 
                         name=tc['name'], 
                         status="error"
                     ))
                
                # עדכון הסטייט בגרף (הצגת "כישלון" לשיחות הקודמות)
                graph.update_state(config, {"messages": messages_to_add})
                # כעת ה-flow ימשיך למטה וישלח את ה-user_text כהודעה חדשה לגרף
        
    
    # --- הפעלת הגרף כברירת מחדל עם הבקשה ---
    approval_from_existing_context = bool(is_approval(user_text) and (embedded_thread_id or payload.reply_to_message_id))
    user_input_msg = HumanMessage(content=user_text)
    
    events = _graph_stream_as_user(user_id, {"messages": [user_input_msg], "user_id": user_id}, config, stream_mode="values")
    
    final_output = ""
    for event in events:
        if "messages" in event:
             last_msg = event["messages"][-1]
             final_output = extract_text(last_msg.content)
                  
    # First strip, THEN extract buttons (critical for regex $ anchor)
    final_output = final_output.strip()
    
    # --- HITL Detection after Stream ---
    # check if the graph paused for approval/sensitive tools
    new_state = graph.get_state(config)
    is_paused = new_state.next and any("sensitive" in n for n in new_state.next)

    unresolved_post_approval = _last_unresolved_ai_with_tools(new_state.values.get("messages", []))
    has_unresolved_sensitive_after_explicit_approval = bool(
        approval_from_existing_context
        and unresolved_post_approval
        and any(
            tc.get("name") in {"create_draft", "create_event", "update_event_time", "delete_event", "send_email", "trash_email"}
            for tc in getattr(unresolved_post_approval, "tool_calls", [])
        )
    )

    if approval_from_existing_context and (is_paused or has_unresolved_sensitive_after_explicit_approval):
        server_logger.info("Auto-resuming newly paused action from explicit approval input.")
        final_output = ""
        auto_resume_budget = 3
        while auto_resume_budget > 0:
            for event in _graph_stream_as_user(user_id, None, config, stream_mode="values"):
                if "messages" in event:
                    last_msg = event["messages"][-1]
                    content_text = extract_text(last_msg.content)
                    if content_text.strip():
                        final_output = content_text

            new_state = graph.get_state(config)
            is_paused = new_state.next and any("sensitive" in n for n in new_state.next)
            unresolved_post_approval = _last_unresolved_ai_with_tools(new_state.values.get("messages", []))
            if not (
                is_paused
                or (
                    unresolved_post_approval
                    and any(
                        tc.get("name") in {"create_draft", "create_event", "update_event_time", "delete_event", "send_email", "trash_email"}
                        for tc in getattr(unresolved_post_approval, "tool_calls", [])
                    )
                )
            ):
                break
            auto_resume_budget -= 1

    if is_paused:
        msgs = new_state.values.get("messages", [])
        last_ai_with_content = next(
            (m for m in reversed(msgs) if isinstance(m, AIMessage) and extract_text(m.content).strip()),
            None,
        )
        last_ai_with_tools = next(
            (m for m in reversed(msgs) if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)),
            None,
        )
        if last_ai_with_tools and last_ai_with_tools.tool_calls:
            final_output = _render_pending_approval(
                last_ai_with_tools.tool_calls,
                msgs,
                extract_text(last_ai_with_content.content) if last_ai_with_content else final_output,
            )
        elif last_ai_with_content and not final_output:
            final_output = _strip_internal_approval_sections_safe(extract_text(last_ai_with_content.content))
    
    if is_paused and not final_output:
        # Graph paused for HITL — extract the pending tool call args and show them nicely
        msgs = new_state.values.get("messages", [])
        last_ai_with_content = next(
            (m for m in reversed(msgs) if isinstance(m, AIMessage) and extract_text(m.content).strip()), None
        )
        if last_ai_with_content:
            final_output = extract_text(last_ai_with_content.content)
        else:
            last_m = msgs[-1] if msgs else None
            if hasattr(last_m, "tool_calls") and last_m.tool_calls:
                final_output = _render_pending_approval(last_m.tool_calls, msgs)
            else:
                final_output = "⏳ ממתין לאישורך לביצוע הפעולה."
            
    if not final_output.strip():
        if not is_paused:
            final_output = "✅ הודעת מערכת: הבקשה עובדה בהצלחה."
        else:
            final_output = "⏳ ממתין לאישור הפעולה..."

    response = _build_response(
        answer=final_output.strip(),
        internal_id=thread_id,
        is_paused=bool(is_paused),
    )
    server_logger.info(f"📤 ask_brain response (paused={bool(is_paused)})")
    return response


# --- 3. ניתוח אירועים (מיילים) והכנת הקרקע לאישור ---
@app.post("/analyze_email")
def analyze_incoming_event(payload: RequestModel):
    server_logger.info(f"📧 Analyzing email from source: {payload.source}")
    user_id = _resolve_request_user_id(payload)
    
    initial_action_params = _build_incoming_email_action_params(
        payload=payload,
        enriched_text=payload.text,
    )
    internal_id = workflow_state_store.save_action(
        user_id,
        "langgraph",
        "incoming_email",
        initial_action_params,
        status="processing",
    )
    
    config = {"configurable": {"thread_id": internal_id}}
    
    enriched_text = payload.text
    verified_sender = ""
    verified_subject = ""
    reply_possible = True
    sender_type = "person"
    attachment_names: list[str] = []
    has_calendar_invite = False
    if payload.email_id:
        try:
            full_email = fetch_email_by_id(payload.email_id)
            if full_email and full_email.get("body"):
                body = full_email["body"]
                # Extreme truncation for Groq free tier
                if len(body) > 3000:
                    body = body[:3000] + "... [Extreme Truncation]"
                sender = full_email.get("sender") or ""
                subject = full_email.get("subject") or ""
                verified_sender = sender
                verified_subject = subject
                reply_possible = bool(full_email.get("reply_possible", True))
                sender_type = "no-reply" if not reply_possible else "person"
                attachment_names = [item.get("filename", "").strip() for item in full_email.get("attachments", []) if item.get("filename")]
                has_calendar_invite = bool(full_email.get("has_calendar_invite"))
                metadata_lines = []
                if sender:
                    metadata_lines.append(f"From: {sender}")
                if subject:
                    metadata_lines.append(f"Subject: {subject}")
                metadata_lines.append(f"Reply-Possible: {'yes' if reply_possible else 'no'}")
                metadata_lines.append(f"Sender-Type: {sender_type}")
                metadata_lines.append(f"Attachments-Verified: {'yes' if attachment_names else 'no'}")
                metadata_lines.append(f"Attachment-Names: {', '.join(attachment_names) if attachment_names else 'None'}")
                metadata_lines.append(f"Has-Calendar-Invite: {'yes' if has_calendar_invite else 'no'}")
                metadata_lines.append(f"Content: {body}")
                enriched_text = "\n".join(metadata_lines)
                if has_calendar_invite:
                    enriched_text += "\n\n[📅 מייל זה מכיל הזמנת יומן]"
        except Exception as e:
            server_logger.error(f"⚠️ Email enrichment failed: {e}")
            
    # שאיבת פרטי קשר מתוך המייל ושמירה
    contact_email = payload.text.split("From: ")[-1].split("\n")[0].strip() if "From: " in payload.text else ""
    if contact_email and "@" in contact_email:
         try:
             email_part = re.search(r'<(.+?)>', contact_email)
             email_val = email_part.group(1) if email_part else contact_email
             name_val = contact_email.replace(f"<{email_val}>", "").strip() or email_val.split("@")[0]
             workflow_state_store.save_contact(user_id, name_val, email_val)
         except: pass

    current_action_params = _build_incoming_email_action_params(
        payload=payload,
        enriched_text=enriched_text,
    )
    workflow_state_store.update_action(internal_id, params=current_action_params, status="processing")
         
    # הזנה לגרף
    if not graph:
        msg = "❌ מערכת הגרף אינה זמינה (שגיאת התחברות למונגו)."
        workflow_state_store.update_action(
            internal_id,
            status="error",
            params=_build_incoming_email_action_params(
                payload=payload,
                enriched_text=enriched_text,
                response_preview=msg,
                error=msg,
            ),
        )
        return _build_response(answer=msg, internal_id=internal_id, is_paused=False, status="error")

    if not enriched_text or not enriched_text.strip():
        # Safeguard against the "contents are required" error
        server_logger.warning(f"⚠️ Email content is completely empty. Bypassing LangGraph. Thread: {internal_id}")
        workflow_state_store.update_action(
            internal_id,
            status="ignored",
            params=_build_incoming_email_action_params(
                payload=payload,
                enriched_text=enriched_text,
                response_preview="empty-email",
            ),
        )
        _log_time_saved_outcome(
            user_id=user_id,
            thread_id=internal_id,
            action_type="email_triage_ignore",
            metadata={"reason": "empty_email"},
        )
        return _build_response(
            answer="הודעה חסרת תוכן טקסטואלי או קריא (ייתכן שמכילה רק תמונות או קבצים שאינם נתמכים כרגע).",
            internal_id=internal_id,
            is_paused=False,
            status="ignored",
        )

    input_text = (
        f"[New Incoming Email from {payload.source}]\n"
        "First classify the email into exactly one type: MEETING, TASK, REPLY, CRITICAL, or IGNORE.\n"
        "Only then decide whether it should reach Telegram.\n"
        "Use only verified metadata for attachments, replyability, and calendar-invite detection.\n\n"
        f"Email Content:\n{enriched_text}"
    )
    user_input_msg = HumanMessage(content=input_text)

    if _looks_like_low_value_notification([user_input_msg]):
        server_logger.info(f"Skipping low-value no-reply notification (thread: {internal_id}).")
        workflow_state_store.update_action(
            internal_id,
            status="ignored",
            params=_build_incoming_email_action_params(
                payload=payload,
                enriched_text=enriched_text,
                response_preview="low-value-notification",
            ),
        )
        _log_time_saved_outcome(
            user_id=user_id,
            thread_id=internal_id,
            action_type="email_triage_ignore",
            metadata={"reason": "low_value_notification"},
        )
        return _build_response(
            answer="מייל סווג כעדכון low-value ולא נשלח לטלגרם.",
            internal_id=internal_id,
            is_paused=False,
            status="ignored",
        )
    
    final_output = ""
    last_aimsg = None
    
    # 🌟 USE LOCK TO PREVENT 429 ERRORS (Sequental processing) 🌟
    server_logger.info(f"⏳ Waiting in queue to process email (thread: {internal_id})...")
    with email_processing_lock:
        server_logger.info(f"▶️ Processing email (thread: {internal_id})...")
        events = _graph_stream_as_user(user_id, {"messages": [user_input_msg], "user_id": user_id}, config, stream_mode="values")
        
        for event in events:
            if "messages" in event:
                 msg = event["messages"][-1]
                 if isinstance(msg, AIMessage):
                      last_aimsg = msg
                      final_output = extract_text(msg.content)
                           
        # Lock will be released automatically when exiting the block
        server_logger.info(f"✅ Finished processing email (thread: {internal_id}). Lock released.")

    if last_aimsg and last_aimsg.tool_calls:
        pending_tool_names = {tc.get("name") for tc in last_aimsg.tool_calls if tc.get("name")}
        should_block_deadline_calendar = (
            "create_event" in pending_tool_names
            and _context_looks_like_deadline_task([user_input_msg])
            and not _context_looks_like_meeting([user_input_msg])
        )
        if should_block_deadline_calendar:
            server_logger.info(
                f"Blocking calendar creation for deadline-only email (thread: {internal_id})."
            )
            graph.update_state(
                config,
                {
                    "messages": [
                        ToolMessage(
                            tool_call_id=tc["id"],
                            content=(
                                "This email has a deadline or async task, not a synchronous meeting request. "
                                "Do NOT create a calendar event unless the user explicitly asks to add one. "
                                "Summarize the task briefly and, if useful, draft a response or suggest a reminder without creating an event."
                            ),
                            name=tc["name"],
                            status="error",
                        )
                        for tc in last_aimsg.tool_calls
                        if tc.get("name") == "create_event"
                    ]
                },
            )
            final_output = ""
            last_aimsg = None
            for event in _graph_stream_as_user(user_id, None, config, stream_mode="values"):
                if "messages" in event:
                    msg = event["messages"][-1]
                    if isinstance(msg, AIMessage):
                        last_aimsg = msg
                        final_output = extract_text(msg.content)

    if last_aimsg and last_aimsg.tool_calls:
        pending_tool_names = {tc.get("name") for tc in last_aimsg.tool_calls if tc.get("name")}
        should_block_unreplyable_draft = (
            pending_tool_names.intersection({"create_draft", "send_email"})
            and not _reply_possible_from_context(_extract_email_context_from_messages([user_input_msg]))
        )
        if should_block_unreplyable_draft:
            server_logger.info(
                f"Blocking draft/send for non-replyable email (thread: {internal_id})."
            )
            graph.update_state(
                config,
                {
                    "messages": [
                        ToolMessage(
                            tool_call_id=tc["id"],
                            content=(
                                "This email is not replyable via email. Do NOT create a draft and do NOT send an email. "
                                "Either ignore it or summarize it without reply actions."
                            ),
                            name=tc["name"],
                            status="error",
                        )
                        for tc in last_aimsg.tool_calls
                        if tc.get("name") in {"create_draft", "send_email"}
                    ]
                },
            )
            final_output = ""
            last_aimsg = None
            for event in _graph_stream_as_user(user_id, None, config, stream_mode="values"):
                if "messages" in event:
                    msg = event["messages"][-1]
                    if isinstance(msg, AIMessage):
                        last_aimsg = msg
                        final_output = extract_text(msg.content)

    corrective_prompt = _build_actionable_email_correction([user_input_msg])
    if (
        corrective_prompt
        and not (last_aimsg and last_aimsg.tool_calls)
        and final_output.strip() in {"", "אין פעולה נדרשת מהמייל הזה."}
    ):
        server_logger.info(
            f"Retrying actionable email that fell through as no-action (thread: {internal_id})."
        )
        final_output = ""
        last_aimsg = None
        with email_processing_lock:
            for event in _graph_stream_as_user(
                user_id,
                {"messages": [HumanMessage(content=corrective_prompt)], "user_id": user_id},
                config,
                stream_mode="values",
            ):
                if "messages" in event:
                    msg = event["messages"][-1]
                    if isinstance(msg, AIMessage):
                        last_aimsg = msg
                        final_output = extract_text(msg.content)

    # 🚫 Early exit for SPAM/TRASH
    if "[IGNORE_EMAIL]" in final_output:
        server_logger.info(f"🚮 Email classified as SPAM/TRASH. Silent mode active. Thread: {internal_id}")
        workflow_state_store.update_action(
            internal_id,
            status="ignored",
            params=_build_incoming_email_action_params(
                payload=payload,
                enriched_text=enriched_text,
                response_preview=final_output,
            ),
        )
        _log_time_saved_outcome(
            user_id=user_id,
            thread_id=internal_id,
            action_type="email_triage_ignore",
            metadata={"reason": "model_ignore"},
        )
        return _build_response(
            answer="מייל סווג כספאם או לא רלוונטי.",
            internal_id=internal_id,
            is_paused=False,
            status="ignored",
        )

    if last_aimsg and last_aimsg.tool_calls:
        final_output = _render_pending_approval(last_aimsg.tool_calls, [user_input_msg], final_output)

    # If empty content but has tool calls, generate a meaningful HITL message
    if not final_output and last_aimsg and last_aimsg.tool_calls:
        final_output = _render_pending_approval(last_aimsg.tool_calls, [user_input_msg])
    elif not final_output:
        final_output = "אין פעולה נדרשת מהמייל הזה."
    
    # Clean output for Telegram (minimizing markdown parsing errors)
    # We DO NOT strip symbols like [], *, _ anymore as they are critical for buttons and formatting.
    # We only clean very specific dangerous characters if needed.
    final_output = final_output.strip()
    
    # Final safety check: Telegram rejects empty or whitespace-only messages
    if not final_output:
        final_output = "הבקשה עובדה בהצלחה (ללא תוכן טקסטואלי נוסף)."

    new_state = graph.get_state(config)
    is_paused = bool(new_state.next and any("sensitive" in n for n in new_state.next))
    latest_error = _latest_checkpoint_error(internal_id)
    response_status = "success"
    if latest_error and not is_paused:
        response_status = "error"
    elif is_paused:
        response_status = "pending"

    action_params = _build_incoming_email_action_params(
        payload=payload,
        enriched_text=enriched_text,
        response_preview=final_output,
        tool_calls=list(getattr(last_aimsg, "tool_calls", []) or []),
        error=latest_error,
    )
    workflow_state_store.update_action(
        internal_id,
        status=response_status if response_status != "success" else "completed",
        params=action_params,
    )
    if response_status == "success" and not is_paused:
        _log_time_saved_outcome(
            user_id=user_id,
            thread_id=internal_id,
            action_type="email_triage_summary",
            metadata={"status": "completed"},
        )

    response = _build_response(
        answer=final_output,
        internal_id=internal_id,
        is_paused=is_paused,
        status=response_status,
    )

    delivered = send_via_bot(response)
    server_logger.info(f"📤 analyze_email response (paused={is_paused}, delivered={delivered})")
    if delivered:
        return {"status": "sent", "internal_id": internal_id, "is_paused": is_paused}
    return response


@app.post("/execute")
def execute_task(payload: ExecutionRequest):
    msg = "Manual execution is deprecated. LangGraph orchestrates execution natively."
    return {"status": "error", "message": msg, "answer": msg, "draft": msg}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


