from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.router import _vault
from app.core.config import Settings, get_settings
from app.core.crypto import SecretVault
from app.db.models import Base, Candle, CandleCoverage, Symbol
from app.db.session import build_engine, get_db
from app.main import create_app
from app.services.market_data import (
    TIMEFRAME_SECONDS,
    aggregate_candles,
    bucket_open_time,
    validate_candle_series,
)
from app.services.mexc_provider import get_mexc_client, reset_mexc_health_cache
from exchanges.mexc.market_client import MexcMarketDataClient
from exchanges.mexc.order_rules import parse_mexc_symbol_info, validate_order_params
from exchanges.mexc.rate_limiter import TokenBucketRateLimiter
from exchanges.mexc.ws_manager import MexcWsManager


def _make_mock_mexc_transport() -> httpx.MockTransport:
    now_sec = 1795017600  # Exact 4h/1D aligned UTC timestamp (2026-11-18T16:00:00Z-ish)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v3/time":
            return httpx.Response(200, json={"serverTime": now_sec * 1000})

        if path == "/api/v3/exchangeInfo":
            return httpx.Response(
                200,
                json={
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "status": "1",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "baseAssetPrecision": 8,
                            "quotePrecision": 2,
                            "quoteAssetPrecision": 2,
                            "baseSizePrecision": "0.000001",
                            "quoteAmountPrecision": "1",
                            "orderTypes": ["LIMIT", "MARKET", "LIMIT_MAKER"],
                            "isSpotTradingAllowed": True,
                        },
                        {
                            "symbol": "ETHUSDT",
                            "status": "1",
                            "baseAsset": "ETH",
                            "quoteAsset": "USDT",
                            "baseAssetPrecision": 8,
                            "quotePrecision": 2,
                            "quoteAssetPrecision": 2,
                            "baseSizePrecision": "0.0001",
                            "quoteAmountPrecision": "1",
                            "orderTypes": ["LIMIT", "MARKET", "LIMIT_MAKER"],
                            "isSpotTradingAllowed": True,
                        },
                    ]
                },
            )

        if path == "/api/v3/ticker/24hr":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "priceChange": "-1345.25",
                        "priceChangePercent": "-0.021",
                        "lastPrice": "62533.64",
                        "highPrice": "65246.93",
                        "lowPrice": "62350.00",
                        "volume": "4939.01",
                        "quoteVolume": "316190544.20",
                        "bidPrice": "62530.00",
                        "askPrice": "62535.00",
                    },
                    {
                        "symbol": "ETHUSDT",
                        "priceChange": "85.10",
                        "priceChangePercent": "0.0285",
                        "lastPrice": "3070.50",
                        "highPrice": "3110.00",
                        "lowPrice": "2980.00",
                        "volume": "42000.0",
                        "quoteVolume": "128961000.00",
                        "bidPrice": "3070.00",
                        "askPrice": "3071.00",
                    },
                ],
            )

        if path == "/api/v3/klines":
            interval = request.url.params.get("interval", "15m")
            limit = int(request.url.params.get("limit", "100"))
            end_ms = request.url.params.get("endTime")
            step_map = {
                "1m": 60,
                "5m": 300,
                "15m": 900,
                "30m": 1800,
                "60m": 3600,
                "4h": 14400,
                "8h": 28800,
                "1d": 86400,
            }
            step = step_map.get(interval, 900)
            anchor = (int(end_ms) // 1000) if end_ms else now_sec
            anchor = (anchor // step) * step
            rows = []
            for idx in range(limit):
                open_sec = anchor - (limit - 1 - idx) * step
                close_sec = open_sec + step
                base_px = 62000.0 + idx * 2.5
                rows.append(
                    [
                        open_sec * 1000,
                        f"{base_px:.2f}",
                        f"{base_px + 15.0:.2f}",
                        f"{base_px - 10.0:.2f}",
                        f"{base_px + 5.0:.2f}",
                        "12.345",
                        close_sec * 1000,
                        "765000.00",
                    ]
                )
            return httpx.Response(200, json=rows)

        if path == "/api/v3/depth":
            return httpx.Response(
                200,
                json={
                    "lastUpdateId": 999111,
                    "bids": [["62530.00", "0.50"], ["62525.00", "1.20"]],
                    "asks": [["62535.00", "0.40"], ["62540.00", "0.90"]],
                },
            )

        if path == "/api/v3/trades":
            return httpx.Response(
                200,
                json=[
                    {
                        "price": "62533.64",
                        "qty": "0.015",
                        "quoteQty": "938.00",
                        "time": now_sec * 1000,
                        "isBuyerMaker": False,
                    },
                    {
                        "price": "62531.00",
                        "qty": "0.020",
                        "quoteQty": "1250.62",
                        "time": (now_sec - 2) * 1000,
                        "isBuyerMaker": True,
                    },
                ],
            )

        return httpx.Response(404, json={"msg": f"Unhandled path {path}"})

    return httpx.MockTransport(handler)


@pytest.fixture()
def phase3_env(tmp_path: Path):
    db_path = tmp_path / "test_phase3.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    master_key_bytes = os.urandom(32)
    master_key_b64 = base64.urlsafe_b64encode(master_key_bytes).decode("ascii")

    test_settings = Settings(
        database_url=db_url,
        master_encryption_key=master_key_b64,
    )
    test_engine = build_engine(db_url)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    mock_client = MexcMarketDataClient(transport=_make_mock_mexc_transport())
    reset_mexc_health_cache()

    app = create_app()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[_vault] = lambda: SecretVault(master_key_bytes)
    app.dependency_overrides[get_mexc_client] = lambda: mock_client

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    mock_client.close()
    reset_mexc_health_cache()
    test_engine.dispose()


def test_rate_limiter_token_consumption_and_backoff():
    clock = [100.0]
    slept = []

    def fake_time():
        return clock[0]

    def fake_sleep(seconds: float):
        slept.append(seconds)
        clock[0] += seconds

    limiter = TokenBucketRateLimiter(
        capacity=10,
        refill_per_second=2.0,
        time_fn=fake_time,
        sleep_fn=fake_sleep,
    )

    assert limiter.acquire(weight=6) == 0.0
    assert limiter.acquire(weight=4) == 0.0
    # Bucket is empty; acquiring weight=2 requires 1.0s refill
    waited = limiter.acquire(weight=2)
    assert pytest.approx(waited, abs=1e-6) == 1.0
    assert limiter.status()["total_weight_used"] == 12

    limiter.trigger_backoff(3.5)
    assert limiter.status()["in_backoff"] is True
    waited_backoff = limiter.acquire(weight=1)
    assert waited_backoff >= 3.5


def test_mexc_symbol_rules_and_order_validation():
    raw = {
        "symbol": "BTCUSDT",
        "status": "1",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "baseAssetPrecision": 8,
        "quotePrecision": 2,
        "quoteAssetPrecision": 2,
        "baseSizePrecision": "0.000001",
        "quoteAmountPrecision": "1",
        "orderTypes": ["LIMIT", "MARKET", "LIMIT_MAKER"],
        "isSpotTradingAllowed": True,
    }
    rules = parse_mexc_symbol_info(raw)
    assert rules.symbol == "BTC/USDT"
    assert rules.price_precision == 2
    assert rules.qty_precision == 6
    assert rules.min_qty == Decimal("0.000001")
    assert rules.min_notional == Decimal("1")
    assert rules.status == "trading"

    ok, err, px, qty = validate_order_params(rules, Decimal("62500.129"), Decimal("0.0010009"))
    assert ok is True
    assert err is None
    assert px == Decimal("62500.12")
    assert qty == Decimal("0.001000")

    # Below min_notional (1 USDT)
    ok_low, err_low, _, _ = validate_order_params(rules, Decimal("62500.00"), Decimal("0.000010"))
    assert ok_low is False
    assert "notional" in (err_low or "").lower()

    # Below min_qty
    ok_qty, err_qty, _, _ = validate_order_params(rules, Decimal("100000.00"), Decimal("0.0000001"))
    assert ok_qty is False
    assert "minimum" in (err_qty or "").lower()


def test_candle_aggregation_and_utc_calendar_boundaries():
    # 1) 1m -> 3m aggregation (two full 3m buckets)
    base_1m = [
        {"time": 180 * 10 + 0, "open": 100, "high": 105, "low": 99, "close": 102, "volume": 10, "is_closed": True},
        {"time": 180 * 10 + 60, "open": 102, "high": 108, "low": 101, "close": 107, "volume": 15, "is_closed": True},
        {"time": 180 * 10 + 120, "open": 107, "high": 109, "low": 104, "close": 106, "volume": 5, "is_closed": True},
        {"time": 180 * 11 + 0, "open": 106, "high": 110, "low": 105, "close": 109, "volume": 8, "is_closed": True},
    ]
    agg_3m = aggregate_candles(base_1m, "3m")
    assert len(agg_3m) == 2
    assert agg_3m[0] == {
        "time": 180 * 10,
        "open": 100.0,
        "high": 109.0,
        "low": 99.0,
        "close": 106.0,
        "volume": 30.0,
        "is_closed": True,
    }
    # Second bucket only has 1 of 3 bars -> incomplete / not closed
    assert agg_3m[1]["is_closed"] is False

    # 2) 1h -> 2h and 6h, 4h -> 12h, 1D -> 3D
    start_day = int(datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc).timestamp())  # Monday 00:00 UTC
    base_1h = [
        {"time": start_day + i * 3600, "open": 100 + i, "high": 102 + i, "low": 99 + i, "close": 101 + i, "volume": 2, "is_closed": True}
        for i in range(6)
    ]
    agg_2h = aggregate_candles(base_1h, "2h")
    assert len(agg_2h) == 3
    assert agg_2h[0]["open"] == 100.0 and agg_2h[0]["close"] == 102.0 and agg_2h[0]["volume"] == 4.0

    agg_6h = aggregate_candles(base_1h, "6h")
    assert len(agg_6h) == 1
    assert agg_6h[0]["open"] == 100.0 and agg_6h[0]["high"] == 107.0 and agg_6h[0]["low"] == 99.0 and agg_6h[0]["close"] == 106.0
    assert agg_6h[0]["is_closed"] is True

    # 3) 1W Monday UTC boundary: Sunday 2026-11-15 vs Monday 2026-11-16
    sun_ts = int(datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc).timestamp())
    mon_ts = int(datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc).timestamp())
    assert bucket_open_time(sun_ts, "1W") < bucket_open_time(mon_ts, "1W")
    assert bucket_open_time(mon_ts, "1W") == mon_ts

    # 4) 1M Calendar month boundary: Jan 31 vs Feb 1
    jan31 = int(datetime(2026, 1, 31, 0, 0, tzinfo=timezone.utc).timestamp())
    feb1 = int(datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc).timestamp())
    assert bucket_open_time(jan31, "1M") == int(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp())
    assert bucket_open_time(feb1, "1M") == feb1


