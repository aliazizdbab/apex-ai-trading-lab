# APEX AI Trading Lab — Architecture & Engineering Decisions

This record captures the concrete engineering decisions implemented across Phases 1–16 of **APEX AI Trading Lab**.

1. **MEXC Spot Real-Data Provider + Token-Bucket Limiter (`backend/exchanges/mexc/`)**:
   - All market tickers, order books, recent trades, OHLCV klines, and symbol precision rules come from live MEXC Spot APIv3 (`https://api.mexc.com`) and WebSockets.
   - Local rate limiter (`rate_limiter.py`) enforces request budgeting; `order_rules.py` normalizes step sizes and tick precision before order validation.
2. **Dual Database Portability (`backend/app/db/` + `deploy/docker-compose.yml`)**:
   - Schema (`0001_phase2_foundation`, `0002_phase4_5_indicators`, `0003_phases6_to_16_complete`) runs cleanly on local SQLite (`apex_local.db`) for zero-Docker Windows workstation workflows while keeping PostgreSQL 16 + Redis 7 containerized configuration ready in `deploy/docker-compose.yml`.
   - Single-owner workstation mode makes `owner_id` nullable on single-owner operational tables (`risk_profiles`, `paper_accounts`, `live_authorizations`, `live_orders`), protected by Fernet API secret encryption (`backend/app/core/crypto.py`) and explicit unencrypted-localhost warnings on live execution screens.
3. **Custom Quantitative Engine Over Pure Historical Candles (`backend/engine/`)**:
   - **Indicators (`engine/indicators/compute.py`)**: 10 deterministic indicators + Heikin Ashi transform.
   - **Strategy Evaluator (`engine/strategy/evaluator.py`)**: Supports 6+ indicators, nested boolean/threshold/cross rule trees, `closed_candle` vs `intrabar` modes, and strictly causal Higher-Timeframe (HTF) alignment (only completed HTF bars mapped onto LTF timestamps).
   - **Backtester (`engine/backtest/runner.py`)**: Event-driven bar-by-bar execution with vectorized approximation parity check, conservative stop-loss tie-breaking (`sl_tiebreak_exits`) when both SL and TP hit within the same candle, plus Walk-Forward (70% In-Sample / 30% Out-of-Sample) optimization with overfitting detection.
4. **Zero-Future-Leakage Bar Replay (`backend/engine/replay/controller.py`)**:
   - Server owns the canonical OHLCV array and `cursor_index`. Responses slice `candles[:cursor_index + 1]` on the server so unrevealed future bars are never transmitted to the client.
5. **Safe Sandboxed Pine Engine (`backend/engine/pine/engine.py`)**:
   - AST-based tree-walking interpreter with zero `eval()`/`exec()`. Detects repaint hazards (`barmerge.lookahead_on`, `barstate.isrealtime`, `barstate.islast`) and explicitly blocks unsupported drawing/collection calls (`line.new`, `array.new`, `matrix.new`, etc.).
6. **AI Provider Abstraction With Strict Non-Autonomy (`backend/ai/provider.py`)**:
   - Zero imports from `exchanges/` or execution clients inside `backend/ai/` and `backend/engine/`.
   - AI outputs (`Strategy` / `AiSuggestion`) are persisted only as `Draft` strategies and `pending` suggestions and can never place real orders without explicit owner authorization and risk clearance.
7. **Strict Paper vs Live Execution Isolation & Mandatory Risk Engine (`backend/engine/risk/`, `backend/app/api/trading_risk.py`)**:
   - Separate tables (`paper_accounts`, `paper_orders`, `paper_trades` vs `live_authorizations`, `live_orders`, `live_trades`) and distinct UI tabs/indicators (`Paper Virtual` vs `Real Live`).
   - Every live order requires: active `Emergency Stop == False`, active owner `LiveAuthorization`, passing `RiskEngine` limits (position cap, exposure %, trade risk %, daily/weekly/drawdown caps, symbol precision), and an idempotent SHA-256 `clientOrderId` (`derive_client_order_id`).
   - Activating Emergency Stop revokes all active live authorizations in the database atomically and creates an immutable audit trail event.
8. **Desktop Shell Option (`desktop/`)**:
   - Added Tauri v2 configuration (`desktop/Cargo.toml`, `desktop/tauri.conf.json`, `desktop/src/main.rs`) bundling `../frontend/dist` and spawning the local FastAPI sidecar (`127.0.0.1:8000`). (Compiling the native binary requires installing the Rust toolchain / `cargo`, which is optional alongside standard browser mode.)
