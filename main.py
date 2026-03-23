from __future__ import annotations

import threading

import uvicorn

from server import get_telegram_bot, server_logger, set_telegram_bot


def run_api() -> None:
    config = uvicorn.Config("server:app", host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def main() -> None:
    bot = get_telegram_bot()
    if bot is not None:
        set_telegram_bot(bot)
    else:
        server_logger.warning("⚠️ Telegram bot is not available; running FastAPI only.")

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    if bot is None:
        api_thread.join()
        return

    bot.run_polling()


if __name__ == "__main__":
    main()
