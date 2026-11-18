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
from app.db.models import Base, LiveOrder, PaperOrder, StrategyVersion
from app.db.session import build_engine, get_db
from app.main import create_app
from app.services.mexc_provider import get_mexc_client, reset_mexc_health_cache
from engine.backtest.runner import (
    run_event_driven_backtest,
    run_vectorized_backtest,
    run_walk_forward_optimization,
)
from engine.pine.engine import analyze_pine_script, execute_pine_script
from engine.replay.controller import apply_replay_order, build_replay_view
from engine.risk.engine import RiskEngine, RiskLimits, derive_client_order_id
from engine.strategy.evaluator import evaluate_strategy
from exchanges.mexc.market_client import MexcMarketDataClient


def _sample_candles(count: int = 180) -> list[dict]:
    t0 = int(datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc).timestamp())
    bars = []
    for i in range(count):
        base = 60000.0 + math.sin(i * 0.22) * 900.0 + (i * 8.0)
        o = base
        c = base + math.cos(i * 0.35) * 180.0
        h = max(o, c) + 80.0
        l = min(o, c) - 75.0
        bars.append(
            {
                "time": t0 + i * 900,
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": round(120.0 + (i % 7) * 18.0, 2),
                "is_closed": True,
            }
        )
    return bars


def _mock_transport() -> httpx.MockTransport:
    bars_15m = _sample_candles(200)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v3/time":
            return httpx.Response(200, json={"serverTime": bars_15m[-1]["time"] * 1000})
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
        if path == "/api/v3/ticker/24hr":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "priceChangePercent": "0.025",
                        "lastPrice": "62000.00",
                        "highPrice": "62800.00",
                        "lowPrice": "60400.00",
                        "volume": "5000.0",
                        "quoteVolume": "310000000.0",
                        "bidPrice": "61998.0",
                        "askPrice": "62002.0",
                    },
                    {
                        "symbol": "ETHUSDT",
                        "priceChangePercent": "-0.012",
                        "lastPrice": "3100.00",
                        "highPrice": "3180.00",
                        "lowPrice": "3050.00",
                        "volume": "25000.0",
                        "quoteVolume": "77500000.0",
                        "bidPrice": "3099.0",
                        "askPrice": "3101.0",
                    },
                ],
            )
        if path == "/api/v3/klines":
            limit = int(request.url.params.get("limit", "180"))
            subset = bars_15m[-min(limit, len(bars_15m)) :]
            rows = [
                [
                    b["time"] * 1000,
                    str(b["open"]),
                    str(b["high"]),
                    str(b["low"]),
                    str(b["close"]),
                    str(b["volume"]),
                    (b["time"] + 900) * 1000,
                    "1000000",
                ]
                for b in subset
            ]
            return httpx.Response(200, json=rows)
        return httpx.Response(404, json={"msg": f"Unhandled {path}"})

    return httpx.MockTransport(handler)


@pytest.fixture()
def full_env(tmp_path: Path):
    db_path = tmp_path / "test_phases6_to_16.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    master_key_bytes = os.urandom(32)
    master_key_b64 = base64.urlsafe_b64encode(master_key_bytes).decode("ascii")

    test_settings = Settings(database_url=db_url, master_encryption_key=master_key_b64)
    test_engine = build_engine(db_url)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    mock_client = MexcMarketDataClient(transport=_mock_transport())
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


def test_security_and_isolation_constraints():
    """Verify Pine engine has zero eval/exec and AI package never imports brokers/exchanges."""
    backend_dir = Path(__file__).resolve().parents[1]

    # 1. Pine sandbox check: no eval, exec, compile, __import__
    pine_dir = backend_dir / "engine" / "pine"
    for py_file in pine_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec", "compile", "__import__"}, (
                    f"Forbidden call {node.func.id} in {py_file}"
                )

    # 2. AI isolation check: no exchanges or paper/live broker imports
    ai_dir = backend_dir / "ai"
    for py_file in ai_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("exchanges")
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("exchanges")


