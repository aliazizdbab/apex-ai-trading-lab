from __future__ import annotations

import threading
import time
from typing import Any

from exchanges.mexc.market_client import MexcMarketDataClient
from exchanges.mexc.ws_manager import MexcWsManager

_shared_mexc_client = MexcMarketDataClient()
_shared_ws_manager = MexcWsManager()
_health_cache_lock = threading.Lock()
_health_cache: dict[str, Any] = {"state": "disconnected", "checked_at": 0.0}


def get_mexc_client() -> MexcMarketDataClient:
    """Return shared public MEXC REST v3 client (overridable in tests)."""
    return _shared_mexc_client


def get_ws_manager() -> MexcWsManager:
    """Return shared MEXC WebSocket state manager."""
    return _shared_ws_manager


def get_cached_mexc_health(client: MexcMarketDataClient, ttl_seconds: float = 15.0) -> str:
    """Return cached MEXC connectivity state ('connected' or 'disconnected')."""
    now = time.monotonic()
    with _health_cache_lock:
        if now - float(_health_cache["checked_at"]) < ttl_seconds:
            return str(_health_cache["state"])

    try:
        client.get_server_time()
        state = "connected"
    except Exception:
        state = "disconnected"

    with _health_cache_lock:
        _health_cache["state"] = state
        _health_cache["checked_at"] = now
    return state


def reset_mexc_health_cache() -> None:
    """Reset the MEXC health TTL cache (used in tests)."""
    with _health_cache_lock:
        _health_cache["state"] = "disconnected"
        _health_cache["checked_at"] = 0.0
