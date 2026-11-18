import { CandlestickChart, Plus, Star } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import { useUiStore } from '@/stores/uiStore';
import { DemoBadge } from '@/ui/DemoBadge';
import { EmptyState } from '@/ui/EmptyState';
import { LiveBadge } from '@/ui/LiveBadge';
import { Panel } from '@/ui/Panel';
import { fmtCompact, fmtPct, fmtPrice } from '@/utils/format';

export function WatchlistPage() {
  const t = useT();
  const navigate = useNavigate();
  const favorites = useUiStore((s) => s.favorites);
  const toggleFavorite = useUiStore((s) => s.toggleFavorite);
  const { rows, isLive } = useLiveMarkets();

  const favRows = rows.filter((r) => favorites.includes(r.symbol));
  const otherRows = rows.filter((r) => !favorites.includes(r.symbol));

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{t('watchlist.title')}</h2>
          {isLive ? <LiveBadge /> : <DemoBadge />}
        </div>
      </div>

      {favRows.length === 0 ? (
        <Panel>
          <EmptyState icon={Star} title={t('watchlist.title')} body={t('watchlist.empty')} />
        </Panel>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {favRows.map((m) => {
            const span = m.high - m.low;
            const posPct = span > 0 ? Math.max(0, Math.min(100, ((m.last - m.low) / span) * 100)) : 50;
            return (
              <Panel key={m.symbol} className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="num text-base font-semibold">{m.symbol}</h3>
                    <p className="num text-xl font-bold">{fmtPrice(m.last)}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className={`num rounded px-1.5 py-0.5 text-xs font-medium ${m.change24h >= 0 ? 'bg-bull/10 text-bull' : 'bg-bear/10 text-bear'}`}>
                      {fmtPct(m.change24h)}
                    </span>
                    <button
                      type="button"
                      onClick={() => toggleFavorite(m.symbol)}
                      aria-label={`${t('watchlist.remove')}: ${m.symbol}`}
                      title={t('watchlist.remove')}
                      className="flex h-8 w-8 items-center justify-center rounded hover:bg-surface"
                    >
                      <Star className="h-4 w-4 fill-amber text-amber" aria-hidden="true" />
                    </button>
                  </div>
                </div>

                <div className="mt-3 space-y-1">
                  <div className="flex justify-between text-[11px] text-mute">
                    <span>{t('watchlist.range24h')}</span>
                    <span className="num">{fmtCompact(m.volume24h)}</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface" dir="ltr">
                    <div className="h-full bg-cyan" style={{ width: `${posPct}%` }} />
                  </div>
                  <div className="num flex justify-between text-[11px] text-mute" dir="ltr">
                    <span>{fmtPrice(m.low)}</span>
                    <span>{fmtPrice(m.high)}</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => navigate(`/terminal?symbol=${encodeURIComponent(m.symbol)}`)}
                  className="mt-3 inline-flex min-h-[36px] w-full items-center justify-center gap-1.5 rounded border border-line bg-surface text-xs font-medium hover:border-cyan hover:text-cyan"
                >
                  <CandlestickChart className="h-4 w-4" aria-hidden="true" />
                  {t('mkt.openChart')}
                </button>
              </Panel>
            );
          })}
        </div>
      )}

      {otherRows.length > 0 && (
        <Panel title={t('watchlist.quickAdd')}>
          <div className="flex flex-wrap gap-2 p-3">
            {otherRows.map((m) => (
              <button
                key={m.symbol}
                type="button"
                onClick={() => toggleFavorite(m.symbol)}
                className="inline-flex min-h-[34px] items-center gap-1 rounded border border-line bg-surface px-2.5 text-xs hover:border-cyan"
              >
                <Plus className="h-3.5 w-3.5 text-cyan" aria-hidden="true" />
                <span className="num">{m.symbol}</span>
              </button>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
