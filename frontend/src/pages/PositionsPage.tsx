import { useQuery } from '@tanstack/react-query';
import { Layers } from 'lucide-react';
import { useState } from 'react';
import { useT } from '@/i18n/useT';
import { fetchLiveOverview, fetchPaperOverview } from '@/services/api';
import { Panel } from '@/ui/Panel';
import { Segmented } from '@/ui/Segmented';
import { fmtPrice } from '@/utils/format';

export function PositionsPage() {
  const t = useT();
  const [mode, setMode] = useState<'paper' | 'real'>('paper');
  const { data: paper } = useQuery({ queryKey: ['paper-overview'], queryFn: fetchPaperOverview });
  const { data: live } = useQuery({ queryKey: ['live-overview'], queryFn: fetchLiveOverview });

  const positions = mode === 'paper' ? (paper?.positions ?? []) : (live?.positions ?? []);

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Layers className="h-5 w-5 text-cyan" aria-hidden="true" />
          <h2 className="text-lg font-semibold">{t('live.positionsTitle')}</h2>
        </div>
        <Segmented<'real' | 'paper'>
          ariaLabel={t('live.positionsTitle')}
          value={mode}
          onChange={setMode}
          options={[
            { value: 'real', label: t('live.realTab') },
            { value: 'paper', label: t('live.paperTab') },
          ]}
        />
      </div>

      <Panel>
        {positions.length === 0 ? (
          <p className="p-6 text-xs text-mute">No open {mode} positions.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-start text-xs">
              <thead className="border-b border-line bg-surface text-mute">
                <tr>
                  <th className="px-3 py-2 text-start">{t('mkt.pair')}</th>
                  <th className="px-3 py-2 text-end">Qty</th>
                  <th className="px-3 py-2 text-end">Entry Price</th>
                  <th className="px-3 py-2 text-end">Mark Price</th>
                  <th className="px-3 py-2 text-end">Market Value</th>
                  <th className="px-3 py-2 text-end">Unrealized PnL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {positions.map((p) => (
                  <tr key={p.symbol}>
                    <td className="num px-3 py-2 font-semibold">{p.symbol}</td>
                    <td className="num px-3 py-2 text-end">{p.qty.toFixed(6)}</td>
                    <td className="num px-3 py-2 text-end">{fmtPrice(p.avg_entry_price)}</td>
                    <td className="num px-3 py-2 text-end">{fmtPrice(p.mark_price)}</td>
                    <td className="num px-3 py-2 text-end">${fmtPrice(p.market_value_usdt)}</td>
                    <td className={`num px-3 py-2 text-end font-medium ${p.unrealized_pnl_usdt >= 0 ? 'text-bull' : 'text-bear'}`}>
                      ${p.unrealized_pnl_usdt.toFixed(2)} ({p.unrealized_pnl_pct.toFixed(2)}%)
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