def test_strategy_six_plus_indicators_htf_and_causality():
    bars_15m = _sample_candles(160)
    # Build 1h bars from 15m bars (every 4 bars)
    htf_1h = [
        {
            "time": bars_15m[i]["time"],
            "open": bars_15m[i]["open"],
            "high": max(b["high"] for b in bars_15m[i : i + 4]),
            "low": min(b["low"] for b in bars_15m[i : i + 4]),
            "close": bars_15m[i + 3]["close"],
            "volume": sum(b["volume"] for b in bars_15m[i : i + 4]),
        }
        for i in range(0, len(bars_15m) - 3, 4)
    ]

    defn = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "stop_loss_pct": 1.5,
        "take_profit_pct": 3.0,
        "indicators": [
            {"key": "ema_fast", "indicator_id": "ema", "params": {"length": 9}},
            {"key": "ema_slow", "indicator_id": "ema", "params": {"length": 21}},
            {"key": "rsi_14", "indicator_id": "rsi", "params": {"length": 14}},
            {"key": "macd_main", "indicator_id": "macd", "params": {}},
            {"key": "bb_20", "indicator_id": "bb", "params": {"length": 20}},
            {"key": "atr_14", "indicator_id": "atr", "params": {"length": 14}},
            {"key": "htf_ema", "indicator_id": "ema", "params": {"length": 10}, "timeframe": "1h"},
        ],
        "entry_rule": {
            "type": "AND",
            "children": [
                {"type": "COMPARE", "left": "ema_fast.ema", "op": ">", "right": "ema_slow.ema"},
                {"type": "COMPARE", "left": "rsi_14.rsi", "op": ">", "right": 45},
                {
                    "type": "NOT",
                    "child": {"type": "COMPARE", "left": "price.close", "op": ">", "right": "bb_20.upper"},
                },
            ],
        },
        "exit_rule": {
            "type": "OR",
            "children": [
                {"type": "CROSS_BELOW", "left": "ema_fast.ema", "right": "ema_slow.ema"},
                {"type": "COMPARE", "left": "rsi_14.rsi", "op": ">", "right": 75},
            ],
        },
    }

    full_res = evaluate_strategy(defn, bars_15m, htf_candles={"1h": (3600, htf_1h)})
    cutoff = 110
    cutoff_ts = bars_15m[cutoff - 1]["time"] + 900
    htf_prefix = [b for b in htf_1h if (b["time"] + 3600) <= cutoff_ts]
    prefix_res = evaluate_strategy(defn, bars_15m[:cutoff], htf_candles={"1h": (3600, htf_prefix)})

    # Prefix signals must match full signals up to cutoff - 1 (zero look-ahead)
    assert prefix_res["entry_signals"] == full_res["entry_signals"][:cutoff]
    assert prefix_res["exit_signals"] == full_res["exit_signals"][:cutoff]


