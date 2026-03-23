from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

TELEGRAM_MESSAGE_LIMIT = 4096
CALLBACK_DATA_LIMIT = 64

MANUAL_OVERRIDE_BASE_TEXT = "אתן הכוונה"
MANUAL_OVERRIDE_TEXT = "✍️ אתן הכוונה"

BUTTON_TEXT_MAP = {
    "אשר וסנכרן ליומן": "📅 אשר וסנכרן ליומן",
    "אשר ושלח": "✅ אשר ושלח",
    "אשר": "✅ אשר",
    "אשר טיוטה": "✅ אשר טיוטה",
    "שלח עכשיו": "📤 שלח עכשיו",
    "ערוך טיוטה": "✏️ ערוך טיוטה",
    "בצע פעולה": "⚡ בצע פעולה",
    "בטל": "❌ בטל",
    "דחה בנימוס": "🙏 דחה בנימוס",
    "דחה למחר": "🕒 דחה למחר",
    "הזכר לי מחר": "⏰ הזכר לי מחר",
    "תזכיר לי לבדוק מחר": "⏰ תזכיר לי לבדוק מחר",
    "תייק למועד מאוחר": "🗂️ תייק למועד מאוחר",
    "תייק בארכיון": "🗂️ תייק בארכיון",
    "מחק הודעה": "🗑️ מחק הודעה",
    "אני אגיב ידנית": MANUAL_OVERRIDE_TEXT,
    MANUAL_OVERRIDE_BASE_TEXT: MANUAL_OVERRIDE_TEXT,
    "Manual": MANUAL_OVERRIDE_TEXT,
}

CALLBACK_ACTION_MAP = {
    MANUAL_OVERRIDE_BASE_TEXT: "אני אגיב ידנית",
    MANUAL_OVERRIDE_TEXT: "אני אגיב ידנית",
}

BUTTON_MARKER_RE = re.compile(r"\[\[BUTTONS:\s*([\s\S]+?)\s*\]\]", re.IGNORECASE)
DOUBLE_BOLD_SPAN_RE = re.compile(r"\*\*([^*\n]+)\*\*")
SINGLE_BOLD_SPAN_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LEADING_DECORATION_RE = re.compile(r"^[^\w\u0590-\u05FFA-Za-z0-9]+")


@dataclass(frozen=True)
class ButtonSpec:
    text: str
    callback_data: str


