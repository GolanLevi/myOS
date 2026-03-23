"""Telegram bot package for the native Telegram integration."""

from .message_formatter import (
    ButtonSpec,
    MANUAL_OVERRIDE_TEXT,
    PreparedMessage,
    build_callback_data,
    prepare_message,
    prepare_server_response,
)

__all__ = [
    "ButtonSpec",
    "MANUAL_OVERRIDE_TEXT",
    "PreparedMessage",
    "TelegramNativeBot",
    "build_callback_data",
    "prepare_message",
    "prepare_server_response",
]


def __getattr__(name: str):
    if name == "TelegramNativeBot":
        from .telegram_bot import TelegramNativeBot

        return TelegramNativeBot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