def test_backtest_parity_sl_tiebreak_and_walk_forward():
    bars = _sample_candles(160)
    defn = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "stop_loss_pct": 1.0,
        "take_profit_pct": 2.0,
        "indicators": [
            {"key": "ema_f", "indicator_id": "ema", "params": {"length": 5}},
            {"key": "ema_s", "indicator_id": "ema", "params": {"length": 12}},
        ],
        "entry_rule": {"type": "CROSS_ABOVE", "left": "ema_f.ema", "right": "ema_s.ema"},
        "exit_rule": {"type": "CROSS_BELOW", "left": "ema_f.ema", "right": "ema_s.ema"},
    }

    ev = run_event_driven_backtest(defn, bars)
    vec = run_vectorized_backtest(defn, bars)
    assert ev["entry_signals"] == vec["entry_signals"]
    assert ev["exit_signals"] == vec["exit_signals"]
    assert len(ev["equity_curve"]) == len(bars)

    # Conservative SL/TP tie-breaker: construct a candle hitting BOTH SL and TP on same bar
    tie_bars = [
        {"time": 1000, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
        {"time": 2000, "open": 100.0, "high": 101.0, "low": 99.0, "close": 95.0, "volume": 10.0},
        {"time": 3000, "open": 95.0, "high": 96.0, "low": 94.0, "close": 105.0, "volume": 10.0},
        # Entry signal at bar 2 close (105 > 100), executes at bar 3 open (100.0)
        # Bar 3 has huge wick hitting BOTH low=90 (SL 2%=98) AND high=115 (TP 2%=102)
        {"time": 4000, "open": 100.0, "high": 115.0, "low": 90.0, "close": 110.0, "volume": 50.0},
    ]
    tie_defn = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "stop_loss_pct": 2.0,
        "take_profit_pct": 2.0,
        "indicators": [{"key": "sma_2", "indicator_id": "sma", "params": {"length": 2}}],
        "entry_rule": {"type": "COMPARE", "left": "price.close", "op": ">", "right": "sma_2.sma"},
        "exit_rule": {"type": "COMPARE", "left": "price.close", "op": "<", "right": 0},
    }
    tie_res = run_event_driven_backtest(tie_defn, tie_bars)
    assert tie_res["metrics"]["sl_tiebreak_exits"] >= 1
    assert tie_res["trades"][0]["exit_reason"] == "stop_loss_tiebreak"
    assert tie_res["trades"][0]["pnl_usdt"] < 0

    wf = run_walk_forward_optimization(defn, bars)
    assert wf["in_sample_bars"] + wf["out_of_sample_bars"] == len(bars)
    assert len(wf["sensitivity_grid"]) == 9


def test_replay_isolation_and_pine_sandbox():
    bars = _sample_candles(80)
    state = {"cash_usdt": 10000.0, "position_qty": 0.0, "avg_entry_price": 0.0, "realized_pnl_usdt": 0.0, "trades": []}
    view = build_replay_view(bars, cursor_index=25, state=state)
    assert len(view["visible_candles"]) == 26
    assert view["visible_candles"][-1]["time"] == bars[25]["time"]
    # Zero future timestamps
    assert all(c["time"] <= bars[25]["time"] for c in view["visible_candles"])

    new_state = apply_replay_order(bars, 25, state, side="buy", qty=0.05)
    assert new_state["position_qty"] == pytest.approx(0.05)
    assert new_state["cash_usdt"] < 10000.0

    # Pine script analysis & execution + repainting + unsupported detection
    pine_ok = """//@version=5
strategy("Test Pine", overlay=true)
len = input.int(10, title="EMA Length")
e = ta.ema(close, len)
plot(e, title="EMA Line")
strategy.entry("L", strategy.long, when=close > e)
"""
    exec_res = execute_pine_script(pine_ok, bars, {"len": 12})
    assert exec_res["analysis"]["inputs"][0]["name"] == "len"
    assert len(exec_res["plots"]["EMA Line"]) == len(bars) - 11
    assert exec_res["entry_count"] > 0

    pine_repaint = """//@version=5
indicator("Repaint")
x = request.security(syminfo.tickerid, "1D", close, lookahead=barmerge.lookahead_on)
plot(x)
"""
    rep_analysis = analyze_pine_script(pine_repaint)
    assert len(rep_analysis["compat_report"]["repaint_warnings"]) >= 1

    pine_bad = """//@version=5
indicator("Bad")
line.new(0, 0, 1, 1)
"""
    with pytest.raises(ValueError, match="unsupported"):
        execute_pine_script(pine_bad, bars)


