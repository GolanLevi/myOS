from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional


_current_user_id: ContextVar[Optional[str]] = ContextVar("myos_current_user_id", default=None)


def get_current_user_id(default: Optional[str] = None) -> Optional[str]:
    value = _current_user_id.get()
    return value if value is not None else default


def set_current_user_id(user_id: Optional[str]) -> Token:
    normalized = str(user_id or "").strip() or None
    return _current_user_id.set(normalized)


def reset_current_user_id(token: Token) -> None:
    _current_user_id.reset(token)


@contextmanager
def active_user_context(user_id: Optional[str]) -> Iterator[Optional[str]]:
    token = set_current_user_id(user_id)
    try:
        yield get_current_user_id()
    finally:
        reset_current_user_id(token)
