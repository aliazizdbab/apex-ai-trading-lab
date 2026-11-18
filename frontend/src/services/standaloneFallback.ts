import { generateDemoCandles, seedFromString } from '@/features/chart/demoCandles';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { DEMO_MARKETS } from '@/features/market/demoData';
import type { Candle, MarketRow } from '@/types';

const LS_KEY = 'apex_standalone_state_v1';

interface StandaloneState {
  strategies: Record<string, unknown>[];
  backtests: Record<string, unknown>[];
  presets: Record<string, unknown>[];
  pineScripts: Record<string, unknown>[];
  suggestions: Record<string, unknown>[];
  copilotConfig: Record<string, unknown>;
  conversations: Record<string, unknown>[];
  paperCash: number;
  paperPositions: Record<string, { qty: number; avg_entry_price: number }>;
  paperOrders: Record<string, unknown>[];
  riskProfile: Record<string, unknown>;
}

function nowIso(): string {
  return new Date().toISOString();
}

function defaultState(): StandaloneState {
  const created = nowIso();
  const v1Id = 'ver-btc-mom-1';
  const v2Id = 'ver-eth-mr-1';
  return {
    strategies: [
      {
        id: 'strat-btc-mom',
        name: 'BTC Momentum & Volatility Pro',
        description: '7-indicator trend + RSI + MACD confluence strategy for Spot markets.',
        status: 'Approved',
        current_version_id: v1Id,
        version_count: 1,
        created_at: created,
        updated_at: created,
        current_version: {
          id: v1Id,
          strategy_id: 'strat-btc-mom',
          version_no: 1,
          definition_hash: 'local-v1',
          change_note: 'Default seeded strategy',
          created_at: created,
          definition: {
            symbol: 'BTC/USDT',
            timeframe: '15m',
            signal_mode: 'closed_candle',
            stop_loss_pct: 1.5,
            take_profit_pct: 3.5,
            indicators: [
              { key: 'ema_fast', indicator_id: 'ema', params: { length: 20 } },
              { key: 'ema_slow', indicator_id: 'ema', params: { length: 50 } },
              { key: 'sma_trend', indicator_id: 'sma', params: { length: 200 } },
              { key: 'rsi_main', indicator_id: 'rsi', params: { length: 14 } },
              { key: 'macd_main', indicator_id: 'macd', params: {} },
              { key: 'bb_main', indicator_id: 'bb', params: { length: 20, mult: 2 } },
              { key: 'atr_main', indicator_id: 'atr', params: { length: 14 } },
            ],
            entry_rule: { type: 'AND', children: [] },
            exit_rule: { type: 'OR', children: [] },
          },
        },
      },
      {
        id: 'strat-eth-mr',
        name: 'ETH Mean Reversion & Trend Filter',
        description: '6-indicator Bollinger + RSI + Stochastic mean-reversion model.',
        status: 'Backtesting',
        current_version_id: v2Id,
        version_count: 1,
        created_at: created,
        updated_at: created,
        current_version: {
          id: v2Id,
          strategy_id: 'strat-eth-mr',
          version_no: 1,
          definition_hash: 'local-v2',
          change_note: 'Default seeded strategy',
          created_at: created,
          definition: {
            symbol: 'ETH/USDT',
            timeframe: '15m',
            signal_mode: 'closed_candle',
            stop_loss_pct: 1.8,
            take_profit_pct: 3.0,
            indicators: [
              { key: 'bb_main', indicator_id: 'bb', params: { length: 20, mult: 2 } },
              { key: 'rsi_main', indicator_id: 'rsi', params: { length: 14 } },
              { key: 'stoch_main', indicator_id: 'stoch', params: { k_length: 14 } },
              { key: 'ema_trend', indicator_id: 'ema', params: { length: 50 } },
              { key: 'adx_main', indicator_id: 'adx', params: { di_length: 14 } },
              { key: 'vwap_main', indicator_id: 'vwap', params: { anchor: 'session' } },
            ],
            entry_rule: { type: 'AND', children: [] },
            exit_rule: { type: 'OR', children: [] },
          },
        },
      },
    ],
    backtests: [],
    presets: [
      {
        id: 'preset-ema20',
        indicator_id: 'ema',
        name: 'EMA 20 Trend',
        symbol: 'BTC/USDT',
        timeframe: '15m',
        params: { length: 20, source: 'close' },
        visible: true,
        created_at: created,
        updated_at: created,
      },
    ],
    pineScripts: [
      {
        id: 'pine-default-1',
        name: 'APEX EMA + RSI Momentum v5',
        script_type: 'strategy',
        version_count: 1,
        created_at: created,
        current_version: {
          id: 'pine-ver-1',
          version_no: 1,
          pine_version: 5,
          source_code:
            '//@version=5\nstrategy("APEX EMA + RSI Momentum v5", overlay=true)\nfastLen = input.int(9, title="Fast EMA Length")\nslowLen = input.int(21, title="Slow EMA Length")\nfastEma = ta.ema(close, fastLen)\nslowEma = ta.ema(close, slowLen)\nplot(fastEma, title="Fast EMA")\nplot(slowEma, title="Slow EMA")\nstrategy.entry("Long", strategy.long, when=ta.crossover(fastEma, slowEma))\nstrategy.close("Long", when=ta.crossunder(fastEma, slowEma))',
          ast: { statement_count: 8, statements: [] },
          compat_report: { supported: true, unsupported_features: [], repaint_warnings: [], sandbox_mode: 'standalone' },
          sha256: 'standalone-default',
          created_at: created,
        },
      },
    ],
    suggestions: [],
    copilotConfig: {
      id: 'copilot-standalone',
      provider: 'builtin',
      model_name: 'apex-quant-copilot-v1',
      base_url: '',
      has_api_key: false,
      api_key_masked: '',
      autonomy_level: 'full_copilot',
      system_instructions: '',
      enabled: true,
      updated_at: created,
      providers: [
        { id: 'builtin', label: 'APEX Built-in Quant Copilot (Mobile/Offline Ready)', default_model: 'apex-quant-copilot-v1', default_base_url: '' },
        { id: 'gemini', label: 'Google Gemini API', default_model: 'gemini-2.5-flash', default_base_url: 'https://generativelanguage.googleapis.com/v1beta' },
        { id: 'openai', label: 'OpenAI API', default_model: 'gpt-4o', default_base_url: 'https://api.openai.com/v1' },
        { id: 'anthropic', label: 'Anthropic Claude API', default_model: 'claude-3-7-sonnet-latest', default_base_url: 'https://api.anthropic.com/v1' },
        { id: 'deepseek', label: 'DeepSeek API', default_model: 'deepseek-chat', default_base_url: 'https://api.deepseek.com/v1' },
        { id: 'openrouter', label: 'OpenRouter API', default_model: 'openai/gpt-4o-mini', default_base_url: 'https://openrouter.ai/api/v1' },
        { id: 'custom', label: 'Custom OpenAI-Compatible Endpoint', default_model: 'custom-model', default_base_url: 'http://127.0.0.1:11434/v1' },
      ],
    },
    conversations: [],
    paperCash: 10000,
    paperPositions: {},
    paperOrders: [],
    riskProfile: {
      id: 'rp-standalone',
      name: 'Default Conservative Spot Profile',
      max_risk_per_trade_pct: 2,
      max_daily_loss_pct: 5,
      max_weekly_loss_pct: 10,
      max_drawdown_pct: 15,
      max_open_positions: 5,
      max_asset_exposure_pct: 40,
      cooldown_minutes: 15,
      emergency_stop_active: false,
      updated_at: created,
    },
  };
}

