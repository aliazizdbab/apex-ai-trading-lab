from __future__ import annotations

import time
from typing import Any

import httpx

from exchanges.mexc.order_rules import SymbolOrderRules, parse_mexc_symbol_info, to_mexc_symbol
from exchanges.mexc.rate_limiter import TokenBucketRateLimiter


class MexcApiError(RuntimeError):
    """Raised when MEXC REST v3 returns an error or invalid payload."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MexcMarketDataClient:
    """Public MEXC Spot REST v3 client (no credentials required)."""

    BASE_URL = "https://api.mexc.com"

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        timeout: float = 10.0,
        rate_limiter: TokenBucketRateLimiter | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None, weight: int = 1) -> Any:
        self.rate_limiter.acquire(weight=weight)
        try:
            resp = self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise MexcApiError(f"Network error contacting MEXC: {exc}") from exc

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "2"))
            self.rate_limiter.trigger_backoff(retry_after)
            raise MexcApiError("MEXC rate limit exceeded (429)", status_code=429)

        if resp.status_code >= 400:
            raise MexcApiError(f"MEXC API error {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)

        try:
            return resp.json()
        except ValueError as exc:
            raise MexcApiError("Invalid JSON response from MEXC") from exc

    def get_server_time(self) -> tuple[int, float]:
        """Ping /api/v3/time and return (server_time_ms, latency_ms)."""
        t0 = time.perf_counter()
        data = self._get("/api/v3/time", weight=1)
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        if not isinstance(data, dict) or "serverTime" not in data:
            raise MexcApiError("Unexpected /api/v3/time payload")
        return int(data["serverTime"]), latency_ms

    def get_exchange_info(self, symbols: list[str] | None = None) -> list[SymbolOrderRules]:
        """Fetch Spot symbol rules from /api/v3/exchangeInfo."""
        params: dict[str, Any] = {}
        if symbols:
            mexc_syms = [to_mexc_symbol(s) for s in symbols]
            if len(mexc_syms) == 1:
                params["symbol"] = mexc_syms[0]
            else:
                params["symbols"] = ",".join(mexc_syms)
        data = self._get("/api/v3/exchangeInfo", params=params or None, weight=5)
        raw_symbols = data.get("symbols", []) if isinstance(data, dict) else []
        wanted = {to_mexc_symbol(s) for s in symbols} if symbols else None
        rules: list[SymbolOrderRules] = []
        for item in raw_symbols:
            if wanted and str(item.get("symbol", "")).upper() not in wanted:
                continue
            rules.append(parse_mexc_symbol_info(item))
        return rules

    def get_24h_tickers(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        """Fetch 24h ticker statistics from /api/v3/ticker/24hr."""
        data = self._get("/api/v3/ticker/24hr", weight=5)
        if isinstance(data, dict):
            rows = [data]
        elif isinstance(data, list):
            rows = data
        else:
            raise MexcApiError("Unexpected /api/v3/ticker/24hr payload")

        symbol_map = {to_mexc_symbol(s): s for s in symbols} if symbols else None
        result: list[dict[str, Any]] = []
        for item in rows:
            mexc_sym = str(item.get("symbol", "")).upper()
            if symbol_map is not None and mexc_sym not in symbol_map:
                continue
            display_sym = symbol_map[mexc_sym] if symbol_map else mexc_sym
            last_price = float(item.get("lastPrice") or 0.0)
            change_ratio = float(item.get("priceChangePercent") or 0.0)
            result.append(
                {
                    "symbol": display_sym,
                    "mexc_symbol": mexc_sym,
                    "last": last_price,
                    "change24h": round(change_ratio * 100.0, 4),
                    "volume24h": float(item.get("quoteVolume") or 0.0),
                    "baseVolume24h": float(item.get("volume") or 0.0),
                    "high": float(item.get("highPrice") or 0.0),
                    "low": float(item.get("lowPrice") or 0.0),
                    "bid": float(item.get("bidPrice") or 0.0),
                    "ask": float(item.get("askPrice") or 0.0),
                    "status": "trading" if last_price > 0 else "halted",
                }
            )
        return result

    def get_klines(
        self,
        mexc_symbol: str,
        mexc_interval: str,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch OHLCV klines from /api/v3/klines."""
        clamped_limit = max(1, min(limit, 1000))
        params: dict[str, Any] = {
            "symbol": to_mexc_symbol(mexc_symbol),
            "interval": mexc_interval,
            "limit": clamped_limit,
        }
        if start_time_ms is not None:
            params["startTime"] = int(start_time_ms)
        if end_time_ms is not None:
            params["endTime"] = int(end_time_ms)

        data = self._get("/api/v3/klines", params=params, weight=2)
        if not isinstance(data, list):
            raise MexcApiError("Unexpected /api/v3/klines payload")

        now_ms = int(time.time() * 1000)
        candles: list[dict[str, Any]] = []
        for row in data:
            if not isinstance(row, list) or len(row) < 7:
                continue
            open_ms = int(row[0])
            close_ms = int(row[6])
            candles.append(
                {
                    "time": open_ms // 1000,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "is_closed": close_ms <= now_ms,
                }
            )
        candles.sort(key=lambda c: c["time"])
        return candles

    def get_order_book(self, mexc_symbol: str, limit: int = 15) -> dict[str, Any]:
        """Fetch live Spot order book depth from /api/v3/depth."""
        clamped = max(5, min(limit, 100))
        data = self._get(
            "/api/v3/depth",
            params={"symbol": to_mexc_symbol(mexc_symbol), "limit": clamped},
            weight=2,
        )
        bids = [[float(p), float(q)] for p, q in data.get("bids", [])]
        asks = [[float(p), float(q)] for p, q in data.get("asks", [])]
        best_bid = bids[0][0] if bids else 0.0
        best_ask = asks[0][0] if asks else 0.0
        spread = max(0.0, best_ask - best_bid) if (best_bid > 0 and best_ask > 0) else 0.0
        spread_pct = (spread / best_ask * 100.0) if best_ask > 0 else 0.0
        return {
            "lastUpdateId": data.get("lastUpdateId"),
            "bids": bids,
            "asks": asks,
            "spread": spread,
            "spread_pct": round(spread_pct, 4),
        }

    def get_recent_trades(self, mexc_symbol: str, limit: int = 25) -> list[dict[str, Any]]:
        """Fetch recent Spot trades from /api/v3/trades."""
        clamped = max(1, min(limit, 100))
        data = self._get(
            "/api/v3/trades",
            params={"symbol": to_mexc_symbol(mexc_symbol), "limit": clamped},
            weight=2,
        )
        if not isinstance(data, list):
            raise MexcApiError("Unexpected /api/v3/trades payload")
        return [
            {
                "price": float(item["price"]),
                "qty": float(item["qty"]),
                "quoteQty": float(item.get("quoteQty") or 0.0),
                "time": int(item["time"]),
                "side": "sell" if item.get("isBuyerMaker") else "buy",
            }
            for item in data
        ]
