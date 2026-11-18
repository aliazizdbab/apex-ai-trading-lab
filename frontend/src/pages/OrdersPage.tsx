import { useQuery } from '@tanstack/react-query';
import { ListOrdered } from 'lucide-react';
import { useState } from 'react';
import { useT } from '@/i18n/useT';
import { fetchLiveOverview, fetchPaperOverview } from '@/services/api';
import { Panel } from '@/ui/Panel';
import { Segmented } from '@/ui/Segmented';
import { fmtPrice } from '@/utils/format';

export function OrdersPage() {
  const t = useT();
  const [mode, setMode] = useState<'paper' | 'real'>('paper');
  const { data: paper } = useQuery({ queryKey: ['paper-overview'], queryFn: fetchPaperOverview });
  const { data: live } = useQuery({ queryKey: ['live-overview'], queryFn: fetchLiveOverview });

  const orders = mode === 'paper' ? (paper?.orders ?? []) : (live?.orders ?? []);

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ListOrdered className="h-5 w-5 text-cyan" aria-hidden="true" />
          <h2 className="text-lg font-semibold">{t('live.ordersTitle')}</h2>
        </div>
        <Segmented<'real' | 'paper'>
          ariaLabel={t('live.ordersTitle')}
          value={mode}
          onChange={setMode}
          options={[
            { value: 'real', label: t('live.realTab') },
            { value: 'paper', label: t('live.paperTab') },
          ]}
        />
      </div>

      <Panel>
        {orders.length === 0 ? (
          <p className="p-6 text-xs text-mute">No {mode} orders recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-start text-xs">
              <thead className="border-b border-line bg-surface text-mute">
                <tr>
                  <th className="px-3 py-2 text-start">Client Order ID</th>
                  <th className="px-3 py-2 text-start">{t('mkt.pair')}</th>
                  <th className="px-3 py-2 text-start">Side</th>
                  <th className="px-3 py-2 text-end">Qty</th>
                  <th className="px-3 py-2 text-end">Price</th>
                  <th className="px-3 py-2 text-start">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td className="px-3 py-2 font-mono text-[11px] text-mute" dir="ltr">{o.client_order_id}</td>
                    <td className="num px-3 py-2 font-semibold">{o.symbol}</td>
                    <td className={`px-3 py-2 uppercase ${o.side === 'buy' ? 'text-bull' : 'text-bear'}`}>{o.side}</td>
                    <td className="num px-3 py-2 text-end">{o.qty}</td>
                    <td className="num px-3 py-2 text-end">{o.price ? fmtPrice(o.price) : '—'}</td>
                    <td className="px-3 py-2 font-mono">{o.status}</td>
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