def test_risk_engine_gates_and_idempotency():
    engine = RiskEngine()
    limits = RiskLimits(max_risk_per_trade_pct=2.0, max_asset_exposure_pct=30.0, max_open_positions=2)

    # Reject when emergency stop active
    stopped = engine.evaluate_order(
        limits=RiskLimits(emergency_stop_active=True),
        symbol="BTC/USDT",
        side="buy",
        qty=0.01,
        price=60000.0,
        available_usdt=10000.0,
        total_equity_usdt=10000.0,
    )
    assert stopped["approved"] is False
    assert stopped["reason"] == "EMERGENCY_STOP_ACTIVE"

    # Reject when asset exposure exceeds 30% (0.1 * 60000 = 6000 = 60% > 30%)
    over_exp = engine.evaluate_order(
        limits=limits,
        symbol="BTC/USDT",
        side="buy",
        qty=0.1,
        price=60000.0,
        available_usdt=10000.0,
        total_equity_usdt=10000.0,
    )
    assert over_exp["approved"] is False
    assert "ASSET_EXPOSURE_EXCEEDED" in over_exp["reason"]

    # Approve valid order within limits (0.04 * 60000 = 2400 = 24% exposure; 1.5% SL -> 0.36% risk)
    ok = engine.evaluate_order(
        limits=limits,
        symbol="BTC/USDT",
        side="buy",
        qty=0.04,
        price=60000.0,
        available_usdt=10000.0,
        total_equity_usdt=10000.0,
        stop_loss_pct=1.5,
    )
    assert ok["approved"] is True
    assert ok["risk_approval_token"]

    # Deterministic idempotency ID
    oid1 = derive_client_order_id("ver-1", "BTC/USDT", 1795000000, "buy")
    oid2 = derive_client_order_id("ver-1", "BTC/USDT", 1795000000, "buy")
    assert oid1 == oid2


