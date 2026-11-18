import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Save, Trash2, Workflow } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import {
  ApiError,
  createStrategy,
  fetchIndicatorCatalog,
  type StrategyIndicatorDef,
} from '@/services/api';
import { Panel } from '@/ui/Panel';

const DEFAULT_INDICATORS: StrategyIndicatorDef[] = [
  { key: 'ema_fast', indicator_id: 'ema', params: { length: 12, source: 'close', offset: 0 } },
  { key: 'ema_slow', indicator_id: 'ema', params: { length: 26, source: 'close', offset: 0 } },
  { key: 'rsi_14', indicator_id: 'rsi', params: { length: 14, source: 'close', overbought: 70, oversold: 30 } },
  { key: 'macd_main', indicator_id: 'macd', params: { fast_length: 12, slow_length: 26, signal_length: 9, source: 'close' } },
  { key: 'bb_20', indicator_id: 'bb', params: { length: 20, mult: 2.0, source: 'close' } },
  { key: 'atr_14', indicator_id: 'atr', params: { length: 14 } },
];

export function StrategyComposerPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { rows: markets } = useLiveMarkets();
  const { data: catalog } = useQuery({ queryKey: ['indicator-catalog'], queryFn: fetchIndicatorCatalog });

  const [name, setName] = useState('Custom Multi-Indicator Strategy');
  const [description, setDescription] = useState('Composed 6-indicator Spot strategy with strict SL/TP rules.');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [stopLossPct, setStopLossPct] = useState(1.5);
  const [takeProfitPct, setTakeProfitPct] = useState(3.2);
  const [indicators, setIndicators] = useState<StrategyIndicatorDef[]>(DEFAULT_INDICATORS);
  const [newIndType, setNewIndType] = useState('vwap');
  const [entryLeft, setEntryLeft] = useState('ema_fast.ema');
  const [entryOp, setEntryOp] = useState('>');
  const [entryRight, setEntryRight] = useState('ema_slow.ema');
  const [rsiThreshold, setRsiThreshold] = useState(48);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: createStrategy,
    onSuccess: (res) => {
      setSaveErr(null);
      setSaveMsg(`Saved "${res.name}" v1 (${res.current_version?.definition.indicators.length ?? 0} indicators)`);
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
    onError: (err) => {
      setSaveMsg(null);
      setSaveErr(err instanceof ApiError ? err.detail : 'Failed to save strategy');
    },
  });

  const addSlot = () => {
    const idx = indicators.length + 1;
    const spec = (catalog?.items ?? []).find((c) => c.id === newIndType);
    const params: Record<string, number | string> = {};
    for (const p of spec?.parameters ?? []) params[p.name] = p.default;
    setIndicators((prev) => [...prev, { key: `${newIndType}_${idx}`, indicator_id: newIndType, params }]);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const hasRsi = indicators.some((i) => i.key === 'rsi_14');
    const entryChildren: Record<string, unknown>[] = [
      { type: 'COMPARE', left: entryLeft, op: entryOp, right: entryRight },
    ];
    if (hasRsi) {
      entryChildren.push({ type: 'COMPARE', left: 'rsi_14.rsi', op: '>', right: rsiThreshold });
    }
    createMut.mutate({
      name,
      description,
      status: 'Draft',
      definition: {
        symbol,
        timeframe,
        signal_mode: 'closed_candle',
        stop_loss_pct: stopLossPct,
        take_profit_pct: takeProfitPct,
        indicators,
        entry_rule: { type: 'AND', children: entryChildren },
        exit_rule: {
          type: 'OR',
          children: [
            { type: 'CROSS_BELOW', left: entryLeft, right: entryRight },
            ...(hasRsi ? [{ type: 'COMPARE', left: 'rsi_14.rsi', op: '>', right: 75 }] : []),
          ],
        },
      },
    });
  };

  const inputCls =
    'min-h-[36px] w-full rounded border border-line bg-surface px-2.5 text-xs text-ink focus:border-cyan focus:outline-none';

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex items-center gap-2">
        <Workflow className="h-5 w-5 text-cyan" aria-hidden="true" />
        <div>
          <h2 className="text-lg font-semibold">{t('strat.composerTitle')}</h2>
          <p className="text-xs text-mute">{t('strat.composerSub')}</p>
        </div>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        <Panel title={t('strat.name')}>
          <div className="grid gap-3 p-4 sm:grid-cols-2">
            <label className="space-y-1 text-xs">
              <span className="text-mute">{t('strat.name')}</span>
              <input type="text" required value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">{t('strat.description')}</span>
              <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} className={inputCls} />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">{t('mkt.pair')}</span>
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={inputCls}>
                {markets.map((m) => (
                  <option key={m.symbol} value={m.symbol}>{m.symbol}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">{t('term.timeframe')}</span>
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={inputCls}>
                {TIMEFRAMES.map((tf) => (
                  <option key={tf.id} value={tf.id}>{tf.id}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">{t('strat.stopLoss')}</span>
              <input type="number" step="0.1" min={0.1} max={50} value={stopLossPct} onChange={(e) => setStopLossPct(Number(e.target.value))} className={`${inputCls} tabular-nums`} />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">{t('strat.takeProfit')}</span>
              <input type="number" step="0.1" min={0.1} max={200} value={takeProfitPct} onChange={(e) => setTakeProfitPct(Number(e.target.value))} className={`${inputCls} tabular-nums`} />
            </label>
          </div>
        </Panel>

        <Panel
          title={`${t('term.indicators')} (${indicators.length})`}
          actions={
            <div className="flex items-center gap-2">
              <select value={newIndType} onChange={(e) => setNewIndType(e.target.value)} className="h-8 rounded border border-line bg-surface px-2 text-xs">
                {(catalog?.items ?? []).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <button type="button" onClick={addSlot} className="inline-flex h-8 items-center gap-1 rounded border border-cyan bg-surface px-2.5 text-xs text-cyan hover:bg-elevated">
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                {t('strat.addInd')}
              </button>
            </div>
          }
        >
          <ul className="divide-y divide-line">
            {indicators.map((ind, idx) => (
              <li key={ind.key} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-semibold text-cyan">{ind.key}</span>
                  <span className="rounded border border-line bg-surface px-1.5 py-0.5 uppercase">{ind.indicator_id}</span>
                  <span className="font-mono text-mute" dir="ltr">
                    {Object.entries(ind.params).map(([k, v]) => `${k}=${v}`).join(', ')}
                  </span>
                </div>
                {indicators.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setIndicators((prev) => prev.filter((_, i) => i !== idx))}
                    className="rounded border border-line bg-surface p-1.5 text-bear hover:border-bear"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title={t('strat.entryRules')}>
          <div className="grid gap-3 p-4 sm:grid-cols-4">
            <label className="space-y-1 text-xs">
              <span className="text-mute">Left series</span>
              <input type="text" value={entryLeft} onChange={(e) => setEntryLeft(e.target.value)} className={`${inputCls} font-mono`} />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">Operator</span>
              <select value={entryOp} onChange={(e) => setEntryOp(e.target.value)} className={inputCls}>
                <option value=">">&gt;</option>
                <option value=">=">&gt;=</option>
                <option value="<">&lt;</option>
                <option value="<=">&lt;=</option>
              </select>
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">Right series</span>
              <input type="text" value={entryRight} onChange={(e) => setEntryRight(e.target.value)} className={`${inputCls} font-mono`} />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">RSI &gt;</span>
              <input type="number" value={rsiThreshold} onChange={(e) => setRsiThreshold(Number(e.target.value))} className={`${inputCls} tabular-nums`} />
            </label>
          </div>
        </Panel>

        {saveMsg && <p className="text-xs text-bull">{saveMsg}</p>}
        {saveErr && <p className="text-xs text-bear">{saveErr}</p>}

        <button
          type="submit"
          disabled={createMut.isPending}
          className="inline-flex min-h-[38px] items-center gap-1.5 rounded bg-cyan px-4 text-xs font-medium text-bg hover:opacity-90"
        >
          <Save className="h-4 w-4" aria-hidden="true" />
          {t('strat.saveNew')}
        </button>
      </form>
    </div>
  );
}
