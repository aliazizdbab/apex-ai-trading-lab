import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ShieldCheck, Zap } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import {
  ApiError,
  authorizeLiveStrategy,
  fetchLiveOverview,
  listStrategies,
  revokeLiveAuthorization,
  submitLiveOrder,
} from '@/services/api';
import { Panel } from '@/ui/Panel';
import { fmtPrice } from '@/utils/format';

export function LiveTradingPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { rows: markets } = useLiveMarkets();
  const { data: liveData } = useQuery({ queryKey: ['live-overview'], queryFn: fetchLiveOverview });
  const { data: stratsData } = useQuery({ queryKey: ['strategies'], queryFn: listStrategies });

  const approvedStrats = (stratsData?.items ?? []).filter((s) => s.status === 'Approved' || s.status === 'Live');
  const [selectedVerId, setSelectedVerId] = useState('');
  const [capValue, setCapValue] = useState(500);
  const [scope, setScope] = useState('BTC/USDT Spot');
  const [authErr, setAuthErr] = useState<string | null>(null);

  const [selectedAuthId, setSelectedAuthId] = useState('');
  const [ordSymbol, setOrdSymbol] = useState('BTC/USDT');
  const [ordQty, setOrdQty] = useState(0.002);
  const [ordErr, setOrdErr] = useState<string | null>(null);
  const [ordMsg, setOrdMsg] = useState<string | null>(null);

  const effectiveVerId = selectedVerId || approvedStrats[0]?.current_version_id || '';
  const activeAuths = (liveData?.authorizations ?? []).filter((a) => a.active);
  const effectiveAuthId = selectedAuthId || activeAuths[0]?.id || '';

  const authMut = useMutation({
    mutationFn: authorizeLiveStrategy,
    onSuccess: () => {
      setAuthErr(null);
      queryClient.invalidateQueries({ queryKey: ['live-overview'] });
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
    onError: (err) => setAuthErr(err instanceof ApiError ? err.detail : 'Authorization failed'),
  });

  const revokeMut = useMutation({
    mutationFn: revokeLiveAuthorization,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['live-overview'] }),
  });

  const orderMut = useMutation({
    mutationFn: submitLiveOrder,
    onSuccess: (res) => {
      setOrdErr(null);
      setOrdMsg(`Staged ${res.client_order_id} (${res.status}) · duplicate=${res.duplicate_prevented}`);
      queryClient.invalidateQueries({ queryKey: ['live-overview'] });
    },
    onError: (err) => {
      setOrdMsg(null);
      setOrdErr(err instanceof ApiError ? err.detail : 'Order rejected');
    },
  });

  const onAuthorize = (e: FormEvent) => {
    e.preventDefault();
    if (!effectiveVerId) return;
    authMut.mutate({ strategy_version_id: effectiveVerId, capital_mode: 'fixed_usdt', capital_value: capValue, scope });
  };

  const onStageOrder = (e: FormEvent) => {
    e.preventDefault();
    if (!effectiveAuthId) return;
    orderMut.mutate({
      authorization_id: effectiveAuthId,
      symbol: ordSymbol,
      side: 'buy',
      order_type: 'MARKET',
      qty: ordQty,
      stop_loss_pct: 1.5,
    });
  };

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex items-center gap-2">
        <Zap className="h-5 w-5 text-amber" aria-hidden="true" />
        <h2 className="text-lg font-semibold">{t('live.title')}</h2>
      </div>

      {liveData?.local_host_warning && (
        <Panel className="border-amber/40 bg-amber/10 p-3 text-xs">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber" aria-hidden="true" />
            <div className="space-y-1">
              <p className="font-semibold text-amber">Local Execution & Risk Notice</p>
              <p className="text-mute">{liveData.local_host_warning}</p>
              <p className="text-mute">
                MEXC Encrypted Keys Configured: {liveData.exchange_credentials_configured ? 'Yes' : 'No (add in /settings)'}
              </p>
            </div>
          </div>
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={t('live.authorizeTitle')}>
          <form onSubmit={onAuthorize} className="space-y-3 p-4 text-xs">
            <label className="block space-y-1">
              <span className="text-mute">Approved Strategy Version</span>
              <select value={effectiveVerId} onChange={(e) => setSelectedVerId(e.target.value)} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5">
                {approvedStrats.map((s) =>
                  s.current_version ? (
                    <option key={s.id} value={s.current_version.id}>
                      {s.name} (v{s.current_version.version_no} · {s.status})
                    </option>
                  ) : null,
                )}
              </select>
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1">
                <span className="text-mute">Capital Allocation (USDT)</span>
                <input type="number" min={10} value={capValue} onChange={(e) => setCapValue(Number(e.target.value))} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5 tabular-nums" />
              </label>
              <label className="space-y-1">
                <span className="text-mute">Scope</span>
                <input type="text" value={scope} onChange={(e) => setScope(e.target.value)} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5" />
              </label>
            </div>
            {authErr && <p className="text-bear">{authErr}</p>}
            <button type="submit" disabled={!effectiveVerId || authMut.isPending} className="inline-flex min-h-[36px] items-center gap-1.5 rounded bg-cyan px-4 font-medium text-bg hover:opacity-90 disabled:opacity-50">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              {t('live.authorizeBtn')}
            </button>
          </form>
        </Panel>

        <Panel title={t('live.stageOrder')}>
          <form onSubmit={onStageOrder} className="space-y-3 p-4 text-xs">
            <label className="block space-y-1">
              <span className="text-mute">Active Live Authorization</span>
              <select value={effectiveAuthId} onChange={(e) => setSelectedAuthId(e.target.value)} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5">
                {activeAuths.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.scope} (${a.capital_value})
                  </option>
                ))}
              </select>
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1">
                <span className="text-mute">{t('mkt.pair')}</span>
                <select value={ordSymbol} onChange={(e) => setOrdSymbol(e.target.value)} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5">
                  {markets.map((m) => (
                    <option key={m.symbol} value={m.symbol}>{m.symbol} ({fmtPrice(m.last)})</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-mute">Qty</span>
                <input type="number" step="0.0001" min={0.0001} value={ordQty} onChange={(e) => setOrdQty(Number(e.target.value))} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5 tabular-nums" />
              </label>
            </div>
            {ordMsg && <p className="font-mono text-bull" dir="ltr">{ordMsg}</p>}
            {ordErr && <p className="text-bear">{ordErr}</p>}
            <button type="submit" disabled={!effectiveAuthId || orderMut.isPending} className="min-h-[36px] rounded border border-amber bg-amber/10 px-4 font-medium text-amber hover:bg-amber/20 disabled:opacity-50">
              {t('live.stageOrder')}
            </button>
          </form>
        </Panel>
      </div>

      <Panel title={`Live Authorizations (${liveData?.authorizations.length ?? 0})`}>
        {(liveData?.authorizations ?? []).length === 0 ? (
          <p className="p-4 text-xs text-mute">No live authorizations granted yet.</p>
        ) : (
          <ul className="divide-y divide-line">
            {liveData!.authorizations.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-xs">
                <div>
                  <span className="font-semibold">{a.scope}</span>
                  <span className="ms-2 font-mono text-mute">${a.capital_value}</span>
                  <span className={`ms-2 rounded px-1.5 py-0.5 text-[10px] ${a.active ? 'bg-bull/15 text-bull' : 'bg-surface text-mute'}`}>
                    {a.active ? 'ACTIVE' : 'REVOKED'}
                  </span>
                </div>
                {a.active && (
                  <button type="button" onClick={() => revokeMut.mutate(a.id)} className="rounded border border-line bg-surface px-2.5 py-1 text-bear hover:border-bear">
                    {t('live.revoke')}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
