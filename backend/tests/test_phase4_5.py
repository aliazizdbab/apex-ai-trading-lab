from __future__ import annotations

import ast
import base64
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.router import _vault
from app.core.config import Settings, get_settings
from app.core.crypto import SecretVault
from app.db.models import Base, IndicatorCatalog, IndicatorParameter, SavedIndicatorPreset
from app.db.session import build_engine, get_db
from app.main import create_app
from app.services.mexc_provider import get_mexc_client, reset_mexc_health_cache
from engine.indicators.catalog import INDICATOR_SPECS, validate_and_coerce_params
from engine.indicators.compute import compute_heikin_ashi, compute_indicator
from exchanges.mexc.market_client import MexcMarketDataClient


def _sample_candles(count: int = 120) -> list[dict]:
    t0 = int(datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc).timestamp())
    candles = []
    price = 60000.0
    for i in range(count):
        wave = math.sin(i * 0.27) * 180.0 + (i * 12.0)
        o = price + wave
        c = o + math.cos(i * 0.41) * 95.0
        h = max(o, c) + 45.0 + (i % 5) * 8.0
        l = min(o, c) - 42.0 - (i % 4) * 7.0
        candles.append(
            {
                "time": t0 + i * 900,
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": round(100.0 + (i % 9) * 15.5, 3),
                "is_closed": True,
            }
        )
    return candles


def _make_phase4_mock_transport() -> httpx.MockTransport:
    bars = _sample_candles(120)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v3/time":
            return httpx.Response(200, json={"serverTime": bars[-1]["time"] * 1000})
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
                        }
                    ]
                },
            )
        if path == "/api/v3/klines":
            limit = int(request.url.params.get("limit", "120"))
            subset = bars[-min(limit, len(bars)) :]
            rows = [
                [
                    c["time"] * 1000,
                    str(c["open"]),
                    str(c["high"]),
                    str(c["low"]),
                    str(c["close"]),
                    str(c["volume"]),
                    (c["time"] + 900) * 1000,
                    "1000000",
                ]
                for c in subset
            ]
            return httpx.Response(200, json=rows)
        return httpx.Response(404, json={"msg": f"Unhandled {path}"})

    return httpx.MockTransport(handler)


@pytest.fixture()
def phase4_env(tmp_path: Path):
    db_path = tmp_path / "test_phase4_5.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    master_key_bytes = os.urandom(32)
    master_key_b64 = base64.urlsafe_b64encode(master_key_bytes).decode("ascii")

    test_settings = Settings(database_url=db_url, master_encryption_key=master_key_b64)
    test_engine = build_engine(db_url)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    mock_client = MexcMarketDataClient(transport=_make_phase4_mock_transport())
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


def test_engine_package_import_isolation():
    """Architecture rule: backend/engine/ must never import fastapi or exchanges."""
    engine_dir = Path(__file__).resolve().parents[1] / "engine"
    py_files = list(engine_dir.rglob("*.py"))
    assert len(py_files) >= 3

    forbidden = ("fastapi", "exchanges", "starlette", "httpx")
    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    assert root_mod not in forbidden, f"{py_file} imports forbidden module {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                assert root_mod not in forbidden, f"{py_file} imports forbidden module {node.module}"