@dataclass(frozen=True)
class PreparedMessage:
    text: str
    buttons: list[ButtonSpec]
    parse_mode: str | None = None


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_utf8(text: str, limit: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text

    trimmed = text
    while trimmed and len(trimmed.encode("utf-8")) > limit:
        trimmed = trimmed[:-1]
    return trimmed


def truncate_for_telegram(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def build_callback_data(action: str, thread_id: str | None = None, limit: int = CALLBACK_DATA_LIMIT) -> str:
    action = normalize_whitespace(str(action)).replace(" ", "_")
    thread_id = normalize_whitespace(str(thread_id)) if thread_id else ""
    if not action:
        action = "action"

    if not thread_id:
        return truncate_utf8(action, limit)

    suffix = f"::{thread_id}"
    suffix_bytes = len(suffix.encode("utf-8"))
    if suffix_bytes >= limit:
        return truncate_utf8(suffix, limit)

    action_limit = limit - suffix_bytes
    return f"{truncate_utf8(action, action_limit)}{suffix}"


def parse_button_marker(text: str) -> tuple[str, list[str]]:
    match = BUTTON_MARKER_RE.search(text)
    if not match:
        return text, []

    raw_buttons = match.group(1).strip().strip("[]").replace("'", "").replace('"', "")
    if "|" in raw_buttons:
        buttons = [part.strip() for part in raw_buttons.split("|") if part.strip()]
    elif "," in raw_buttons:
        buttons = [part.strip() for part in raw_buttons.split(",") if part.strip()]
    else:
        buttons = [raw_buttons] if raw_buttons else []

    cleaned = BUTTON_MARKER_RE.sub("", text).strip()
    return cleaned, buttons


def _decorate_button_text(text: str) -> str:
    cleaned = normalize_whitespace(text)
    return BUTTON_TEXT_MAP.get(cleaned, cleaned)


def _callback_source_text(text: str) -> str:
    cleaned = normalize_whitespace(text)
    if cleaned in CALLBACK_ACTION_MAP:
        return CALLBACK_ACTION_MAP[cleaned]
    if cleaned in BUTTON_TEXT_MAP:
        return cleaned
    return LEADING_DECORATION_RE.sub("", cleaned).strip()


def fallback_buttons_for_text(text: str, is_paused: bool = False) -> list[str]:
    normalized = normalize_whitespace(text).lower()

    if is_paused:
        if any(token in normalized for token in ["פגישה", "ראיון", "meeting", "appointment", "יומן", "אירוע"]):
            return ["אשר וסנכרן ליומן", "דחה בנימוס", MANUAL_OVERRIDE_BASE_TEXT]
        if any(token in normalized for token in ["מייל", "email", "טיוט", "נושא", "תוכן"]):
            return ["אשר ושלח", "דחה בנימוס", MANUAL_OVERRIDE_BASE_TEXT]
        return ["אשר", "בטל", MANUAL_OVERRIDE_BASE_TEXT]

    if any(token in normalized for token in ["פגישה", "meeting", "appointment", "יומן"]):
        return ["אשר וסנכרן ליומן", "דחה בנימוס", MANUAL_OVERRIDE_BASE_TEXT]
    if any(token in normalized for token in ["טיוט", "reply", "draft", "שלח", "מייל", "email"]):
        return ["שלח עכשיו", "ערוך טיוטה", MANUAL_OVERRIDE_BASE_TEXT]
    if any(token in normalized for token in ["משימה", "task", "action", "פעולה"]):
        return ["בצע פעולה", "דחה למחר", MANUAL_OVERRIDE_BASE_TEXT]
    return ["אשר", "בטל", MANUAL_OVERRIDE_BASE_TEXT]


def _coerce_button_specs(
    buttons: Sequence[str | Mapping[str, Any]],
    thread_id: str | None = None,
    callbacks: Sequence[str] | None = None,
) -> list[ButtonSpec]:
    specs: list[ButtonSpec] = []
    callbacks = list(callbacks or [])

    for index, button in enumerate(buttons):
        if isinstance(button, Mapping):
            raw_text = normalize_whitespace(str(button.get("text", "")).strip())
            text = _decorate_button_text(raw_text)
            callback_data = str(button.get("callback_data", "")).strip()
            if not callback_data:
                callback_data = build_callback_data(_callback_source_text(raw_text), thread_id)
        else:
            raw_text = normalize_whitespace(str(button).strip())
            text = _decorate_button_text(raw_text)
            callback_data = callbacks[index].strip() if index < len(callbacks) and callbacks[index] else ""
            if not callback_data:
                callback_data = build_callback_data(_callback_source_text(raw_text), thread_id)

        if not text:
            continue

        specs.append(ButtonSpec(text=text, callback_data=truncate_utf8(callback_data, CALLBACK_DATA_LIMIT)))

    return specs


def prepare_message(
    text: str,
    buttons: Sequence[str | Mapping[str, Any]] | None = None,
    thread_id: str | None = None,
    callbacks: Sequence[str] | None = None,
    parse_mode: str | None = None,
    fallback_buttons: Sequence[str | Mapping[str, Any]] | None = None,
    allow_marker_buttons: bool = True,
) -> PreparedMessage:
    normalized_text = normalize_whitespace(text)
    if allow_marker_buttons:
        cleaned_text, marker_buttons = parse_button_marker(normalized_text)
    else:
        cleaned_text, marker_buttons = BUTTON_MARKER_RE.sub("", normalized_text).strip(), []
    selected_buttons: Sequence[str | Mapping[str, Any]] = buttons or marker_buttons or fallback_buttons or []
    specs = _coerce_button_specs(selected_buttons, thread_id=thread_id, callbacks=callbacks)
    return PreparedMessage(
        text=truncate_for_telegram(cleaned_text),
        buttons=specs,
        parse_mode=parse_mode,
    )


def _extract_inline_keyboard_buttons(reply_markup: Mapping[str, Any]) -> list[str | Mapping[str, Any]]:
    keyboard = reply_markup.get("inline_keyboard", [])
    extracted: list[str | Mapping[str, Any]] = []
    for row in keyboard:
        if not row:
            continue
        for item in row:
            if not isinstance(item, Mapping):
                continue
            text = str(item.get("text", "")).strip()
            callback_data = str(item.get("callback_data", "")).strip()
            if text:
                extracted.append({"text": text, "callback_data": callback_data})
    return extracted


def _render_server_text_as_html(text: str) -> str:
    escaped = html.escape(normalize_whitespace(text), quote=False)
    escaped = DOUBLE_BOLD_SPAN_RE.sub(lambda match: f"<b>{match.group(1)}</b>", escaped)
    return SINGLE_BOLD_SPAN_RE.sub(lambda match: f"<b>{match.group(1)}</b>", escaped)


def _looks_like_terminal_confirmation(text: str) -> bool:
    normalized = normalize_whitespace(text).lower()
    terminal_tokens = [
        "הפעולה בוצעה",
        "הפעולה הושלמה",
        "נשלח בהצלחה",
        "נשלחה בהצלחה",
        "האירוע נוסף ליומן",
        "האירוע עודכן",
        "הבקשה עובדה בהצלחה",
        "action completed",
        "sent successfully",
        "event created successfully",
        "event updated",
    ]
    return any(token in normalized for token in terminal_tokens)


def prepare_server_response(response: Mapping[str, Any]) -> PreparedMessage:
    text = str(response.get("answer") or response.get("draft") or response.get("message") or "")
    thread_id = str(response.get("internal_id") or response.get("thread_id") or "").strip() or None
    parse_mode = response.get("parse_mode")
    should_fallback = bool(response.get("is_paused") or response.get("action_needed"))
    has_marker_buttons = bool(BUTTON_MARKER_RE.search(text))

    buttons: list[str | Mapping[str, Any]] = []
    callbacks: list[str] = []

    if isinstance(response.get("reply_markup"), Mapping):
        buttons = _extract_inline_keyboard_buttons(response["reply_markup"])
    elif isinstance(response.get("tg_keyboard"), Sequence):
        buttons = []
        for row in response["tg_keyboard"]:
            if not row:
                continue
            first = row[0] if isinstance(row, Sequence) else None
            if isinstance(first, Mapping) and first.get("text"):
                buttons.append(
                    {
                        "text": str(first["text"]),
                        "callback_data": str(first.get("callback_data", "")).strip(),
                    }
                )

    if not buttons and response.get("suggested_buttons"):
        buttons = [str(button) for button in response.get("suggested_buttons", [])]

    if response.get("button_callbacks"):
        callbacks = [str(item) for item in response.get("button_callbacks", [])]

    parse_mode_value = parse_mode if isinstance(parse_mode, str) else "HTML"
    rendered_text = _render_server_text_as_html(text) if parse_mode_value == "HTML" else text

    return prepare_message(
        text=rendered_text,
        buttons=buttons,
        thread_id=thread_id,
        callbacks=callbacks,
        parse_mode=parse_mode_value,
        fallback_buttons=fallback_buttons_for_text(text, is_paused=bool(response.get("is_paused"))) if should_fallback else None,
        allow_marker_buttons=should_fallback or bool(buttons) or (has_marker_buttons and not _looks_like_terminal_confirmation(text)),
    )