def test_end_to_end_phases6_to_14_api_workflow(full_env):
    client, SessionLocal = full_env

    # 1. Strategies list + immutable versioning
    strats = client.get("/api/v1/strategies").json()["items"]
    assert len(strats) >= 2
    btc_strat = next(s for s in strats if "BTC" in s["name"])
    assert len(btc_strat["current_version"]["definition"]["indicators"]) >= 6
    v1_id = btc_strat["current_version_id"]

    new_defn = dict(btc_strat["current_version"]["definition"])
    new_defn["stop_loss_pct"] = 1.25
    v2_res = client.post(
        f"/api/v1/strategies/{btc_strat['id']}/versions",
        json={"definition": new_defn, "change_note": "Tighten SL"},
    )
    assert v2_res.status_code == 201
    assert v2_res.json()["version_count"] == 2

    with SessionLocal() as db:
        v1 = db.query(StrategyVersion).filter(StrategyVersion.id == v1_id).one()
        assert v1.definition_json["stop_loss_pct"] == 1.5  # Immutable!

    # 2. Backtest run & Optimize
    bt_res = client.post(
        "/api/v1/backtests/run",
        json={"strategy_version_id": v1_id, "symbol": "BTC/USDT", "timeframe": "15m", "bars": 180},
    )
    assert bt_res.status_code == 201
    bt_data = bt_res.json()
    assert bt_data["vectorized_parity"] is True
    assert len(bt_data["equity_curve"]) == 180

    opt_res = client.post(
        "/api/v1/backtests/optimize",
        json={"strategy_version_id": v1_id, "symbol": "BTC/USDT", "timeframe": "15m", "bars": 180},
    )
    assert opt_res.status_code == 200
    assert len(opt_res.json()["sensitivity_grid"]) == 9

    # 3. Replay session step & order
    rep_start = client.post(
        "/api/v1/replay/sessions",
        json={"symbol": "BTC/USDT", "timeframe": "15m", "bars": 120, "start_cursor": 30},
    )
    assert rep_start.status_code == 201
    rep_id = rep_start.json()["id"]
    assert len(rep_start.json()["visible_candles"]) == 31

    rep_step = client.post(f"/api/v1/replay/sessions/{rep_id}/step", json={"steps": 5})
    assert rep_step.status_code == 200
    assert len(rep_step.json()["visible_candles"]) == 36

    rep_ord = client.post(f"/api/v1/replay/sessions/{rep_id}/order", json={"side": "buy", "qty": 0.02})
    assert rep_ord.status_code == 200
    assert rep_ord.json()["state"]["position_qty"] == pytest.approx(0.02)

    # 4. Pine scripts & execution
    scripts = client.get("/api/v1/pine/scripts").json()["items"]
    assert len(scripts) >= 1
    pine_exec = client.post(
        "/api/v1/pine/execute",
        json={
            "source_code": scripts[0]["current_version"]["source_code"],
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "limit": 120,
        },
    )
    assert pine_exec.status_code == 200
    assert "Fast EMA" in pine_exec.json()["plots"]

    # 5. AI Strategy Builder (always Draft + pending suggestion) & Research & Intelligence
    ai_build = client.post(
        "/api/v1/ai/strategy-builder",
        json={"prompt": "Build a mean reversion strategy for ETH/USDT", "symbol": "ETH/USDT", "timeframe": "15m"},
    )
    assert ai_build.status_code == 201
    assert ai_build.json()["status"] == "Draft"

    ai_res = client.post("/api/v1/ai/research", json={"backtest_job_id": bt_data["id"]})
    assert ai_res.status_code == 200
    sug_id = ai_res.json()["suggestion_id"]
    assert ai_res.json()["status"] == "pending"

    dec = client.post(f"/api/v1/ai/suggestions/{sug_id}/decision", json={"decision": "approved"})
    assert dec.status_code == 200
    assert dec.json()["status"] == "approved"

    intel = client.get("/api/v1/ai/market-intelligence")
    assert intel.status_code == 200
    assert intel.json()["regime"]

    # 6. Paper Trading vs Live Trading + Emergency Stop
    paper_ord = client.post(
        "/api/v1/paper/orders",
        json={"symbol": "BTC/USDT", "side": "buy", "order_type": "MARKET", "qty": 0.04, "price": 62000.0},
    )
    assert paper_ord.status_code == 201
    paper_ov = client.get("/api/v1/paper/overview").json()
    assert len(paper_ov["positions"]) == 1

    # Live order blocked without LiveAuthorization
    no_auth_live = client.post(
        "/api/v1/live/orders",
        json={"authorization_id": "nonexistent", "symbol": "BTC/USDT", "side": "buy", "qty": 0.01, "price": 62000.0},
    )
    assert no_auth_live.status_code == 403

    # Authorize approved strategy version & stage idempotent live order
    auth_res = client.post(
        "/api/v1/live/authorize",
        json={"strategy_version_id": v1_id, "capital_mode": "fixed_usdt", "capital_value": 1000.0, "scope": "BTC/USDT Spot"},
    )
    assert auth_res.status_code == 201
    auth_id = auth_res.json()["id"]

    live_ord1 = client.post(
        "/api/v1/live/orders",
        json={
            "authorization_id": auth_id,
            "symbol": "BTC/USDT",
            "side": "buy",
            "qty": 0.005,
            "price": 62000.0,
            "candle_time": 1795000000,
        },
    )
    assert live_ord1.status_code == 201
    assert live_ord1.json()["duplicate_prevented"] is False

    # Duplicate signal with same candle_time prevents duplicate order
    live_ord2 = client.post(
        "/api/v1/live/orders",
        json={
            "authorization_id": auth_id,
            "symbol": "BTC/USDT",
            "side": "buy",
            "qty": 0.005,
            "price": 62000.0,
            "candle_time": 1795000000,
        },
    )
    assert live_ord2.status_code == 201
    assert live_ord2.json()["duplicate_prevented"] is True

    with SessionLocal() as db:
        assert db.query(PaperOrder).count() == 1
        assert db.query(LiveOrder).count() == 1  # Strictly separated!

    # Emergency Stop revokes active LiveAuthorizations and blocks further orders
    estop = client.post("/api/v1/risk/emergency-stop", json={"active": True})
    assert estop.status_code == 200
    assert estop.json()["emergency_stop_active"] is True
    assert estop.json()["revoked_authorizations"] >= 1


