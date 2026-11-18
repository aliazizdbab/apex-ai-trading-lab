import type { Candle, ConnectionState, MarketRow } from '@/types';
import type { Lang, Theme } from '@/stores/uiStore';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore non-JSON error body
    }
    throw new ApiError(res.status, detail);
  }

  return (await res.json()) as T;
}

export interface HealthResponse {
  status: string;
  engine: ConnectionState;
  mexc: ConnectionState;
  ai: ConnectionState;
  database: string;
  auth_setup_completed: boolean;
  totp_enabled: boolean;
  audit_chain_valid: boolean;
}

export interface UserSummary {
  id: string;
  email: string;
  display_name: string;
  totp_enabled: boolean;
}

export interface AuthStatusResponse {
  setup_completed: boolean;
  authenticated: boolean;
  user: UserSummary | null;
}

export interface SetupResponse {
  user: UserSummary;
  access_token: string;
  totp_secret: string;
  totp_uri: string;
}

export interface LoginResponse {
  user: UserSummary;
  access_token: string;
}

export interface TotpEnrollResponse {
  totp_secret: string;
  totp_uri: string;
  totp_enabled: boolean;
}

export interface UserSettingsPayload {
  theme: Theme;
  lang: Lang;
  sidebarCollapsed: boolean;
}

export interface CredentialItem {
  id: string;
  provider_type: 'exchange' | 'ai';
  provider_name: string;
  label: string;
  api_key_masked: string;
  has_secret: boolean;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  level: string;
  category: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  items: NotificationItem[];
  unread_count: number;
}

export interface AuditLogItem {
  id: number;
  ts: string;
  actor: string;
  action: string;
  entity: string;
  payload_redacted: Record<string, unknown>;
  hash_prev: string;
  entry_hash: string;
}

export interface AuditLogsResponse {
  chain_valid: boolean;
  total_entries: number;
  error: string | null;
  items: AuditLogItem[];
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/v1/health');
}

export function fetchAuthStatus(): Promise<AuthStatusResponse> {
  return request<AuthStatusResponse>('/api/v1/auth/status');
}