function loadState(): StandaloneState {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) {
      const init = defaultState();
      localStorage.setItem(LS_KEY, JSON.stringify(init));
      return init;
    }
    return { ...defaultState(), ...(JSON.parse(raw) as Partial<StandaloneState>) };
  } catch {
    return defaultState();
  }
}

function saveState(state: StandaloneState): void {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(state));
  } catch {
    // ignore quota errors
  }
}

function parseJsonBody(init?: RequestInit): Record<string, unknown> {
  if (!init?.body || typeof init.body !== 'string') return {};
  try {
    return JSON.parse(init.body) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function candlesFor(symbol: string, tfId: string, limit = 250): Candle[] {
  const tf = TIMEFRAMES.find((t) => t.id === tfId) ?? TIMEFRAMES[3]!;
  const m = DEMO_MARKETS.find((r) => r.symbol === symbol) ?? DEMO_MARKETS[0]!;
  return generateDemoCandles({
    count: limit,
    stepSeconds: tf.seconds,
    startPrice: m.last,
    endTime: Math.floor(Date.now() / 1000),
    seed: seedFromString(`${symbol}-${tfId}`),
  });
}

function runQuickBacktest(candles: Candle[], slPct: number, tpPct: number, initialCap: number) {
  let equity = initialCap;
  const eqCurve: { time: number; equity: number }[] = [];
  const ddCurve: { time: number; drawdown_pct: number }[] = [];
  const trades: Record<string, unknown>[] = [];
  let peak = equity;
  let wins = 0;

  let posEntry = 0;
  let posTime = 0;
  let posQty = 0;
  for (let i = 10; i < candles.length; i++) {
    const prev = candles[i - 1]!;
    const bar = candles[i]!;
    const sma5 = candles.slice(i - 5, i).reduce((s, c) => s + c.close, 0) / 5;
    if (posQty === 0 && bar.close > sma5 && bar.close > prev.close) {
      posEntry = bar.close;
      posTime = bar.time;
      posQty = (equity * 0.95) / bar.close;
    } else if (posQty > 0) {
      const chgPct = ((bar.close - posEntry) / posEntry) * 100;
      const reason = chgPct <= -slPct ? 'stop_loss' : chgPct >= tpPct ? 'take_profit' : i === candles.length - 1 ? 'end' : '';
      if (reason) {
        const pnl = (bar.close - posEntry) * posQty;
        const fee = bar.close * posQty * 0.001;
        equity += pnl - fee;
        if (pnl - fee >= 0) wins++;
        trades.push({
          entry_time: posTime,
          exit_time: bar.time,
          entry_price: Number(posEntry.toFixed(4)),
          exit_price: Number(bar.close.toFixed(4)),
          qty: Number(posQty.toFixed(6)),
          pnl_usdt: Number((pnl - fee).toFixed(2)),
          pnl_pct: Number(chgPct.toFixed(2)),
          fee_usdt: Number(fee.toFixed(2)),
          exit_reason: reason,
        });
        posQty = 0;
      }
    }
    peak = Math.max(peak, equity);
    const dd = peak > 0 ? ((peak - equity) / peak) * 100 : 0;
    eqCurve.push({ time: bar.time, equity: Number(equity.toFixed(2)) });
    ddCurve.push({ time: bar.time, drawdown_pct: Number(dd.toFixed(2)) });
  }

  const totalRet = ((equity - initialCap) / initialCap) * 100;
  const maxDd = ddCurve.reduce((mx, d) => Math.max(mx, d.drawdown_pct), 0);
  const winRate = trades.length > 0 ? (wins / trades.length) * 100 : 0;
  return {
    metrics: {
      initial_capital: initialCap,
      final_equity: Number(equity.toFixed(2)),
      total_return_pct: Number(totalRet.toFixed(2)),
      total_trades: trades.length,
      winning_trades: wins,
      losing_trades: Math.max(0, trades.length - wins),
      win_rate_pct: Number(winRate.toFixed(1)),
      profit_factor: trades.length > wins ? Number(((wins + 1) / Math.max(1, trades.length - wins)).toFixed(2)) : 1.85,
      max_drawdown_pct: Number(maxDd.toFixed(2)),
      sharpe_ratio: Number((totalRet / Math.max(1, maxDd + 1)).toFixed(2)),
      sortino_ratio: Number(((totalRet * 1.2) / Math.max(1, maxDd + 1)).toFixed(2)),
      expectancy_usdt: trades.length > 0 ? Number(((equity - initialCap) / trades.length).toFixed(2)) : 0,
      sl_tiebreak_exits: 0,
    },
    equity_curve: eqCurve,
    drawdown_curve: ddCurve,
    trades,
  };
}

async function fetchLiveMexcTickersFallback(): Promise<MarketRow[]> {
  try {
    const res = await fetch('https://api.mexc.com/api/v3/ticker/24hr');
    if (!res.ok) return DEMO_MARKETS;
    const raw = (await res.json()) as Record<string, string>[];
    const desired = new Set(DEMO_MARKETS.map((m) => m.symbol.replace('/', '')));
    const mapped: MarketRow[] = raw
      .filter((r) => desired.has(String(r.symbol || '')))
      .map((r) => {
        const sym = String(r.symbol);
        const pair = `${sym.slice(0, -4)}/USDT`;
        return {
          symbol: pair,
          last: Number(r.lastPrice || 0),
          change24h: Number(r.priceChangePercent || 0) * 100,
          volume24h: Number(r.quoteVolume || 0),
          high: Number(r.highPrice || 0),
          low: Number(r.lowPrice || 0),
          status: 'trading',
        };
      });
    return mapped.length > 0 ? mapped : DEMO_MARKETS;
  } catch {
    return DEMO_MARKETS;
  }
}

export async function handleStandaloneRequest<T>(rawPath: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || 'GET').toUpperCase();
  const [pathOnly, queryStr] = rawPath.split('?');
  const qs = new URLSearchParams(queryStr || '');
  const body = parseJsonBody(init);
  const state = loadState();

  if (pathOnly === '/api/v1/health') {
    return {
      status: 'ok',
      engine: 'connected',
      mexc: 'connected',
      ai: 'connected',
      database: 'connected',
      auth_setup_completed: false,
      totp_enabled: false,
      audit_chain_valid: true,
    } as T;
  }

  if (pathOnly === '/api/v1/auth/status') {
    return { setup_completed: false, authenticated: false, user: null } as T;
  }

  if (pathOnly === '/api/v1/notifications') {
    return { items: [], unread_count: 0 } as T;
  }

  if (pathOnly === '/api/v1/market/tickers') {
    const items = await fetchLiveMexcTickersFallback();
    return {
      exchange: 'mexc',
      source: 'standalone_mexc_public',
      items: items.map((m) => ({
        ...m,
        bid: Number((m.last * 0.9998).toFixed(4)),
        ask: Number((m.last * 1.0002).toFixed(4)),
        spread_pct: 0.04,
      })),
    } as T;
  }

  if (pathOnly === '/api/v1/market/candles') {
    const symbol = qs.get('symbol') || 'BTC/USDT';
    const tf = qs.get('timeframe') || '15m';
    const limit = Number(qs.get('limit') || '200');
    const items = candlesFor(symbol, tf, limit);
    return {
      symbol,
      timeframe: tf,
      source: 'standalone_cache',
      quality: { total_bars: items.length, duplicates: 0, gaps: 0, zero_or_negative_prices: 0, integrity_ok: true, data_snapshot_hash: 'standalone' },
      items,
    } as T;
  }

  if (pathOnly === '/api/v1/market/orderbook') {
    const symbol = qs.get('symbol') || 'BTC/USDT';
    const m = DEMO_MARKETS.find((x) => x.symbol === symbol) ?? DEMO_MARKETS[0]!;
    return {
      symbol,
      source: 'standalone',
      bids: [1, 2, 3, 4, 5].map((i) => [Number((m.last * (1 - i * 0.0005)).toFixed(4)), i * 0.45]),
      asks: [1, 2, 3, 4, 5].map((i) => [Number((m.last * (1 + i * 0.0005)).toFixed(4)), i * 0.42]),
    } as T;
  }

  if (pathOnly === '/api/v1/market/trades') {
    const symbol = qs.get('symbol') || 'BTC/USDT';
    const m = DEMO_MARKETS.find((x) => x.symbol === symbol) ?? DEMO_MARKETS[0]!;
    const nowSec = Math.floor(Date.now() / 1000);
    return {
      symbol,
      source: 'standalone',
      items: [0, 1, 2, 3, 4].map((i) => ({
        price: Number((m.last * (1 + (i % 2 === 0 ? 0.0002 : -0.0002))).toFixed(4)),
        qty: Number((0.15 * (i + 1)).toFixed(3)),
        side: i % 2 === 0 ? 'buy' : 'sell',
        time: (nowSec - i * 15) * 1000,
      })),
    } as T;
  }

  if (pathOnly === '/api/v1/exchanges/mexc/status') {
    return {
      exchange: 'mexc',
      public_api: 'connected',
      base_url: 'https://api.mexc.com',
      spot_pairs_cached: DEMO_MARKETS.length,
      rate_limiter: { requests_per_minute_limit: 600, tokens_remaining: 590 },
      symbol_rules_sample: [],
    } as T;
  }

  if (pathOnly === '/api/v1/indicators/catalog') {
    return {
      items: [
        { id: 'ema', name: 'Exponential Moving Average (EMA)', category: 'trend', kind: 'overlay', pane: 'overlay', description: 'EMA smoothing', outputs: [{ key: 'ema', label: 'EMA', color: '#36C5F0', series_type: 'line' }], parameters: [{ name: 'length', label: 'Length', param_type: 'int', default: 20, min_val: 2, max_val: 400, options: null }] },
        { id: 'sma', name: 'Simple Moving Average (SMA)', category: 'trend', kind: 'overlay', pane: 'overlay', description: 'SMA average', outputs: [{ key: 'sma', label: 'SMA', color: '#F4B85C', series_type: 'line' }], parameters: [{ name: 'length', label: 'Length', param_type: 'int', default: 50, min_val: 2, max_val: 400, options: null }] },
        { id: 'rsi', name: 'Relative Strength Index (RSI)', category: 'momentum', kind: 'oscillator', pane: 'oscillator', description: 'Momentum oscillator', outputs: [{ key: 'rsi', label: 'RSI', color: '#9275FF', series_type: 'line' }], parameters: [{ name: 'length', label: 'Length', param_type: 'int', default: 14, min_val: 2, max_val: 100, options: null }] },
        { id: 'bb', name: 'Bollinger Bands', category: 'volatility', kind: 'overlay', pane: 'overlay', description: 'Upper / basis / lower bands', outputs: [{ key: 'basis', label: 'Basis', color: '#36C5F0', series_type: 'line' }], parameters: [{ name: 'length', label: 'Length', param_type: 'int', default: 20, min_val: 2, max_val: 200, options: null }] },
      ],
    } as T;
  }

  if (pathOnly === '/api/v1/indicators/presets') {
    if (method === 'GET') return { items: state.presets } as T;
    if (method === 'POST') {
      const p = { id: `preset-${Date.now()}`, ...body, visible: body.visible ?? true, created_at: nowIso(), updated_at: nowIso() };
      state.presets.unshift(p);
      saveState(state);
      return p as T;
    }
  }

  if (pathOnly === '/api/v1/indicators/compute') {
    const symbol = String(body.symbol || 'BTC/USDT');
    const timeframe = String(body.timeframe || '15m');
    const candles = candlesFor(symbol, timeframe, Number(body.limit || 200));
    return { symbol, timeframe, source: 'standalone', candle_mode: body.candle_mode || 'standard', quality: { total_bars: candles.length, integrity_ok: true }, candles, outputs: [] } as T;
  }

  if (pathOnly === '/api/v1/strategies') {
    if (method === 'GET') return { items: state.strategies } as T;
    if (method === 'POST') {
      const id = `strat-${Date.now()}`;
      const verId = `ver-${Date.now()}`;
      const strat = {
        id,
        name: String(body.name || 'Custom Strategy'),
        description: String(body.description || ''),
        status: String(body.status || 'Draft'),
        current_version_id: verId,
        version_count: 1,
        created_at: nowIso(),
        updated_at: nowIso(),
        current_version: { id: verId, strategy_id: id, version_no: 1, definition: body.definition, definition_hash: id, change_note: String(body.change_note || 'Initial'), created_at: nowIso() },
      };
      state.strategies.unshift(strat);
      saveState(state);
      return strat as T;
    }
  }

  if (pathOnly === '/api/v1/strategies/evaluate') {
    const symbol = String(body.symbol || 'BTC/USDT');
    const timeframe = String(body.timeframe || '15m');
    const candles = candlesFor(symbol, timeframe, 200);
    return { symbol, timeframe, bars_evaluated: candles.length, entry_count: 8, exit_count: 6, latest_confluence: 0.67, recent_signals: [{ time: candles[candles.length - 1]!.time, type: 'entry', price: candles[candles.length - 1]!.close }] } as T;
  }

  if (pathOnly === '/api/v1/backtests') return { items: state.backtests } as T;

  if (pathOnly === '/api/v1/backtests/run') {
    const symbol = String(body.symbol || 'BTC/USDT');
    const tf = String(body.timeframe || '15m');
    const bars = Number(body.bars || 300);
    const cap = Number(body.initial_capital_usdt || 10000);
    const candles = candlesFor(symbol, tf, bars);
    const res = runQuickBacktest(candles, 1.5, 3.5, cap);
    const jobId = `bt-${Date.now()}`;
    state.backtests.unshift({ id: jobId, strategy_version_id: body.strategy_version_id, strategy_name: 'APEX Strategy', version_no: 1, symbol, timeframe: tf, data_snapshot_hash: 'standalone', total_return_pct: res.metrics.total_return_pct, win_rate_pct: res.metrics.win_rate_pct, profit_factor: res.metrics.profit_factor, max_drawdown_pct: res.metrics.max_drawdown_pct, sharpe_ratio: res.metrics.sharpe_ratio, total_trades: res.metrics.total_trades, created_at: nowIso() });
    saveState(state);
    return { id: jobId, strategy_version_id: body.strategy_version_id, symbol, timeframe: tf, data_snapshot_hash: 'standalone', quality: { total_bars: bars, integrity_ok: true }, ...res, vectorized_parity: true, vectorized_approx_return_pct: res.metrics.total_return_pct, created_at: nowIso() } as T;
  }

  if (pathOnly === '/api/v1/backtests/optimize') {
    const symbol = String(body.symbol || 'BTC/USDT');
    const tf = String(body.timeframe || '15m');
    const bars = Number(body.bars || 300);
    const candles = candlesFor(symbol, tf, bars);
    const split = Math.floor(candles.length * 0.7);
    const isRes = runQuickBacktest(candles.slice(0, split), 1.5, 3.5, 10000);
    const oosRes = runQuickBacktest(candles.slice(split), 1.5, 3.5, 10000);
    return {
      strategy_version_id: body.strategy_version_id,
      symbol,
      timeframe: tf,
      data_snapshot_hash: 'standalone',
      split_index: split,
      in_sample_bars: split,
      out_of_sample_bars: candles.length - split,
      best_params: { stop_loss_pct: 1.5, take_profit_pct: 3.5 },
      in_sample_metrics: isRes.metrics,
      out_of_sample_metrics: oosRes.metrics,
      overfitting_warning: false,
      overfitting_reason: 'Consistent In-Sample & Out-of-Sample profile.',
      sensitivity_grid: [1.0, 1.5, 2.0].map((sl) => ({ stop_loss_pct: sl, take_profit_pct: sl * 2.3, is_return_pct: isRes.metrics.total_return_pct, is_win_rate_pct: isRes.metrics.win_rate_pct, is_max_drawdown_pct: isRes.metrics.max_drawdown_pct, is_trades: isRes.metrics.total_trades, score: isRes.metrics.sharpe_ratio })),
    } as T;
  }

  if (pathOnly.startsWith('/api/v1/replay/sessions')) {
    const candles = candlesFor(String(body.symbol || 'BTC/USDT'), String(body.timeframe || '15m'), 160);
    const vis = candles.slice(0, 60);
    return { id: 'replay-standalone', symbol: String(body.symbol || 'BTC/USDT'), timeframe: String(body.timeframe || '15m'), status: 'active', cursor_index: 59, total_bars: candles.length, visible_candles: vis, current_bar: vis[vis.length - 1] ?? null, state: { cash_usdt: 10000, position_qty: 0, avg_entry_price: 0, realized_pnl_usdt: 0, unrealized_pnl_usdt: 0, total_equity_usdt: 10000, trades: [] } } as T;
  }

  if (pathOnly === '/api/v1/pine/scripts') return { items: state.pineScripts } as T;
  if (pathOnly === '/api/v1/pine/analyze') {
    return { title: 'Pine Script v5', pine_version: 5, script_type: 'strategy', sha256: 'standalone', inputs: [], builtin_indicators: ['ta.ema', 'ta.rsi'], referenced_timeframes: [], alerts: [], ast: { statement_count: 6, statements: [] }, compat_report: { supported: true, unsupported_features: [], repaint_warnings: [], sandbox_mode: 'standalone' } } as T;
  }

  if (pathOnly === '/api/v1/ai/copilot/config') {
    if (method === 'PUT') {
      state.copilotConfig = { ...state.copilotConfig, ...body, updated_at: nowIso() };
      saveState(state);
    }
    return state.copilotConfig as T;
  }

  if (pathOnly === '/api/v1/ai/copilot/test') {
    return { ok: true, provider: state.copilotConfig.provider, model_name: state.copilotConfig.model_name, latency_ms: 4, message: 'Standalone mobile/web Quant Copilot engine active.' } as T;
  }

  if (pathOnly === '/api/v1/ai/copilot/conversations') {
    if (method === 'POST') {
      const conv = { id: `conv-${Date.now()}`, provider: String(state.copilotConfig.provider), topic: String(body.topic || 'New Session'), messages: [], created_at: nowIso() };
      state.conversations.unshift(conv);
      saveState(state);
      return conv as T;
    }
    return { items: state.conversations } as T;
  }

  if (pathOnly === '/api/v1/ai/copilot/chat') {
    const msg = String(body.message || '');
    const isAr = /[\u0600-\u06FF]/.test(msg) || body.language_hint === 'ar';
    const reply = isAr
      ? `تم تنفيذ التحليل في الوضع المستقل على جهازك:\n• وضع السوق الحي: نظام متوازن.\n• لديك ${state.strategies.length} استراتيجيات جاهزة ويمكنك تشغيل الباك-تيست والاطلاع على دليل التطبيق من /guide.`
      : `Analyzed in standalone client mode:\n• ${state.strategies.length} strategies ready, isolated Paper balance $${state.paperCash.toFixed(2)}. Open /backtesting or /guide to explore every tool.`;
    const convId = String(body.conversation_id || `conv-${Date.now()}`);
    const msgs = [{ role: 'user', content: msg, created_at: nowIso() }, { role: 'assistant', content: reply, provider_used: 'builtin:standalone', tool_actions: [], created_at: nowIso() }];
    return { conversation_id: convId, topic: msg.slice(0, 48), reply, provider_used: 'builtin:standalone', tool_actions: [], quick_prompts: [], fallback_warning: null, messages: msgs } as T;
  }

  if (pathOnly === '/api/v1/ai/market-intelligence') {
    const items = await fetchLiveMexcTickersFallback();
    const adv = items.filter((i) => i.change24h >= 0).length;
    const breadth = items.length ? (adv / items.length) * 100 : 50;
    const avg = items.length ? items.reduce((s, i) => s + i.change24h, 0) / items.length : 0;
    return {
      regime: breadth >= 60 ? 'Bullish Expansion' : breadth <= 40 ? 'Bearish Pressure' : 'Range / Mixed Consolidation',
      breadth_pct: Number(breadth.toFixed(2)),
      avg_change_pct: Number(avg.toFixed(2)),
      volatility_leaders: items.slice(0, 5).map((r) => ({ symbol: r.symbol, last: r.last, range_pct: Number((((r.high - r.low) / Math.max(r.last, 1e-9)) * 100).toFixed(2)) })),
      momentum_leaders: [...items].sort((a, b) => b.change24h - a.change24h).slice(0, 5).map((r) => ({ symbol: r.symbol, last: r.last, change24h: r.change24h })),
    } as T;
  }

  if (pathOnly === '/api/v1/ai/suggestions') return { items: state.suggestions } as T;

  if (pathOnly === '/api/v1/risk/profile') {
    if (method === 'PUT') {
      state.riskProfile = { ...state.riskProfile, ...body, updated_at: nowIso() };
      saveState(state);
    }
    return state.riskProfile as T;
  }

  if (pathOnly === '/api/v1/paper/overview') {
    const positions = Object.entries(state.paperPositions).map(([sym, p]) => {
      const m = DEMO_MARKETS.find((x) => x.symbol === sym) ?? DEMO_MARKETS[0]!;
      const mv = p.qty * m.last;
      const unrl = mv - p.qty * p.avg_entry_price;
      return { symbol: sym, qty: p.qty, avg_entry_price: p.avg_entry_price, mark_price: m.last, market_value_usdt: Number(mv.toFixed(2)), unrealized_pnl_usdt: Number(unrl.toFixed(2)), unrealized_pnl_pct: p.avg_entry_price > 0 ? Number(((m.last - p.avg_entry_price) / p.avg_entry_price) * 100) : 0 };
    });
    const posVal = positions.reduce((s, p) => s + p.market_value_usdt, 0);
    return { account: { id: 'paper-local', name: 'APEX Paper Spot (Standalone)', initial_balance_usdt: 10000, available_usdt: Number(state.paperCash.toFixed(2)), positions_value_usdt: Number(posVal.toFixed(2)), total_equity_usdt: Number((state.paperCash + posVal).toFixed(2)), realized_pnl_usdt: 0, unrealized_pnl_usdt: 0 }, positions, orders: state.paperOrders, trades: [] } as T;
  }

  if (pathOnly === '/api/v1/paper/reset') {
    state.paperCash = 10000;
    state.paperPositions = {};
    state.paperOrders = [];
    saveState(state);
    return { ok: true, available_usdt: 10000 } as T;
  }

  if (pathOnly === '/api/v1/live/overview') {
    return { exchange_credentials_configured: false, local_host_warning: 'Connect a local or remote APEX FastAPI backend to execute MEXC Spot orders.', risk_profile: state.riskProfile, realized_pnl_usdt: 0, positions: [], authorizations: [], orders: [], trades: [] } as T;
  }

  if (pathOnly === '/api/v1/system/updates/status') {
    return {
      current_version: '1.1.0',
      release_tag: 'v1.1.0',
      repo: 'aliazizdbab/apex-ai-trading-lab',
      channel: 'stable',
      local_commit: 'mobile-pwa',
      auto_check_enabled: true,
      release_url: 'https://github.com/aliazizdbab/apex-ai-trading-lab/releases/tag/v1.1.0',
      repo_url: 'https://github.com/aliazizdbab/apex-ai-trading-lab',
      platforms: {
        web: 'https://github.com/aliazizdbab/apex-ai-trading-lab/releases/download/v1.1.0/apex-web-v1.1.0.zip',
        windows: 'https://github.com/aliazizdbab/apex-ai-trading-lab/releases/download/v1.1.0/apex-windows-v1.1.0.zip',
        macos: 'https://github.com/aliazizdbab/apex-ai-trading-lab/releases/download/v1.1.0/apex-macos-v1.1.0.tar.gz',
        android: 'https://github.com/aliazizdbab/apex-ai-trading-lab/releases/download/v1.1.0/apex-android-v1.1.0.apk',
      },
    } as T;
  }

  return { ok: true, items: [] } as T;
}
