import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Layers, Play, Workflow } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useT } from '@/i18n/useT';
import {
  evaluateStrategy,
  listStrategies,
  updateStrategyStatus,
  type StrategyItem,
} from '@/services/api';
import { Panel } from '@/ui/Panel';
import { fmtPrice } from '@/utils/format';

const STATUSES = ['Draft', 'Validating', 'Backtesting', 'Paper Trading', 'Approved', 'Live', 'Paused', 'Disabled', 'Archived'];

export function StrategyLibraryPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: listStrategies,
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const strategies = data?.items ?? [];
  const selected: StrategyItem | null =
    strategies.find((s) => s.id === selectedId) ?? strategies[0] ?? null;

  const statusMut = useMutation({
    mutationFn: ({ id, st }: { id: string; st: string }) => updateStrategyStatus(id, st),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strategies'] }),
  });

  const evalMut = useMutation({
    mutationFn: evaluateStrategy,
  });

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Layers className="h-5 w-5 text-cyan" aria-hidden="true" />
          <h2 className="text-lg font-semibold">{t('strat.libraryTitle')}</h2>
        </div>
        <Link
          to="/strategy-composer"
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded bg-cyan px-3 text-xs font-medium text-bg hover:opacity-90"
        >
          <Workflow className="h-4 w-4" aria-hidden="true" />
          {t('nav.strategyComposer')}
        </Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Panel title={`${t('strat.libraryTitle')} (${strategies.length})`}>
          {isLoading ? (
            <p className="p-4 text-xs text-mute">{t('common.loading')}</p>
          ) : (
            <ul className="divide-y divide-line">
              {strategies.map((s) => {
                const active = selected?.id === s.id;
                return (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(s.id)}
                      className={`w-full border-s-2 px-3 py-3 text-start ${
                        active ? 'border-cyan bg-elevated' : 'border-transparent hover:bg-surface'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold">{s.name}</span>
                        <span className="rounded border border-line bg-surface px-1.5 py-0.5 text-[10px] font-medium">
                          {s.status}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-mute">{s.description}</p>
                      <div className="mt-1.5 flex items-center gap-2 text-[11px] text-mute">
                        <span>v{s.version_count}</span>
                        <span>·</span>
                        <span>
                          {t('strat.indicatorsCount', {
                            count: s.current_version?.definition.indicators.length ?? 0,
                          })}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        {selected && (
          <div className="flex flex-col gap-4">
            <Panel title={selected.name}>
              <div className="space-y-4 p-4">
                <p className="text-xs text-mute">{selected.description}</p>

                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 text-xs">
                    <span className="text-mute">{t('strat.status')}:</span>
                    <select
                      value={selected.status}
                      onChange={(e) => statusMut.mutate({ id: selected.id, st: e.target.value })}
                      className="min-h-[34px] rounded border border-line bg-surface px-2.5 text-xs"
                    >
                      {STATUSES.map((st) => (
                        <option key={st} value={st}>
                          {st}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selected.current_version && (
                    <button
                      type="button"
                      disabled={evalMut.isPending}
                      onClick={() =>
                        evalMut.mutate({
                          strategy_version_id: selected.current_version!.id,
                          symbol: selected.current_version!.definition.symbol,
                          timeframe: selected.current_version!.definition.timeframe,
                          limit: 200,
                        })
                      }
                      className="inline-flex min-h-[34px] items-center gap-1.5 rounded border border-cyan bg-surface px-3 text-xs font-medium text-cyan hover:bg-elevated"
                    >
                      <Play className="h-3.5 w-3.5" aria-hidden="true" />
                      {t('strat.evaluateNow')}
                    </button>
                  )}
                </div>

                {selected.current_version && (
                  <div className="space-y-2 rounded border border-line bg-surface p-3 text-xs">
                    <div className="flex flex-wrap gap-3 text-mute">
                      <span>Pair: {selected.current_version.definition.symbol}</span>
                      <span>TF: {selected.current_version.definition.timeframe}</span>
                      <span>SL: {selected.current_version.definition.stop_loss_pct}%</span>
                      <span>TP: {selected.current_version.definition.take_profit_pct}%</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.current_version.definition.indicators.map((ind) => (
                        <span
                          key={ind.key}
                          className="rounded border border-line bg-panel px-2 py-0.5 font-mono text-[11px]"
                        >
                          {ind.key}: {ind.indicator_id}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {evalMut.data && (
                  <div className="space-y-2 rounded border border-cyan/30 bg-cyan/5 p-3 text-xs">
                    <div className="flex flex-wrap gap-4 font-mono" dir="ltr">
                      <span>Bars: {evalMut.data.bars_evaluated}</span>
                      <span className="text-bull">Entries: {evalMut.data.entry_count}</span>
                      <span className="text-bear">Exits: {evalMut.data.exit_count}</span>
                      <span>Confluence: {(evalMut.data.latest_confluence * 100).toFixed(0)}%</span>
                    </div>
                    {evalMut.data.recent_signals.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {evalMut.data.recent_signals.slice(-6).map((sig, i) => (
                          <span
                            key={i}
                            className={`rounded px-1.5 py-0.5 font-mono text-[11px] ${
                              sig.type === 'entry' ? 'bg-bull/15 text-bull' : 'bg-bear/15 text-bear'
                            }`}
                          >
                            {sig.type.toUpperCase()} @ {fmtPrice(sig.price)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Panel>

            <Panel title={`${t('strat.versions')} (${selected.versions?.length ?? 0})`}>
              <ul className="divide-y divide-line">
                {(selected.versions ?? []).map((v) => (
                  <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-xs">
                    <div>
                      <span className="font-semibold">v{v.version_no}</span>
                      <span className="ms-2 text-mute">{v.change_note}</span>
                    </div>
                    <div className="font-mono text-[11px] text-mute" dir="ltr">
                      {v.definition_hash.slice(0, 12)} · {new Date(v.created_at).toLocaleString()}
                    </div>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        )}
      </div>
    </div>
  );
}
