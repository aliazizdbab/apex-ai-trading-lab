import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { OctagonAlert, Save, ShieldAlert } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { useT } from '@/i18n/useT';
import {
  fetchRiskProfile,
  toggleEmergencyStop,
  updateRiskProfile,
} from '@/services/api';
import { Panel } from '@/ui/Panel';

export function RiskManagementPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { data: profile } = useQuery({
    queryKey: ['risk-profile'],
    queryFn: fetchRiskProfile,
  });

  const [maxRiskTrade, setMaxRiskTrade] = useState(2.0);
  const [maxDailyLoss, setMaxDailyLoss] = useState(5.0);
  const [maxWeeklyLoss, setMaxWeeklyLoss] = useState(10.0);
  const [maxDrawdown, setMaxDrawdown] = useState(15.0);
  const [maxPositions, setMaxPositions] = useState(5);
  const [maxExposure, setMaxExposure] = useState(40.0);
  const [cooldown, setCooldown] = useState(15);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!profile) return;
    setMaxRiskTrade(profile.max_risk_per_trade_pct);
    setMaxDailyLoss(profile.max_daily_loss_pct);
    setMaxWeeklyLoss(profile.max_weekly_loss_pct);
    setMaxDrawdown(profile.max_drawdown_pct);
    setMaxPositions(profile.max_open_positions);
    setMaxExposure(profile.max_asset_exposure_pct);
    setCooldown(profile.cooldown_minutes);
  }, [profile]);

  const saveMut = useMutation({
    mutationFn: updateRiskProfile,
    onSuccess: () => {
      setSavedMsg('Risk profile updated.');
      queryClient.invalidateQueries({ queryKey: ['risk-profile'] });
    },
  });

  const estopMut = useMutation({
    mutationFn: toggleEmergencyStop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['risk-profile'] });
      queryClient.invalidateQueries({ queryKey: ['live-overview'] });
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    saveMut.mutate({
      max_risk_per_trade_pct: maxRiskTrade,
      max_daily_loss_pct: maxDailyLoss,
      max_weekly_loss_pct: maxWeeklyLoss,
      max_drawdown_pct: maxDrawdown,
      max_open_positions: maxPositions,
      max_asset_exposure_pct: maxExposure,
      cooldown_minutes: cooldown,
    });
  };

  const estopActive = Boolean(profile?.emergency_stop_active);
  const inputCls =
    'min-h-[36px] w-full rounded border border-line bg-surface px-2.5 text-xs tabular-nums focus:border-cyan focus:outline-none';

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-5 w-5 text-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">{t('risk.title')}</h2>
      </div>

      <Panel className={estopActive ? 'border-bear bg-bear/10 p-4' : 'border-bull/40 bg-bull/5 p-4'}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <OctagonAlert className={`h-5 w-5 ${estopActive ? 'text-bear' : 'text-bull'}`} aria-hidden="true" />
            <span className={estopActive ? 'text-bear' : 'text-bull'}>
              {estopActive ? t('risk.estopActive') : t('risk.estopInactive')}
            </span>
          </div>
          <button
            type="button"
            disabled={estopMut.isPending}
            onClick={() => estopMut.mutate(!estopActive)}
            className={`min-h-[38px] rounded px-4 text-xs font-semibold ${
              estopActive
                ? 'border border-bull bg-surface text-bull hover:bg-elevated'
                : 'bg-bear text-white hover:opacity-90'
            }`}
          >
            {estopActive ? t('risk.clearEstop') : t('risk.activateEstop')}
          </button>
        </div>
      </Panel>

      <Panel title={profile?.name ?? t('risk.title')}>
        <form onSubmit={onSubmit} className="grid gap-3 p-4 sm:grid-cols-2">
          <label className="space-y-1 text-xs">
            <span className="text-mute">Max Risk Per Trade (%)</span>
            <input type="number" step="0.1" min={0.1} max={50} value={maxRiskTrade} onChange={(e) => setMaxRiskTrade(Number(e.target.value))} className={inputCls} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">Max Daily Loss (%)</span>
            <input type="number" step="0.1" min={0.1} max={90} value={maxDailyLoss} onChange={(e) => setMaxDailyLoss(Number(e.target.value))} className={inputCls} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">Max Weekly Loss (%)</span>
            <input type="number" step="0.1" min={0.1} max={95} value={maxWeeklyLoss} onChange={(e) => setMaxWeeklyLoss(Number(e.target.value))} className={inputCls} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">Max Drawdown (%)</span>
            <input type="number" step="0.1" min={0.1} max={95} value={maxDrawdown} onChange={(e) => setMaxDrawdown(Number(e.target.value))} className={inputCls} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">Max Open Positions</span>
            <input type="number" min={1} max={50} value={maxPositions} onChange={(e) => setMaxPositions(Number(e.target.value))} className={inputCls} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">Max Asset Exposure (%)</span>
            <input type="number" step="0.5" min={1} max={100} value={maxExposure} onChange={(e) => setMaxExposure(Number(e.target.value))} className={inputCls} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">Cooldown After Loss (minutes)</span>
            <input type="number" min={0} max={1440} value={cooldown} onChange={(e) => setCooldown(Number(e.target.value))} className={inputCls} />
          </label>
          <div className="flex items-end sm:col-span-2">
            <button type="submit" disabled={saveMut.isPending} className="inline-flex min-h-[38px] items-center gap-1.5 rounded bg-cyan px-4 text-xs font-medium text-bg hover:opacity-90">
              <Save className="h-4 w-4" aria-hidden="true" />
              {t('risk.save')}
            </button>
          </div>
          {savedMsg && <p className="text-xs text-bull sm:col-span-2">{savedMsg}</p>}
        </form>
      </Panel>
    </div>
  );
}
