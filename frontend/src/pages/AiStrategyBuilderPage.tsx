import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import { aiBuildStrategy } from '@/services/api';
import { Panel } from '@/ui/Panel';

export function AiStrategyBuilderPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { rows: markets } = useLiveMarkets();

  const [prompt, setPrompt] = useState('Build a BTC Spot momentum strategy combining EMA, RSI, MACD, and Bollinger Bands with 1.5% SL.');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('15m');

  const buildMut = useMutation({
    mutationFn: aiBuildStrategy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      queryClient.invalidateQueries({ queryKey: ['ai-suggestions'] });
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    buildMut.mutate({ prompt, symbol, timeframe });
  };

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <div className="flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-cyan" aria-hidden="true" />
        <div>
          <h2 className="text-lg font-semibold">{t('ai.builderTitle')}</h2>
          <p className="text-xs text-mute">{t('ai.builderSub')}</p>
        </div>
      </div>

      <Panel title={t('ai.builderTitle')}>
        <form onSubmit={onSubmit} className="space-y-3 p-4">
          <label className="block space-y-1 text-xs">
            <span className="text-mute">{t('ai.promptLabel')}</span>
            <textarea
              rows={4}
              required
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="w-full rounded border border-line bg-surface p-3 text-xs text-ink focus:border-cyan focus:outline-none"
            />
          </label>
          <div className="flex flex-wrap items-end gap-3">
            <label className="space-y-1 text-xs">
              <span className="text-mute">{t('mkt.pair')}</span>
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="min-h-[36px] rounded border border-line bg-surface px-2.5 text-xs">
                {markets.map((m) => (
                  <option key={m.symbol} value={m.symbol}>{m.symbol}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-mute">{t('term.timeframe')}</span>
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="min-h-[36px] rounded border border-line bg-surface px-2.5 text-xs">
                {TIMEFRAMES.map((tf) => (
                  <option key={tf.id} value={tf.id}>{tf.id}</option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              disabled={buildMut.isPending}
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded bg-cyan px-4 text-xs font-medium text-bg hover:opacity-90"
            >
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {t('ai.generate')}
            </button>
          </div>
        </form>
      </Panel>

      {buildMut.data && (
        <Panel title={`${buildMut.data.name} (${buildMut.data.status})`}>
          <div className="space-y-3 p-4 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded border border-amber/40 bg-amber/10 px-2 py-0.5 font-semibold text-amber">
                Status: {buildMut.data.status}
              </span>
              <span className="rounded border border-line bg-surface px-2 py-0.5 font-mono text-mute">
                Provider: {buildMut.data.provider_used}
              </span>
            </div>
            <p>{buildMut.data.explanation}</p>
            <div className="flex flex-wrap gap-1.5">
              {buildMut.data.definition.indicators.map((ind) => (
                <span key={ind.key} className="rounded border border-line bg-surface px-2 py-0.5 font-mono">
                  {ind.key}: {ind.indicator_id}
                </span>
              ))}
            </div>
            <div className="flex gap-2 pt-2">
              <Link to="/strategy-library" className="rounded border border-cyan bg-surface px-3 py-1.5 text-cyan">
                {t('nav.strategyLibrary')}
              </Link>
              <Link to="/backtesting" className="rounded border border-line bg-surface px-3 py-1.5 hover:border-cyan">
                {t('nav.backtesting')}
              </Link>
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}
