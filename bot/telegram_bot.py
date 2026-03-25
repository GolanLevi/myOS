from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import requests
from dotenv import load_dotenv

from core.state_manager import WorkflowStateStore
from utils.logger import memory_logger, server_logger

from .message_formatter import ButtonSpec, PreparedMessage, build_callback_data, prepare_message, prepare_server_response

load_dotenv()

_TELEGRAM_IMPORT_ERROR: Exception | None = None
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
except Exception as exc:  # pragma: no cover - exercised only when dependency is missing
    InlineKeyboardButton = InlineKeyboardMarkup = Update = None  # type: ignore[assignment]
    Application = ApplicationBuilder = CallbackQueryHandler = CommandHandler = ContextTypes = MessageHandler = filters = None  # type: ignore[assignment]
    _TELEGRAM_IMPORT_ERROR = exc


DEFAULT_API_BASE_URL = os.getenv("MYOS_API_URL") or os.getenv("SERVER_URL") or os.getenv("FASTAPI_URL") or "http://localhost:8000"
DEFAULT_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _safe_int(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _button_specs_to_markup(buttons: Sequence[ButtonSpec]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(text=button.text, callback_data=button.callback_data)] for button in buttons]
    return InlineKeyboardMarkup(rows)


class TelegramNativeBot:
    """Native Telegram bot wrapper for myOS."""

    def __init__(
        self,
        bot_token: str | None = None,
        api_base_url: str | None = None,
        default_chat_id: int | None = None,
        state_manager: WorkflowStateStore | None = None,
        request_timeout: int = 60,
    ) -> None:
        if _TELEGRAM_IMPORT_ERROR is not None:
            raise RuntimeError(
                "python-telegram-bot is required for TelegramNativeBot. "
                "Install python-telegram-bot>=21.0 before running the bot."
            ) from _TELEGRAM_IMPORT_ERROR

        token = (bot_token or DEFAULT_BOT_TOKEN).strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is missing.")

        self.bot_token = token
        self.api_base_url = (api_base_url or DEFAULT_API_BASE_URL).rstrip("/")
        self.default_chat_id = default_chat_id if default_chat_id is not None else _safe_int(DEFAULT_CHAT_ID)
        self.request_timeout = request_timeout
        self.state_manager = state_manager or WorkflowStateStore()

        self.application = ApplicationBuilder().token(token).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CallbackQueryHandler(self._handle_callback_query))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_message))

    def _build_api_url(self, path: str) -> str:
        return f"{self.api_base_url}/{path.lstrip('/')}"

    def _post_json(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        response = requests.post(
            self._build_api_url(path),
            json=dict(payload),
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object from server.")
        return data

    async def _post_json_async(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._post_json, path, payload)

    def _resolve_chat_id(self, update: Update) -> int:
        chat_id = update.effective_chat.id if update.effective_chat else self.default_chat_id
        if chat_id is None:
            raise ValueError("No chat_id available and TELEGRAM_CHAT_ID is not configured.")
        return chat_id

    def _store_thread_mapping(self, telegram_message_id: int, thread_id: str) -> None:
        if not thread_id:
            return

        if self.state_manager.messages is not None:
            self.state_manager.messages.update_one(
                {"telegram_id": str(telegram_message_id)},
                {"$set": {"telegram_id": str(telegram_message_id), "action_id": thread_id}},
                upsert=True,
            )
        else:
            self.state_manager._memory_messages[str(telegram_message_id)] = thread_id

        memory_logger.info(f"🔗 Stored Telegram message {telegram_message_id} -> thread {thread_id}")

    def _resolve_thread_from_reply(self, reply_to_message_id: int | None) -> str | None:
        if reply_to_message_id is None:
            return None

        if self.state_manager.messages is not None:
            mapping = self.state_manager.messages.find_one({"telegram_id": str(reply_to_message_id)})
            if mapping and mapping.get("action_id"):
                return str(mapping["action_id"])

        if hasattr(self.state_manager, "_memory_messages"):
            return self.state_manager._memory_messages.get(str(reply_to_message_id))
        return None

    def _to_markup(self, buttons: Sequence[ButtonSpec]) -> InlineKeyboardMarkup | None:
        return _button_specs_to_markup(buttons)

    def _serialize_markup(self, buttons: Sequence[ButtonSpec]) -> dict[str, Any] | None:
        if not buttons:
            return None
        return {
            "inline_keyboard": [
                [{"text": button.text, "callback_data": button.callback_data}] for button in buttons
            ]
        }

    @staticmethod
    def _extract_thread_id_from_callback_data(callback_data: str | None) -> str | None:
        if not callback_data or "::" not in callback_data:
            return None
        return callback_data.split("::", 1)[1].strip() or None

    async def _send_prepared_message(
        self,
        chat_id: int,
        prepared: PreparedMessage,
        thread_id: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        markup = self._to_markup(prepared.buttons)
        sent = await self.application.bot.send_message(
            chat_id=chat_id,
            text=prepared.text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=markup,
            parse_mode=prepared.parse_mode,
            disable_web_page_preview=True,
        )

        mapping_thread_id = thread_id
        if mapping_thread_id:
            self._store_thread_mapping(sent.message_id, mapping_thread_id)

        return sent.message_id

    async def send_message(
        self,
        chat_id: int,
        text: str,
        thread_id: str | None = None,
        buttons: Sequence[str | Mapping[str, Any]] | None = None,
        button_callbacks: Sequence[str] | None = None,
        reply_to_message_id: int | None = None,
        parse_mode: str | None = None,
    ) -> int:
        prepared = prepare_message(
            text=text,
            buttons=buttons,
            thread_id=thread_id,
            callbacks=button_callbacks,
            parse_mode=parse_mode,
        )
        return await self._send_prepared_message(chat_id, prepared, thread_id=thread_id, reply_to_message_id=reply_to_message_id)

    async def send_server_response(
        self,
        chat_id: int,
        response: Mapping[str, Any],
        reply_to_message_id: int | None = None,
    ) -> int:
        prepared = prepare_server_response(response)
        thread_id = str(response.get("internal_id") or response.get("thread_id") or "").strip() or None
        return await self._send_prepared_message(chat_id, prepared, thread_id=thread_id, reply_to_message_id=reply_to_message_id)

    def send_server_response_sync(
        self,
        chat_id: int,
        response: Mapping[str, Any],
        reply_to_message_id: int | None = None,
    ) -> int:
        prepared = prepare_server_response(response)
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": prepared.text,
            "disable_web_page_preview": True,
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if prepared.parse_mode:
            payload["parse_mode"] = prepared.parse_mode

        reply_markup = self._serialize_markup(prepared.buttons)
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

        response_obj = requests.post(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data=payload,
            timeout=self.request_timeout,
        )
        response_obj.raise_for_status()
        telegram_payload = response_obj.json()
        if not telegram_payload.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {telegram_payload}")

        message_id = int(telegram_payload["result"]["message_id"])
        thread_id = str(response.get("internal_id") or response.get("thread_id") or "").strip()
        if thread_id:
            self._store_thread_mapping(message_id, thread_id)
        return message_id

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message:
            await update.message.reply_text("שלום")

    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        if not message or not message.text:
            return

        user_id = str(update.effective_user.id if update.effective_user else "telegram")
        reply_to_message_id = message.reply_to_message.message_id if message.reply_to_message else None
        resolved_thread_id = self._resolve_thread_from_reply(reply_to_message_id)

        payload: dict[str, Any] = {
            "text": message.text,
            "source": "telegram",
            "user_id": user_id,
            "reply_to_message_id": reply_to_message_id,
        }
        active_thread_id = context.user_data.get("active_thread_id")
        if not reply_to_message_id and active_thread_id:
            payload["thread_id"] = active_thread_id

        if resolved_thread_id:
            server_logger.info(f"🔗 Reply resolved to thread {resolved_thread_id} from Telegram message {reply_to_message_id}")

        response = await self._post_json_async("/ask", payload)
        response_thread_id = str(response.get("internal_id") or response.get("thread_id") or payload.get("thread_id") or "").strip()
        if response_thread_id:
            context.user_data["active_thread_id"] = response_thread_id
        await self.send_server_response(
            chat_id=self._resolve_chat_id(update),
            response=response,
            reply_to_message_id=message.message_id,
        )

    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return

        await query.answer()
        callback_data = query.data or ""
        user_id = str(query.from_user.id if query.from_user else "telegram")
        reply_to_message_id = query.message.message_id if query.message else None

        payload: dict[str, Any] = {
            "text": callback_data,
            "source": "telegram",
            "user_id": user_id,
            "reply_to_message_id": reply_to_message_id,
        }
        callback_thread_id = self._extract_thread_id_from_callback_data(callback_data)
        if callback_thread_id:
            payload["thread_id"] = callback_thread_id
            context.user_data["active_thread_id"] = callback_thread_id

        response = await self._post_json_async("/ask", payload)
        response_thread_id = str(response.get("internal_id") or response.get("thread_id") or callback_thread_id or "").strip()
        if response_thread_id:
            context.user_data["active_thread_id"] = response_thread_id
        await self.send_server_response(
            chat_id=self._resolve_chat_id(update),
            response=response,
            reply_to_message_id=reply_to_message_id,
        )

    async def initialize(self) -> None:
        await self.application.initialize()

    async def start(self) -> None:
        await self.application.start()

    async def stop(self) -> None:
        await self.application.stop()

    async def shutdown(self) -> None:
        await self.application.shutdown()

    def _clear_legacy_webhook(self) -> None:
        response = requests.get(
            f"https://api.telegram.org/bot{self.bot_token}/deleteWebhook",
            params={"drop_pending_updates": "false"},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram deleteWebhook failed: {payload}")

    def run_polling(self) -> None:
        # Native polling and legacy webhooks cannot coexist. Clear any stale
        # webhook first so a previously configured n8n trigger does not block
        # getUpdates after restarts or rollbacks.
        try:
            self._clear_legacy_webhook()
            server_logger.info("✅ Cleared Telegram webhook before starting native polling.")
        except Exception as exc:
            server_logger.warning(f"⚠️ Could not clear Telegram webhook before polling: {exc}")

        self.application.run_polling(allowed_updates=["message", "callback_query"])


def create_bot_from_env() -> TelegramNativeBot:
    return TelegramNativeBot()


def main() -> None:
    bot = create_bot_from_env()
    bot.run_polling()


if __name__ == "__main__":
    main()