def test_heikin_ashi_and_reference_indicators():
    # 1) Heikin Ashi exact math
    raw = [
        {"time": 100, "open": 10.0, "high": 15.0, "low": 8.0, "close": 12.0, "volume": 50.0},
        {"time": 200, "open": 12.0, "high": 18.0, "low": 11.0, "close": 16.0, "volume": 60.0},
    ]
    ha = compute_heikin_ashi(raw)
    assert len(ha) == 2
    assert ha[0]["open"] == pytest.approx(11.0)
    assert ha[0]["close"] == pytest.approx(11.25)
    assert ha[0]["high"] == pytest.approx(15.0)
    assert ha[0]["low"] == pytest.approx(8.0)
    assert ha[1]["open"] == pytest.approx((11.0 + 11.25) / 2.0)
    assert ha[1]["close"] == pytest.approx((12.0 + 18.0 + 11.0 + 16.0) / 4.0)

    # 2) SMA, EMA, Bollinger Bands reference values
    seq = [
        {"time": t * 60, "open": v, "high": v + 1, "low": v - 1, "close": v, "volume": 10.0}
        for t, v in enumerate([10.0, 12.0, 14.0, 16.0])
    ]
    sma_out = compute_indicator("sma", seq, {"length": 3, "source": "close", "offset": 0})["sma"]
    assert [p["value"] for p in sma_out] == [12.0, 14.0]

    ema_out = compute_indicator("ema", seq, {"length": 3, "source": "close", "offset": 0})["ema"]
    assert [p["value"] for p in ema_out] == [12.0, 14.0]

    bb_out = compute_indicator("bb", seq[:3], {"length": 3, "mult": 2.0, "source": "close"})
    expected_sd = math.sqrt(((10 - 12) ** 2 + 0 + (14 - 12) ** 2) / 3.0)
    assert bb_out["basis"][0]["value"] == pytest.approx(12.0)
    assert bb_out["upper"][0]["value"] == pytest.approx(12.0 + 2.0 * expected_sd, abs=1e-6)
    assert bb_out["lower"][0]["value"] == pytest.approx(12.0 - 2.0 * expected_sd, abs=1e-6)

    # 3) RSI rising vs falling bounds
    rising = [
        {"time": t * 60, "open": 10 + t, "high": 11 + t, "low": 9 + t, "close": 10.0 + t, "volume": 5.0}
        for t in range(20)
    ]
    rsi_up = compute_indicator("rsi", rising, {"length": 14})["rsi"]
    assert rsi_up[-1]["value"] == pytest.approx(100.0)

    # 4) VWAP UTC session reset check
    day1 = int(datetime(2026, 11, 10, 23, 0, tzinfo=timezone.utc).timestamp())
    day2 = int(datetime(2026, 11, 11, 0, 0, tzinfo=timezone.utc).timestamp())
    vwap_bars = [
        {"time": day1, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 10.0},
        {"time": day2, "open": 200.0, "high": 200.0, "low": 200.0, "close": 200.0, "volume": 5.0},
    ]
    vwap_out = compute_indicator("vwap", vwap_bars, {"anchor": "session", "source": "close"})["vwap"]
    assert vwap_out[0]["value"] == pytest.approx(100.0)
    assert vwap_out[1]["value"] == pytest.approx(200.0)  # reset on new UTC day

    # 5) All 11 indicators produce non-empty valid outputs on 120 bars
    bars = _sample_candles(120)
    assert len(INDICATOR_SPECS) == 11
    for ind_id in INDICATOR_SPECS:
        series = compute_indicator(ind_id, bars)
        assert len(series) >= 1
        for key, pts in series.items():
            assert len(pts) > 0, f"{ind_id}.{key} returned empty points"


def test_strict_causality_no_lookahead_for_all_indicators():
    """Computing on prefix candles[:N] must match full candles at timestamp N-1 for every indicator."""
    bars = _sample_candles(120)
    cutoff = 85
    target_time = bars[cutoff - 1]["time"]

    for ind_id in INDICATOR_SPECS:
        full_series = compute_indicator(ind_id, bars)
        prefix_series = compute_indicator(ind_id, bars[:cutoff])

        assert set(full_series.keys()) == set(prefix_series.keys())
        for key in full_series:
            full_map = {p["time"]: p["value"] for p in full_series[key]}
            prefix_map = {p["time"]: p["value"] for p in prefix_series[key]}
            assert (target_time in full_map) == (target_time in prefix_map), (
                f"Look-ahead presence mismatch in {ind_id}.{key}"
            )
            if target_time in prefix_map:
                assert prefix_map[target_time] == pytest.approx(full_map[target_time], abs=1e-8), (
                    f"Look-ahead value mismatch in {ind_id}.{key}"
                )


def test_indicator_parameter_validation():
    coerced = validate_and_coerce_params("ema", {"length": "50", "source": "hlc3", "offset": "2"})
    assert coerced == {"length": 50, "source": "hlc3", "offset": 2}

    with pytest.raises(ValueError):
        validate_and_coerce_params("ema", {"length": 0})
    with pytest.raises(ValueError):
        validate_and_coerce_params("ema", {"source": "invalid_source"})
    with pytest.raises(ValueError):
        validate_and_coerce_params("unknown_ind", {})


