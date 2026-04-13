import os
import time
from typing import Any

from pymongo import MongoClient

from utils.logger import server_logger

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")

PRICING_USD_PER_1M: dict[str, dict[str, dict[str, float]]] = {
    "gemini": {
        "gemini-flash-latest": {"input": 0.075, "output": 0.30},
        "gemini-3-flash-preview": {"input": 0.075, "output": 0.30},
        "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-2.5-flash-preview": {"input": 0.075, "output": 0.30},
    },
    "anthropic": {
        "claude-3-5-haiku-latest": {"input": 0.80, "output": 4.00},
    },
    "groq": {
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    },
}

_client: MongoClient | None = None
_collection = None

MODEL_ALIASES: dict[str, dict[str, str]] = {
    "gemini": {
        "gemini-3-flash-preview": "gemini-flash-latest",
        "gemini-2.5-flash": "gemini-flash-latest",
        "gemini-2.5-flash-preview": "gemini-flash-latest",
    },
}


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        _client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        _collection = _client["myos"]["cost_log"]
        _collection.create_index([("userId", 1), ("timestamp", -1)])
        _collection.create_index([("agent_name", 1), ("timestamp", -1)])
        return _collection
    except Exception as exc:
        server_logger.warning(f"Cost logger unavailable: {exc}")
        _collection = None
        return None


def estimate_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    provider_key = (provider or "").strip().lower()
    model_key = (model or "").strip().lower()
    provider_rates = PRICING_USD_PER_1M.get(provider_key, {})
    alias_model_key = MODEL_ALIASES.get(provider_key, {}).get(model_key, model_key)
    rates = provider_rates.get(model_key) or provider_rates.get(alias_model_key)
    if not rates:
        if provider_key == "gemini" and "flash" in model_key:
            rates = provider_rates.get("gemini-flash-latest")
        elif provider_key == "anthropic" and "haiku" in model_key:
            rates = provider_rates.get("claude-3-5-haiku-latest")
        elif provider_key == "groq" and "llama-3.3-70b" in model_key:
            rates = provider_rates.get("llama-3.3-70b-versatile")
    if not rates:
        return 0.0
    return round(
        (max(input_tokens, 0) * rates["input"] / 1_000_000)
        + (max(output_tokens, 0) * rates["output"] / 1_000_000),
        8,
    )


def _extract_usage_dict(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        return usage

    response_metadata = getattr(response, "response_metadata", None)
    if isinstance(response_metadata, dict):
        for key in ("usage_metadata", "token_usage", "usage"):
            nested = response_metadata.get(key)
            if isinstance(nested, dict):
                return nested
    return {}


def extract_token_counts(response: Any) -> tuple[int, int]:
    usage = _extract_usage_dict(response)
    input_tokens = int(
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or usage.get("inputTokenCount")
        or 0
    )
    output_tokens = int(
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or usage.get("candidatesTokenCount")
        or 0
    )
    return input_tokens, output_tokens


def log_llm_cost(
    *,
    user_id: str,
    agent_name: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    thread_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    collection = _get_collection()
    if collection is None:
        return

    estimated_cost = estimate_cost_usd(provider, model, input_tokens, output_tokens)
    doc = {
        "userId": user_id,
        "user_id": user_id,
        "agent_name": agent_name,
        "provider": provider,
        "model": model,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "estimated_cost_usd": estimated_cost,
        "thread_id": thread_id or "",
        "metadata": metadata or {},
        "timestamp": time.time(),
    }
    try:
        collection.insert_one(doc)
    except Exception as exc:
        server_logger.warning(f"Failed to write cost log: {exc}")