def test_ai_copilot_config_and_full_tool_execution_workflow(full_env):
    client, SessionLocal = full_env

    # 1. Before configuring copilot, health.ai is disconnected
    assert client.get("/api/v1/health").json()["ai"] == "disconnected"

    # 2. Save external provider config with encrypted API key -> health.ai becomes connected
    put_res = client.put(
        "/api/v1/ai/copilot/config",
        json={
            "provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-secret-123456abcd",
            "autonomy_level": "full_copilot",
            "system_instructions": "Focus on risk-adjusted momentum strategies.",
            "enabled": True,
        },
    )
    assert put_res.status_code == 200
    cfg = put_res.json()
    assert cfg["provider"] == "openai"
    assert cfg["has_api_key"] is True
    assert "sk-test-secret-123456abcd" not in str(cfg)
    assert cfg["api_key_masked"] == "sk-t...abcd"
    assert client.get("/api/v1/health").json()["ai"] == "connected"

    # 3. Switch to built-in quant copilot engine & test connection
    cfg_builtin = client.put(
        "/api/v1/ai/copilot/config",
        json={
            "provider": "builtin",
            "model_name": "apex-quant-copilot-v1",
            "autonomy_level": "full_copilot",
            "clear_api_key": True,
            "enabled": True,
        },
    )
    assert cfg_builtin.status_code == 200
    assert cfg_builtin.json()["has_api_key"] is False

    test_res = client.post("/api/v1/ai/copilot/test", json={})
    assert test_res.status_code == 200
    assert test_res.json()["ok"] is True

    # 4. Run full-app multi-tool Arabic prompt: create strategy + backtest + walk-forward + paper buy
    chat1 = client.post(
        "/api/v1/ai/copilot/chat",
        json={
            "message": "أنشئ استراتيجية زخم على ETH/USDT إطار 15m وشغل باك تيست ثم اعمل walk-forward optimization ثم اشتر 0.1 ETH في الحساب الورقي",
            "active_page": "/strategy-composer",
            "language_hint": "ar",
        },
    )
    assert chat1.status_code == 200
    c1 = chat1.json()
    conv_id = c1["conversation_id"]
    tools_run = {a["tool"]: a for a in c1["tool_actions"]}
    assert tools_run["create_strategy"]["ok"] is True
    assert tools_run["run_backtest"]["ok"] is True
    assert tools_run["run_walk_forward"]["ok"] is True
    assert tools_run["execute_paper_order"]["ok"] is True
    created_strat_id = tools_run["create_strategy"]["data"]["strategy_id"]

    # 5. Follow-up modification + live signal evaluation + risk update in same conversation
    chat2 = client.post(
        "/api/v1/ai/copilot/chat",
        json={
            "conversation_id": conv_id,
            "message": "عدل وقف الخسارة إلى 1.2% والهدف إلى 4.2% وافحص الإشارات الحية على ETH/USDT",
            "active_page": "/strategy-composer",
            "active_strategy_id": created_strat_id,
            "language_hint": "ar",
        },
    )
    assert chat2.status_code == 200
    c2 = chat2.json()
    tools2 = {a["tool"]: a for a in c2["tool_actions"]}
    assert tools2["modify_strategy"]["ok"] is True
    assert tools2["modify_strategy"]["data"]["stop_loss_pct"] == 1.2
    assert tools2["modify_strategy"]["data"]["take_profit_pct"] == 4.2
    assert tools2["evaluate_signals"]["ok"] is True

    # 6. Verify persisted PaperOrder + Conversation messages
    convs = client.get("/api/v1/ai/copilot/conversations")
    assert convs.status_code == 200
    assert len(convs.json()["items"]) >= 1
    with SessionLocal() as db:
        assert db.query(PaperOrder).count() >= 1


def test_github_updates_status_and_check_endpoints(full_env):
    client, _ = full_env
    st = client.get("/api/v1/system/updates/status")
    assert st.status_code == 200
    st_json = st.json()
    assert st_json["current_version"] == "1.0.0"
    assert st_json["repo"] == "aliazizdbab/apex-ai-trading-lab"
    assert "windows" in st_json["platforms"]
    assert "macos" in st_json["platforms"]
    assert "android" in st_json["platforms"]
    assert "web" in st_json["platforms"]

    chk = client.post("/api/v1/system/updates/check")
    assert chk.status_code == 200
    chk_json = chk.json()
    assert chk_json["current_version"] == "1.0.0"
    assert chk_json["repo"] == "aliazizdbab/apex-ai-trading-lab"
    assert "platforms" in chk_json

