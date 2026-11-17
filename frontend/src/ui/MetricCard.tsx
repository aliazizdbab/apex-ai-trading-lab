import { fmtPct } from '@/utils/format';
import { DemoBadge } from './DemoBadge';
import { Sparkline } from './Sparkline';

interface Props {
  label: string;
  value: string;
  tip: string;
  deltaPct?: number;
  period?: string;
  spark?: number[];
  demo?: boolean;
}

export function MetricCard({ label, value, tip, deltaPct, period, spark, demo }: Props) {
  const tone = deltaPct === undefined || deltaPct === 0 ? 'neutral' : deltaPct > 0 ? 'bull' : 'bear';
  const deltaClass = tone === 'bull' ? 'text-bull' : tone === 'bear' ? 'text-bear' : 'text-mute';
  return (
    <div className="min-w-0 rounded-md border border-line bg-panel p-3" title={tip}>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-xs text-mute">{label}</span>
        {demo && <DemoBadge />}
      </div>
      <div className="num mt-1 text-xl font-semibold">{value}</div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {deltaPct !== undefined && <span className={`num font-medium ${deltaClass}`}>{fmtPct(deltaPct)}</span>}
        {period && <span className="truncate text-mute">{period}</span>}
      </div>
      {spark && (
        <div className="mt-2">
          <Sparkline values={spark} tone={tone} />
        </div>
      )}
    </div>
  );
}
