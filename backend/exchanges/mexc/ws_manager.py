from __future__ import annotations

import time
from typing import Any

from exchanges.mexc.order_rules import to_mexc_symbol


class MexcWsManager:
    """Manages MEXC Spot WebSocket stream topics, backoff reconnection, and message parsing."""

    WS_ENDPOINT = "wss://wbs-api.mexc.com/ws"

    def __init__(self) -> None:
        self._subscriptions: set[str] = set()
        self._attempt = 0
        self._connected = False
        self._last_event_ms: dict[str, int] = {}
        self._gap_events = 0

    @staticmethod
    def compute_backoff_delay(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
        """Compute bounded exponential backoff delay in seconds."""
        if attempt <= 0:
            return base
        return min(cap, base * (2 ** (attempt - 1)))

    @staticmethod
    def build_kline_topic(symbol: str, mexc_interval: str) -> str:
        """Build MEXC Spot public kline subscription topic."""
        return f"spot@public.kline.v3.api@{to_mexc_symbol(symbol)}@{mexc_interval}"

    @staticmethod
    def build_deals_topic(symbol: str) -> str:
        """Build MEXC Spot public trades subscription topic."""
        return f"spot@public.deals.v3.api@{to_mexc_symbol(symbol)}"

    @staticmethod
    def parse_ws_kline_message(raw: dict[str, Any]) -> dict[str, Any] | None:
        """Parse a MEXC Spot kline push message into canonical candle dict."""
        channel = str(raw.get("c", ""))
        data = raw.get("d")
        if "public.kline" not in channel or not isinstance(data, dict):
            return None
        k = data.get("k")
        if not isinstance(k, dict):
            return None
        try:
            open_sec = int(k["t"])
            return {
                "symbol": str(raw.get("s", "")),
                "interval": str(k.get("i", "")),
                "time": open_sec,
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low": float(k["l"]),
                "close": float(k["c"]),
                "volume": float(k["v"]),
                "event_time_ms": int(raw.get("t", int(time.time() * 1000))),
            }
        except (KeyError, TypeError, ValueError):
            return None

    def register_subscription(self, topic: str) -> dict[str, Any]:
        self._subscriptions.add(topic)
        return {"method": "SUBSCRIPTION", "params": [topic]}

    def mark_connected(self) -> None:
        self._connected = True
        self._attempt = 0

    def record_disconnect(self) -> float:
        self._connected = False
        self._attempt += 1
        return self.compute_backoff_delay(self._attempt)

    def record_message(self, topic: str, event_time_ms: int) -> bool:
        """Record stream timestamp and flag out-of-order/backward sequence jumps."""
        prev = self._last_event_ms.get(topic)
        self._last_event_ms[topic] = event_time_ms
        if prev is not None and event_time_ms < prev:
            self._gap_events += 1
            return False
        return True

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "endpoint": self.WS_ENDPOINT,
            "connected": self._connected,
            "reconnect_attempt": self._attempt,
            "subscriptions": sorted(self._subscriptions),
            "gap_events": self._gap_events,
        }