def test_phase4_5_catalog_presets_crud_and_compute_endpoints(phase4_env):
    client, SessionLocal = phase4_env

    # 1. Catalog lists all 11 built-in indicators and seeds DB
    cat_res = client.get("/api/v1/indicators/catalog")
    assert cat_res.status_code == 200
    cat_items = cat_res.json()["items"]
    assert len(cat_items) == 11
    ids = {item["id"] for item in cat_items}
    assert {"sma", "ema", "bb", "vwap", "supertrend", "ichimoku", "rsi", "macd", "atr", "adx", "stoch"} == ids

    with SessionLocal() as db:
        assert db.query(IndicatorCatalog).count() == 11
        assert db.query(IndicatorParameter).count() >= 25

    # 2. Presets seeded with 3 defaults (EMA 20, BB, RSI 14)
    presets_res = client.get("/api/v1/indicators/presets")
    assert presets_res.status_code == 200
    initial_presets = presets_res.json()["items"]
    assert len(initial_presets) == 3

    # 3. Create invalid preset returns 400
    bad_preset = client.post(
        "/api/v1/indicators/presets",
        json={"indicator_id": "rsi", "name": "Bad RSI", "params": {"length": 1}},
    )
    assert bad_preset.status_code == 400

    # 4. Create valid MACD preset and persist
    create_res = client.post(
        "/api/v1/indicators/presets",
        json={
            "indicator_id": "macd",
            "name": "MACD Fast (8,21,5)",
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "params": {"fast_length": 8, "slow_length": 21, "signal_length": 5, "source": "close"},
            "visible": True,
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()
    preset_id = created["id"]
    assert created["params"]["fast_length"] == 8

    # 5. Update preset (toggle visibility + update params)
    upd_res = client.put(
        f"/api/v1/indicators/presets/{preset_id}",
        json={"name": "MACD Custom", "visible": False, "params": {"fast_length": 10, "slow_length": 24, "signal_length": 9}},
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["visible"] is False
    assert upd_res.json()["params"]["fast_length"] == 10

    with SessionLocal() as db:
        row = db.query(SavedIndicatorPreset).filter(SavedIndicatorPreset.id == preset_id).one()
        assert row.name == "MACD Custom"
        assert row.visible is False

    # 6. Compute indicators in standard & heikin_ashi candle modes
    compute_std = client.post(
        "/api/v1/indicators/compute",
        json={
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "limit": 120,
            "candle_mode": "standard",
            "indicators": [
                {"instance_id": "p1", "indicator_id": "ema", "params": {"length": 20}},
                {"instance_id": "p2", "indicator_id": "rsi", "params": {"length": 14}},
                {"instance_id": "p3", "indicator_id": "ichimoku", "params": {}},
            ],
        },
    )
    assert compute_std.status_code == 200
    std_data = compute_std.json()
    assert std_data["candle_mode"] == "standard"
    assert len(std_data["candles"]) == 120
    assert len(std_data["outputs"]) == 3
    assert std_data["outputs"][0]["pane"] == "overlay"
    assert std_data["outputs"][1]["pane"] == "oscillator"
    assert len(std_data["outputs"][0]["series"]["ema"]) > 80
    assert len(std_data["outputs"][1]["series"]["rsi"]) > 80
    assert len(std_data["outputs"][2]["series"]["senkou_a"]) > 40

    compute_ha = client.post(
        "/api/v1/indicators/compute",
        json={
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "limit": 120,
            "candle_mode": "heikin_ashi",
            "indicators": [
                {"instance_id": "p1", "indicator_id": "supertrend", "params": {"atr_length": 10, "factor": 3.0}},
            ],
        },
    )
    assert compute_ha.status_code == 200
    ha_data = compute_ha.json()
    assert ha_data["candle_mode"] == "heikin_ashi"
    assert ha_data["candles"][0] != std_data["candles"][0]
    assert len(ha_data["outputs"][0]["series"]["supertrend"]) > 90

    # 7. Delete preset
    del_res = client.delete(f"/api/v1/indicators/presets/{preset_id}")
    assert del_res.status_code == 200
    assert len(client.get("/api/v1/indicators/presets").json()["items"]) == 3
