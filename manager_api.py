from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import os
from dotenv import load_dotenv
load_dotenv()
import re
import asyncio
import datetime

from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver

# ייבוא הסוכנים והכלים
from agents.information_agent import KnowledgeAgent
from core.state_manager import WorkflowStateStore
from utils.calendar_tools import get_upcoming_events, get_events_for_date, normalize_event_summary
from utils.gmail_tools import fetch_email_by_id, send_email as gmail_send_email

# ייבוא הגרף החדש
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage, BaseMessage
from agents.secretariat_graph import build_secretariat_graph

from utils.logger import server_logger, memory_logger
import threading
import time

try:
    from bot.telegram_bot import TelegramNativeBot
except Exception as exc:  # pragma: no cover - only used when bot dependencies are unavailable
    TelegramNativeBot = None  # type: ignore[assignment]
    _telegram_bot_import_error = exc
else:
    _telegram_bot_import_error = None

# app = FastAPI() is defined below

app = FastAPI()

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

# --- מודלים ---
class RequestModel(BaseModel):
    text: str
    source: str = "telegram"
    user_id: str = "admin"
    email_id: Optional[str] = None 
    images: Optional[List[str]] = None
    reply_to_message_id: Optional[int] = None 
    thread_id: Optional[str] = None

class ExecutionRequest(BaseModel):
    action: str
    params: dict


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
    summary = _summarize_text((content_summary or "").strip(), limit=90)
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
        r"שיחה",
        r"סינק",
        r"יומן",
        r"להיפגש",
        r"לתאם",
        r"ראיון בזום",
        r"ראיון טלפוני",
    ]
    return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in meeting_patterns)


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


def _create_event_is_unsolicited_for_context(tool_calls: list[dict], messages: list[BaseMessage]) -> bool:
    tool_names = {tc.get("name") for tc in tool_calls if tc.get("name")}
    if "create_event" not in tool_names:
        return False
    if _context_looks_like_meeting(messages):
        return False
    return _context_looks_like_deadline_task(messages)


def _should_promote_meeting_draft_to_unified_approval(
    tool_calls: list[dict],
    messages: list[BaseMessage],
    ai_text: str,
) -> bool:
    tool_names = {tc.get("name") for tc in tool_calls if tc.get("name")}
    if not tool_names:
        return False
    if not tool_names.issubset({"create_draft", "send_email"}):
        return False
    if not _context_looks_like_meeting(messages):
        return False
    return True


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
    content_summary = _summarize_text(email_context.get("content", "") or subject)
    if _looks_broken_summary(content_summary):
        content_summary = _extract_summary_from_recent_ai_messages(messages) or _summarize_text(subject)
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
    user_id = payload.user_id 
    
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
                graph.invoke(None, config)
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
                        graph.invoke(None, config)
                        post_state = graph.get_state(config)
                        auto_resume_budget -= 1
                        continue
                    server_logger.info("🔁 Continuing approved flow through an additional sensitive step.")
                    graph.invoke(None, config)
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
                            sent_id = gmail_send_email(
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
                events = graph.stream({"messages": messages_to_add}, config, stream_mode="values")
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
    
    events = graph.stream({"messages": [user_input_msg], "user_id": user_id}, config, stream_mode="values")
    
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
            for event in graph.stream(None, config, stream_mode="values"):
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
    user_id = payload.user_id
    
    import uuid
    import time
    internal_id = workflow_state_store.save_action(user_id, "langgraph", "incoming_email", {})
    
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
         
    # הזנה לגרף
    if not graph:
        msg = "❌ מערכת הגרף אינה זמינה (שגיאת התחברות למונגו)."
        return _build_response(answer=msg, internal_id=internal_id, is_paused=False, status="error")

    if not enriched_text or not enriched_text.strip():
        # Safeguard against the "contents are required" error
        server_logger.warning(f"⚠️ Email content is completely empty. Bypassing LangGraph. Thread: {internal_id}")
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
        events = graph.stream({"messages": [user_input_msg], "user_id": user_id}, config, stream_mode="values")
        
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
            for event in graph.stream(None, config, stream_mode="values"):
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
            for event in graph.stream(None, config, stream_mode="values"):
                if "messages" in event:
                    msg = event["messages"][-1]
                    if isinstance(msg, AIMessage):
                        last_aimsg = msg
                        final_output = extract_text(msg.content)

    if last_aimsg and last_aimsg.tool_calls and _should_promote_meeting_draft_to_unified_approval(
        last_aimsg.tool_calls,
        [user_input_msg],
        final_output,
    ):
        server_logger.info(
            f"Promoting meeting draft-only pause into a unified scheduling approval card (thread: {internal_id})."
        )
        graph.update_state(
            config,
            {
                "messages": [
                    ToolMessage(
                        tool_call_id=tc["id"],
                        content=(
                            "Do not stop on a draft-only approval for this meeting email. "
                            "Build one unified approval card for the user that includes the meeting context, "
                            "any calendar conflict or alternate slot, the proposed draft reply, and the rest of the agenda for the requested day. "
                            "Pause only on that unified action card, not on an intermediate draft-only step."
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
        for event in graph.stream(None, config, stream_mode="values"):
            if "messages" in event:
                msg = event["messages"][-1]
                if isinstance(msg, AIMessage):
                    last_aimsg = msg
                    final_output = extract_text(msg.content)

    # 🚫 Early exit for SPAM/TRASH
    if "[IGNORE_EMAIL]" in final_output:
        server_logger.info(f"🚮 Email classified as SPAM/TRASH. Silent mode active. Thread: {internal_id}")
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

    response = _build_response(
        answer=final_output,
        internal_id=internal_id,
        is_paused=is_paused,
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