def test_validate_candle_series_quality_and_snapshot_hash():
    t0 = 1795000000 // 900 * 900
    clean = [
        {"time": t0 + i * 900, "open": 100.0 + i, "high": 105.0 + i, "low": 99.0 + i, "close": 102.0 + i, "volume": 10.0}
        for i in range(5)
    ]
    report_clean = validate_candle_series(clean, "15m")
    assert report_clean.is_clean is True
    assert report_clean.gap_count == 0
    assert report_clean.duplicate_count == 0
    assert report_clean.invalid_ohlc_count == 0
    assert len(report_clean.data_snapshot_hash) == 64

    # Same data produces identical deterministic snapshot hash
    assert validate_candle_series(clean, "15m").data_snapshot_hash == report_clean.data_snapshot_hash

    # Dirty series: gap of 2 bars + duplicate + out-of-order + invalid OHLC (high < low)
    dirty = [
        {"time": t0, "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 10.0},
        {"time": t0 + 900 * 3, "open": 103.0, "high": 100.0, "low": 104.0, "close": 101.0, "volume": 5.0},
        {"time": t0, "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 10.0},
    ]
    report_dirty = validate_candle_series(dirty, "15m")
    assert report_dirty.is_clean is False
    assert report_dirty.gap_count == 2
    assert report_dirty.duplicate_count == 1
    assert report_dirty.out_of_order_count == 1
    assert report_dirty.invalid_ohlc_count == 1


def test_ws_manager_backoff_topics_and_parsing():
    assert MexcWsManager.compute_backoff_delay(1) == 1.0
    assert MexcWsManager.compute_backoff_delay(2) == 2.0
    assert MexcWsManager.compute_backoff_delay(5) == 16.0
    assert MexcWsManager.compute_backoff_delay(10, cap=60.0) == 60.0

    topic = MexcWsManager.build_kline_topic("BTC/USDT", "15m")
    assert topic == "spot@public.kline.v3.api@BTCUSDT@15m"
    assert MexcWsManager.build_deals_topic("ETH/USDT") == "spot@public.deals.v3.api@ETHUSDT"

    ws = MexcWsManager()
    sub_msg = ws.register_subscription(topic)
    assert sub_msg["method"] == "SUBSCRIPTION"
    ws.mark_connected()
    assert ws.record_message(topic, 1000) is True
    assert ws.record_message(topic, 900) is False  # backward jump flagged
    assert ws.snapshot_state()["gap_events"] == 1

    parsed = MexcWsManager.parse_ws_kline_message(
        {
            "c": topic,
            "s": "BTCUSDT",
            "t": 1795000001000,
            "d": {
                "k": {
                    "t": 1795000000,
                    "i": "15m",
                    "o": "62500.00",
                    "h": "62550.00",
                    "l": "62480.00",
                    "c": "62520.00",
                    "v": "3.21",
                }
            },
        }
    )
    assert parsed is not None
    assert parsed["close"] == 62520.0
    assert parsed["time"] == 1795000000


def test_phase3_market_endpoints_and_db_persistence(phase3_env):
    client, SessionLocal = phase3_env

    # 1. /health reports mexc connected
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["mexc"] == "connected"
    assert health.json()["engine"] == "connected"

    # 2. /exchanges/mexc/status reports all 15 timeframes & symbol rules
    status_res = client.get("/api/v1/exchanges/mexc/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "connected"
    assert len(status_data["timeframes"]) == len(TIMEFRAME_SECONDS) == 15
    assert status_data["platform_sl_tp_required"] is True
    assert "LIMIT" in status_data["supported_order_types"]

    # 3. /market/tickers converts ratio to percent
    tickers = client.get("/api/v1/market/tickers")
    assert tickers.status_code == 200
    items = tickers.json()["items"]
    btc = next(r for r in items if r["symbol"] == "BTC/USDT")
    assert pytest.approx(btc["change24h"], abs=1e-4) == -2.1
    assert btc["last"] == 62533.64

    # 4. /market/candles native 15m -> persisted in candles & candle_coverage
    c15 = client.get("/api/v1/market/candles?symbol=BTC/USDT&timeframe=15m&limit=25")
    assert c15.status_code == 200
    d15 = c15.json()
    assert d15["source"] == "mexc_native"
    assert len(d15["items"]) == 25
    assert d15["quality"]["is_clean"] is True

    # 5. /market/candles aggregated 2h (built from 1h)
    c2h = client.get("/api/v1/market/candles?symbol=BTC/USDT&timeframe=2h&limit=10")
    assert c2h.status_code == 200
    d2h = c2h.json()
    assert d2h["source"] == "mexc_agg_1h"
    assert len(d2h["items"]) == 10
    assert d2h["quality"]["is_clean"] is True

    # 6. Orderbook & recent trades
    book = client.get("/api/v1/market/orderbook?symbol=BTC/USDT&limit=5")
    assert book.status_code == 200
    assert book.json()["spread"] == 5.0
    assert len(book.json()["bids"]) == 2

    trades = client.get("/api/v1/market/trades?symbol=BTC/USDT&limit=10")
    assert trades.status_code == 200
    assert len(trades.json()["items"]) == 2

    # 7. Backfill & Coverage
    backfill = client.post(
        "/api/v1/market/backfill",
        json={"symbol": "ETH/USDT", "timeframe": "4h", "bars": 60},
    )
    assert backfill.status_code == 200
    assert backfill.json()["quality"]["total_bars"] == 60

    coverage = client.get("/api/v1/market/coverage")
    assert coverage.status_code == 200
    cov_data = coverage.json()
    assert len(cov_data["symbols"]) >= 2
    assert len(cov_data["coverage"]) >= 3

    with SessionLocal() as db:
        assert db.query(Symbol).count() >= 2
        assert db.query(Candle).count() >= 95
        assert db.query(CandleCoverage).count() >= 3