export function setupOwner(payload: {
  email: string;
  display_name: string;
  password: string;
}): Promise<SetupResponse> {
  return request<SetupResponse>('/api/v1/auth/setup', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function loginOwner(payload: {
  email: string;
  password: string;
  totp_code?: string;
}): Promise<LoginResponse> {
  return request<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function logoutOwner(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>('/api/v1/auth/logout', { method: 'POST' });
}

export function enrollTotp(): Promise<TotpEnrollResponse> {
  return request<TotpEnrollResponse>('/api/v1/auth/totp/enroll', { method: 'POST' });
}

export function activateTotp(totp_code: string): Promise<{ totp_enabled: boolean }> {
  return request<{ totp_enabled: boolean }>('/api/v1/auth/totp/activate', {
    method: 'POST',
    body: JSON.stringify({ totp_code }),
  });
}

export function fetchServerSettings(): Promise<UserSettingsPayload> {
  return request<UserSettingsPayload>('/api/v1/settings');
}

export function updateServerSettings(payload: Partial<UserSettingsPayload>): Promise<UserSettingsPayload> {
  return request<UserSettingsPayload>('/api/v1/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function listCredentials(): Promise<{ items: CredentialItem[] }> {
  return request<{ items: CredentialItem[] }>('/api/v1/credentials');
}

export function createCredential(payload: {
  provider_type: 'exchange' | 'ai';
  provider_name: string;
  label: string;
  api_key: string;
  api_secret?: string;
}): Promise<CredentialItem> {
  return request<CredentialItem>('/api/v1/credentials', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteCredential(credId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/v1/credentials/${encodeURIComponent(credId)}`, {
    method: 'DELETE',
  });
}

export function listNotifications(): Promise<NotificationsResponse> {
  return request<NotificationsResponse>('/api/v1/notifications');
}

export function markNotificationRead(notifId: string): Promise<NotificationItem> {
  return request<NotificationItem>(`/api/v1/notifications/${encodeURIComponent(notifId)}/read`, {
    method: 'POST',
  });
}

export function markAllNotificationsRead(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>('/api/v1/notifications/read-all', { method: 'POST' });
}

export interface MarketTickerRow extends MarketRow {
  mexc_symbol: string;
  baseVolume24h: number;
  bid: number;
  ask: number;
}

export interface DataQualityReport {
  total_bars: number;
  duplicate_count: number;
  out_of_order_count: number;
  invalid_ohlc_count: number;
  gap_count: number;
  is_clean: boolean;
  data_snapshot_hash: string;
}

export interface MarketCandlesResponse {
  symbol: string;
  timeframe: string;
  source: string;
  quality: DataQualityReport;
  items: Candle[];
}

export interface OrderBookResponse {
  symbol: string;
  source: string;
  lastUpdateId: number | null;
  bids: [number, number][];
  asks: [number, number][];
  spread: number;
  spread_pct: number;
}

export interface RecentTradeItem {
  price: number;
  qty: number;
  quoteQty: number;
  time: number;
  side: 'buy' | 'sell';
}

export interface CoverageSymbolItem {
  id: number;
  symbol: string;
  price_precision: number;
  qty_precision: number;
  min_qty: string;
  min_notional: string;
  status: string;
}

export interface CoverageRecord {
  id: number;
  symbol: string;
  timeframe: string;
  from_ts: string;
  to_ts: string;
  validated_at: string;
  gap_count: number;
}

export interface MarketCoverageResponse {
  symbols: CoverageSymbolItem[];
  coverage: CoverageRecord[];
}

export interface MexcStatusResponse {
  exchange: string;
  scope: string;
  status: 'connected' | 'error';
  error: string | null;
  server_time_ms: number | null;
  latency_ms: number | null;
  stored_credentials_count: number;
  rate_limiter: {
    capacity: number;
    available_tokens: number;
    refill_per_second: number;
    total_weight_used: number;
    in_backoff: boolean;
  };
  ws_manager: {
    endpoint: string;
    connected: boolean;
    reconnect_attempt: number;
    subscriptions: string[];
    gap_events: number;
  };
  supported_order_types: string[];
  platform_sl_tp_required: boolean;
  platform_sl_tp_note: string;
  timeframes: {
    id: string;
    mode: 'native' | 'aggregated';
    mexc_interval: string | null;
    aggregated_from: string | null;
  }[];
  symbol_rules_sample: {
    symbol: string;
    price_precision: number;
    qty_precision: number;
    min_qty: string;
    min_notional: string;
    status: string;
  }[];
}

export function fetchAuditLogs(limit = 30): Promise<AuditLogsResponse> {
  return request<AuditLogsResponse>(`/api/v1/audit-logs?limit=${limit}`);
}

export function fetchMarketTickers(): Promise<{ exchange: string; source: string; items: MarketTickerRow[] }> {
  return request<{ exchange: string; source: string; items: MarketTickerRow[] }>('/api/v1/market/tickers');
}

export function fetchMarketCandles(
  symbol: string,
  timeframe: string,
  limit = 250,
): Promise<MarketCandlesResponse> {
  const qs = new URLSearchParams({ symbol, timeframe, limit: String(limit) });
  return request<MarketCandlesResponse>(`/api/v1/market/candles?${qs.toString()}`);
}

export function fetchMarketOrderBook(symbol: string, limit = 12): Promise<OrderBookResponse> {
  const qs = new URLSearchParams({ symbol, limit: String(limit) });
  return request<OrderBookResponse>(`/api/v1/market/orderbook?${qs.toString()}`);
}

export function fetchMarketTrades(
  symbol: string,
  limit = 20,
): Promise<{ symbol: string; source: string; items: RecentTradeItem[] }> {
  const qs = new URLSearchParams({ symbol, limit: String(limit) });
  return request<{ symbol: string; source: string; items: RecentTradeItem[] }>(`/api/v1/market/trades?${qs.toString()}`);
}

export function fetchMarketCoverage(): Promise<MarketCoverageResponse> {
  return request<MarketCoverageResponse>('/api/v1/market/coverage');
}

export function backfillMarketCandles(payload: {
  symbol: string;
  timeframe: string;
  bars: number;
}): Promise<{ symbol: string; timeframe: string; source: string; quality: DataQualityReport }> {
  return request<{ symbol: string; timeframe: string; source: string; quality: DataQualityReport }>(
    '/api/v1/market/backfill',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export interface IndicatorParamSpec {
  name: string;
  label: string;
  param_type: 'int' | 'float' | 'select';
  default: number | string;
  min_val: number | null;
  max_val: number | null;
  options: string[] | null;
}

export interface IndicatorOutputMeta {
  key: string;
  label: string;
  color: string;
  series_type: 'line' | 'histogram';
}

export interface IndicatorCatalogItem {
  id: string;
  name: string;
  category: 'trend' | 'momentum' | 'volatility' | 'volume';
  kind: string;
  pane: 'overlay' | 'oscillator';
  description: string;
  outputs: IndicatorOutputMeta[];
  parameters: IndicatorParamSpec[];
}

export interface IndicatorPresetItem {
  id: string;
  indicator_id: string;
  name: string;
  symbol: string;
  timeframe: string;
  params: Record<string, number | string>;
  visible: boolean;
  created_at: string;
  updated_at: string;
}

export interface IndicatorPoint {
  time: number;
  value: number;
}

export interface ComputedIndicatorOutput {
  instance_id: string;
  indicator_id: string;
  name: string;
  pane: 'overlay' | 'oscillator';
  params: Record<string, number | string>;
  outputs_meta: IndicatorOutputMeta[];
  series: Record<string, IndicatorPoint[]>;
}

export type CandleMode = 'standard' | 'heikin_ashi';

export interface IndicatorComputeResponse {
  symbol: string;
  timeframe: string;
  source: string;
  candle_mode: CandleMode;
  quality: DataQualityReport;
  candles: Candle[];
  outputs: ComputedIndicatorOutput[];
}

export function fetchMexcStatus(): Promise<MexcStatusResponse> {
  return request<MexcStatusResponse>('/api/v1/exchanges/mexc/status');
}

export function fetchIndicatorCatalog(): Promise<{ items: IndicatorCatalogItem[] }> {
  return request<{ items: IndicatorCatalogItem[] }>('/api/v1/indicators/catalog');
}

export function listIndicatorPresets(): Promise<{ items: IndicatorPresetItem[] }> {
  return request<{ items: IndicatorPresetItem[] }>('/api/v1/indicators/presets');
}

export function createIndicatorPreset(payload: {
  indicator_id: string;
  name: string;
  symbol?: string;
  timeframe?: string;
  params: Record<string, number | string>;
  visible?: boolean;
}): Promise<IndicatorPresetItem> {
  return request<IndicatorPresetItem>('/api/v1/indicators/presets', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateIndicatorPreset(
  presetId: string,
  payload: {
    name?: string;
    symbol?: string;
    timeframe?: string;
    params?: Record<string, number | string>;
    visible?: boolean;
  },
): Promise<IndicatorPresetItem> {
  return request<IndicatorPresetItem>(`/api/v1/indicators/presets/${encodeURIComponent(presetId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteIndicatorPreset(presetId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/v1/indicators/presets/${encodeURIComponent(presetId)}`, {
    method: 'DELETE',
  });
}

export function computeIndicators(payload: {
  symbol: string;
  timeframe: string;
  limit?: number;
  candle_mode?: CandleMode;
  indicators: {
    instance_id: string;
    indicator_id: string;
    params: Record<string, number | string>;
  }[];
}): Promise<IndicatorComputeResponse> {
  return request<IndicatorComputeResponse>('/api/v1/indicators/compute', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------------
// Phase 6-14: Strategies, Backtesting, Replay, Pine, AI, Risk, Paper, Live
// ---------------------------------------------------------------------------

export interface StrategyIndicatorDef {
  key: string;
  indicator_id: string;
  params: Record<string, number | string>;
  timeframe?: string | null;
  weight?: number;
  enabled?: boolean;
}

export interface StrategyDefinition {
  symbol: string;
  timeframe: string;
  signal_mode: 'closed_candle' | 'intrabar';
  stop_loss_pct: number;
  take_profit_pct: number;
  indicators: StrategyIndicatorDef[];
  entry_rule: Record<string, unknown>;
  exit_rule: Record<string, unknown>;
}

export interface StrategyVersionItem {
  id: string;
  strategy_id: string;
  version_no: number;
  definition: StrategyDefinition;
  definition_hash: string;
  change_note: string;
  created_at: string;
}

export interface StrategyItem {
  id: string;
  name: string;
  description: string;
  status: string;
  current_version_id: string | null;
  current_version: StrategyVersionItem | null;
  version_count: number;
  versions?: StrategyVersionItem[];
  created_at: string;
  updated_at: string;
}

export interface BacktestMetrics {
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  profit_factor: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  expectancy_usdt: number;
  sl_tiebreak_exits: number;
}

export interface BacktestTrade {
  entry_time: number;
  exit_time: number;
  entry_price: number;
  exit_price: number;
  qty: number;
  pnl_usdt: number;
  pnl_pct: number;
  fee_usdt: number;
  exit_reason: string;
}

export interface BacktestRunResponse {
  id: string;
  strategy_version_id: string;
  symbol: string;
  timeframe: string;
  data_snapshot_hash: string;
  quality: DataQualityReport;
  metrics: BacktestMetrics;
  vectorized_parity: boolean;
  vectorized_approx_return_pct: number;
  equity_curve: { time: number; equity: number }[];
  drawdown_curve: { time: number; drawdown_pct: number }[];
  trades: BacktestTrade[];
  created_at: string;
}

export interface BacktestSummaryItem {
  id: string;
  strategy_version_id: string;
  strategy_name: string;
  version_no: number;
  symbol: string;
  timeframe: string;
  data_snapshot_hash: string;
  total_return_pct: number;
  win_rate_pct: number;
  profit_factor: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  total_trades: number;
  created_at: string;
}

export interface OptimizeResponse {
  strategy_version_id: string;
  symbol: string;
  timeframe: string;
  data_snapshot_hash: string;
  split_index: number;
  in_sample_bars: number;
  out_of_sample_bars: number;
  best_params: { stop_loss_pct: number; take_profit_pct: number };
  in_sample_metrics: BacktestMetrics;
  out_of_sample_metrics: BacktestMetrics;
  overfitting_warning: boolean;
  overfitting_reason: string;
  sensitivity_grid: {
    stop_loss_pct: number;
    take_profit_pct: number;
    is_return_pct: number;
    is_win_rate_pct: number;
    is_max_drawdown_pct: number;
    is_trades: number;
    score: number;
  }[];
}

export interface ReplayViewResponse {
  id: string;
  symbol: string;
  timeframe: string;
  status: string;
  cursor_index: number;
  total_bars: number;
  visible_candles: Candle[];
  current_bar: Candle | null;
  state: {
    cash_usdt: number;
    position_qty: number;
    avg_entry_price: number;
    realized_pnl_usdt: number;
    unrealized_pnl_usdt: number;
    total_equity_usdt: number;
    trades: { time: number; side: string; price: number; qty: number }[];
  };
}

export interface PineInputSpec {
  name: string;
  type: string;
  default: number | string | boolean;
  title: string;
  minval: number | null;
  maxval: number | null;
}

export interface PineAnalysisResponse {
  title: string;
  pine_version: number;
  script_type: string;
  sha256: string;
  inputs: PineInputSpec[];
  builtin_indicators: string[];
  referenced_timeframes: string[];
  alerts: string[];
  ast: { statement_count: number; statements: Record<string, unknown>[] };
  compat_report: {
    supported: boolean;
    unsupported_features: string[];
    repaint_warnings: string[];
    sandbox_mode: string;
  };
}

export interface PineScriptItem {
  id: string;
  name: string;
  script_type: string;
  version_count: number;
  current_version: {
    id: string;
    version_no: number;
    source_code: string;
    pine_version: number;
    ast: Record<string, unknown>;
    compat_report: Record<string, unknown>;
    sha256: string;
    created_at: string;
  } | null;
  created_at: string;
}

export interface PineExecuteResponse {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  analysis: PineAnalysisResponse;
  plots: Record<string, IndicatorPoint[]>;
  entry_signals: boolean[];
  exit_signals: boolean[];
  entry_count: number;
  exit_count: number;
}

export interface AiSuggestionItem {
  id: string;
  kind: string;
  prompt: string;
  proposal: Record<string, unknown>;
  explanation: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  decided_at: string | null;
}

export interface MarketIntelResponse {
  regime: string;
  breadth_pct: number;
  avg_change_pct: number;
  volatility_leaders: { symbol: string; last: number; range_pct: number }[];
  momentum_leaders: { symbol: string; last: number; change24h: number }[];
}

export interface RiskProfileItem {
  id: string;
  name: string;
  max_risk_per_trade_pct: number;
  max_daily_loss_pct: number;
  max_weekly_loss_pct: number;
  max_drawdown_pct: number;
  max_open_positions: number;
  max_asset_exposure_pct: number;
  cooldown_minutes: number;
  emergency_stop_active: boolean;
  updated_at: string;
}

export interface TradingPositionItem {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  mark_price: number;
  market_value_usdt: number;
  unrealized_pnl_usdt: number;
  unrealized_pnl_pct: number;
}

export interface PaperOverviewResponse {
  account: {
    id: string;
    name: string;
    initial_balance_usdt: number;
    available_usdt: number;
    positions_value_usdt: number;
    total_equity_usdt: number;
    realized_pnl_usdt: number;
    unrealized_pnl_usdt: number;
  };
  positions: TradingPositionItem[];
  orders: {
    id: string;
    client_order_id: string;
    symbol: string;
    side: string;
    order_type: string;
    qty: number;
    price: number | null;
    status: string;
    created_at: string;
  }[];
  trades: {
    id: string;
    paper_order_id: string;
    price: number;
    qty: number;
    fee: number;
    fee_asset: string;
    executed_at: string;
  }[];
}

export interface LiveOverviewResponse {
  exchange_credentials_configured: boolean;
  local_host_warning: string;
  risk_profile: RiskProfileItem;
  realized_pnl_usdt: number;
  positions: TradingPositionItem[];
  authorizations: {
    id: string;
    strategy_version_id: string;
    capital_mode: string;
    capital_value: number;
    scope: string;
    active: boolean;
    granted_at: string;
    revoked_at: string | null;
  }[];
  orders: {
    id: string;
    client_order_id: string;
    symbol: string;
    side: string;
    order_type: string;
    qty: number;
    price: number | null;
    status: string;
    risk_approval_token: string;
    created_at: string;
  }[];
  trades: {
    id: string;
    live_order_id: string;
    exchange_trade_id: string;
    price: number;
    qty: number;
    fee: number;
    fee_asset: string;
    executed_at: string;
  }[];
}

export function listStrategies(): Promise<{ items: StrategyItem[] }> {
  return request<{ items: StrategyItem[] }>('/api/v1/strategies');
}

export function createStrategy(payload: {
  name: string;
  description: string;
  status?: string;
  definition: StrategyDefinition;
  change_note?: string;
}): Promise<StrategyItem> {
  return request<StrategyItem>('/api/v1/strategies', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createStrategyVersion(
  strategyId: string,
  payload: { definition: StrategyDefinition; change_note: string },
): Promise<StrategyItem> {
  return request<StrategyItem>(`/api/v1/strategies/${encodeURIComponent(strategyId)}/versions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateStrategyStatus(strategyId: string, statusVal: string): Promise<StrategyItem> {
  return request<StrategyItem>(`/api/v1/strategies/${encodeURIComponent(strategyId)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status: statusVal }),
  });
}

export function evaluateStrategy(payload: {
  strategy_version_id?: string;
  definition?: StrategyDefinition;
  symbol: string;
  timeframe: string;
  limit?: number;
}): Promise<{
  symbol: string;
  timeframe: string;
  bars_evaluated: number;
  entry_count: number;
  exit_count: number;
  latest_confluence: number;
  recent_signals: { time: number; type: string; price: number }[];
}> {
  return request('/api/v1/strategies/evaluate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function runBacktest(payload: {
  strategy_version_id: string;
  symbol: string;
  timeframe: string;
  bars: number;
  initial_capital_usdt: number;
  position_size_pct: number;
  fee_pct: number;
  slippage_pct: number;
}): Promise<BacktestRunResponse> {
  return request<BacktestRunResponse>('/api/v1/backtests/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listBacktests(): Promise<{ items: BacktestSummaryItem[] }> {
  return request<{ items: BacktestSummaryItem[] }>('/api/v1/backtests');
}

export function getBacktest(jobId: string): Promise<{
  id: string;
  strategy_version_id: string;
  symbol: string;
  timeframe: string;
  data_snapshot_hash: string;
  metrics: BacktestMetrics & {
    equity_curve?: { time: number; equity: number }[];
    drawdown_curve?: { time: number; drawdown_pct: number }[];
  };
  trades: BacktestTrade[];
  created_at: string;
}> {
  return request(`/api/v1/backtests/${encodeURIComponent(jobId)}`);
}

export function optimizeBacktest(payload: {
  strategy_version_id: string;
  symbol: string;
  timeframe: string;
  bars: number;
}): Promise<OptimizeResponse> {
  return request<OptimizeResponse>('/api/v1/backtests/optimize', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function startReplaySession(payload: {
  symbol: string;
  timeframe: string;
  bars?: number;
  start_cursor?: number;
}): Promise<ReplayViewResponse> {
  return request<ReplayViewResponse>('/api/v1/replay/sessions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function stepReplaySession(sessionId: string, steps: number): Promise<ReplayViewResponse> {
  return request<ReplayViewResponse>(`/api/v1/replay/sessions/${encodeURIComponent(sessionId)}/step`, {
    method: 'POST',
    body: JSON.stringify({ steps }),
  });
}

export function placeReplayOrder(
  sessionId: string,
  payload: { side: 'buy' | 'sell'; qty: number },
): Promise<ReplayViewResponse> {
  return request<ReplayViewResponse>(`/api/v1/replay/sessions/${encodeURIComponent(sessionId)}/order`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listPineScripts(): Promise<{ items: PineScriptItem[] }> {
  return request<{ items: PineScriptItem[] }>('/api/v1/pine/scripts');
}

export function analyzePineScript(source_code: string): Promise<PineAnalysisResponse> {
  return request<PineAnalysisResponse>('/api/v1/pine/analyze', {
    method: 'POST',
    body: JSON.stringify({ source_code }),
  });
}

export function savePineScript(payload: {
  script_id?: string;
  name?: string;
  source_code: string;
}): Promise<PineScriptItem> {
  return request<PineScriptItem>('/api/v1/pine/scripts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function executePineScript(payload: {
  source_code: string;
  symbol: string;
  timeframe: string;
  limit?: number;
  input_overrides?: Record<string, unknown>;
}): Promise<PineExecuteResponse> {
  return request<PineExecuteResponse>('/api/v1/pine/execute', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function aiBuildStrategy(payload: {
  prompt: string;
  symbol: string;
  timeframe: string;
}): Promise<{
  strategy_id: string;
  strategy_version_id: string;
  suggestion_id: string;
  provider_used: string;
  status: string;
  name: string;
  description: string;
  definition: StrategyDefinition;
  explanation: string;
}> {
  return request('/api/v1/ai/strategy-builder', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function aiRunResearch(payload: {
  backtest_job_id?: string;
  strategy_id?: string;
  prompt?: string;
}): Promise<{
  suggestion_id: string;
  strategy_name: string;
  symbol: string;
  provider_used: string;
  summary: string;
  proposal: Record<string, unknown>;
  status: string;
}> {
  return request('/api/v1/ai/research', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchMarketIntelligence(): Promise<MarketIntelResponse> {
  return request<MarketIntelResponse>('/api/v1/ai/market-intelligence');
}

export function listAiSuggestions(): Promise<{ items: AiSuggestionItem[] }> {
  return request<{ items: AiSuggestionItem[] }>('/api/v1/ai/suggestions');
}

export function decideAiSuggestion(
  suggestionId: string,
  decision: 'approved' | 'rejected',
): Promise<{ id: string; status: string; decided_at: string }> {
  return request(`/api/v1/ai/suggestions/${encodeURIComponent(suggestionId)}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
  });
}

export function fetchRiskProfile(): Promise<RiskProfileItem> {
  return request<RiskProfileItem>('/api/v1/risk/profile');
}

export function updateRiskProfile(payload: Omit<RiskProfileItem, 'id' | 'name' | 'emergency_stop_active' | 'updated_at'>): Promise<RiskProfileItem> {
  return request<RiskProfileItem>('/api/v1/risk/profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function toggleEmergencyStop(active: boolean): Promise<{
  emergency_stop_active: boolean;
  revoked_authorizations: number;
}> {
  return request('/api/v1/risk/emergency-stop', {
    method: 'POST',
    body: JSON.stringify({ active }),
  });
}

export function fetchPaperOverview(): Promise<PaperOverviewResponse> {
  return request<PaperOverviewResponse>('/api/v1/paper/overview');
}

export function submitPaperOrder(payload: {
  symbol: string;
  side: 'buy' | 'sell';
  order_type: 'MARKET' | 'LIMIT';
  qty: number;
  price?: number;
  stop_loss_pct?: number;
}): Promise<{
  order_id: string;
  client_order_id: string;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  fee_usdt: number;
  status: string;
}> {
  return request('/api/v1/paper/orders', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function resetPaperAccount(): Promise<{ ok: boolean; available_usdt: number }> {
  return request('/api/v1/paper/reset', { method: 'POST' });
}

export function fetchLiveOverview(): Promise<LiveOverviewResponse> {
  return request<LiveOverviewResponse>('/api/v1/live/overview');
}

export function authorizeLiveStrategy(payload: {
  strategy_version_id: string;
  capital_mode: 'fixed_usdt' | 'pct_portfolio';
  capital_value: number;
  scope: string;
}): Promise<{ id: string; strategy_version_id: string; scope: string; active: boolean }> {
  return request('/api/v1/live/authorize', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function revokeLiveAuthorization(authId: string): Promise<{ ok: boolean; id: string }> {
  return request(`/api/v1/live/revoke/${encodeURIComponent(authId)}`, { method: 'POST' });
}

export function submitLiveOrder(payload: {
  authorization_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  order_type: 'MARKET' | 'LIMIT';
  qty: number;
  price?: number;
  stop_loss_pct?: number;
}): Promise<{
  order_id: string;
  client_order_id: string;
  status: string;
  duplicate_prevented: boolean;
}> {
  return request('/api/v1/live/orders', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------------
// Agentic AI Quant Copilot (Multi-Provider + Full-App Tool Calling)
// ---------------------------------------------------------------------------

export type CopilotProviderId =
  | 'builtin'
  | 'gemini'
  | 'openai'
  | 'anthropic'
  | 'deepseek'
  | 'openrouter'
  | 'custom';

export type CopilotAutonomyLevel = 'full_copilot' | 'research_and_paper' | 'research_only';

export interface CopilotProviderCatalogItem {
  id: CopilotProviderId;
  label: string;
  default_model: string;
  default_base_url: string;
}

export interface CopilotConfigResponse {
  id: string;
  provider: CopilotProviderId;
  model_name: string;
  base_url: string;
  has_api_key: boolean;
  api_key_masked: string;
  autonomy_level: CopilotAutonomyLevel;
  system_instructions: string;
  enabled: boolean;
  updated_at: string;
  providers: CopilotProviderCatalogItem[];
}

export interface CopilotToolAction {
  tool: string;
  ok: boolean;
  title: string;
  route?: string;
  data?: Record<string, unknown>;
  error?: string;
}

export interface CopilotChatMessage {
  role: 'user' | 'assistant';
  content: string;
  provider_used?: string;
  tool_actions?: CopilotToolAction[];
  fallback_warning?: string | null;
  created_at?: string;
}

export interface CopilotConversationItem {
  id: string;
  provider: string;
  topic: string;
  messages: CopilotChatMessage[];
  created_at: string;
}

export interface CopilotChatResponse {
  conversation_id: string;
  topic: string;
  reply: string;
  provider_used: string;
  tool_actions: CopilotToolAction[];
  quick_prompts: string[];
  fallback_warning: string | null;
  messages: CopilotChatMessage[];
}

export function fetchCopilotConfig(): Promise<CopilotConfigResponse> {
  return request<CopilotConfigResponse>('/api/v1/ai/copilot/config');
}

export function updateCopilotConfig(payload: {
  provider: CopilotProviderId;
  model_name: string;
  base_url?: string;
  api_key?: string;
  clear_api_key?: boolean;
  autonomy_level: CopilotAutonomyLevel;
  system_instructions?: string;
  enabled?: boolean;
}): Promise<CopilotConfigResponse> {
  return request<CopilotConfigResponse>('/api/v1/ai/copilot/config', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function testCopilotConnection(payload: {
  provider?: CopilotProviderId;
  model_name?: string;
  base_url?: string;
  api_key?: string;
}): Promise<{
  ok: boolean;
  provider: string;
  model_name: string;
  latency_ms: number;
  message: string;
}> {
  return request('/api/v1/ai/copilot/test', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listCopilotConversations(): Promise<{ items: CopilotConversationItem[] }> {
  return request<{ items: CopilotConversationItem[] }>('/api/v1/ai/copilot/conversations');
}

export function createCopilotConversation(topic?: string): Promise<CopilotConversationItem> {
  return request<CopilotConversationItem>('/api/v1/ai/copilot/conversations', {
    method: 'POST',
    body: JSON.stringify({ topic: topic || 'New Quant Strategy Session' }),
  });
}

export function deleteCopilotConversation(conversationId: string): Promise<{ ok: boolean; id: string }> {
  return request(`/api/v1/ai/copilot/conversations/${encodeURIComponent(conversationId)}`, {
    method: 'DELETE',
  });
}

export function sendCopilotChat(payload: {
  conversation_id?: string;
  message: string;
  active_page?: string;
  active_strategy_id?: string;
  language_hint?: string;
}): Promise<CopilotChatResponse> {
  return request<CopilotChatResponse>('/api/v1/ai/copilot/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------------
// System GitHub Auto-Update & Multi-Platform Releases
// ---------------------------------------------------------------------------

export interface UpdateStatusResponse {
  current_version: string;
  release_tag: string;
  repo: string;
  channel: string;
  local_commit: string;
  auto_check_enabled: boolean;
  release_url: string;
  repo_url: string;
  platforms: {
    web?: string;
    windows?: string;
    macos?: string;
    android?: string;
  };
}

export interface UpdateCheckResponse {
  ok: boolean;
  error: string | null;
  repo: string;
  repo_url: string;
  update_available: boolean;
  current_version: string;
  latest_version: string;
  latest_tag: string;
  local_commit: string;
  remote_commit: string;
  release_url: string;
  release_notes: string;
  platforms: {
    web?: string;
    windows?: string;
    macos?: string;
    android?: string;
  };
  checked_at: string;
}

export interface UpdateApplyResponse {
  ok: boolean;
  before_commit: string;
  after_commit: string;
  output: string;
}

export function fetchUpdateStatus(): Promise<UpdateStatusResponse> {
  return request<UpdateStatusResponse>('/api/v1/system/updates/status');
}

export async function checkGithubUpdates(): Promise<UpdateCheckResponse> {
  try {
    return await request<UpdateCheckResponse>('/api/v1/system/updates/check', {
      method: 'POST',
    });
  } catch {
    // Fallback for standalone static Web / Android APK builds checking GitHub directly
    const localRes = await fetch('/version.json').catch(() => null);
    const localManifest = localRes && localRes.ok ? await localRes.json() : { version: '1.0.0', repo: 'aliazizdbab/apex-ai-trading-lab', platforms: {} };
    const repo = localManifest.repo || 'aliazizdbab/apex-ai-trading-lab';
    const curr = String(localManifest.version || '1.0.0');
    const ghRes = await fetch(`https://api.github.com/repos/${repo}/releases/latest`);
    const rel = ghRes.ok ? await ghRes.json() : null;
    const latestTag = rel?.tag_name ? String(rel.tag_name) : `v${curr}`;
    const latestVer = latestTag.replace(/^[vV]/, '');
    return {
      ok: ghRes.ok,
      error: ghRes.ok ? null : 'Unable to reach GitHub Releases API',
      repo,
      repo_url: `https://github.com/${repo}`,
      update_available: latestVer !== curr,
      current_version: curr,
      latest_version: latestVer,
      latest_tag: latestTag,
      local_commit: 'standalone',
      remote_commit: latestTag,
      release_url: rel?.html_url || `https://github.com/${repo}/releases/latest`,
      release_notes: rel?.body || localManifest.notes || '',
      platforms: localManifest.platforms || {},
      checked_at: new Date().toISOString(),
    };
  }
}

export function applyGithubUpdate(): Promise<UpdateApplyResponse> {
  return request<UpdateApplyResponse>('/api/v1/system/updates/apply', {
    method: 'POST',
  });
}
