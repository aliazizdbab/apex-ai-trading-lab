import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CandlestickChart, Eye, EyeOff, Library, Play, Save, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { DynamicParamFields } from '@/features/indicators/DynamicParamFields';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import {
  ApiError,
  computeIndicators,
  createIndicatorPreset,
  deleteIndicatorPreset,
  fetchIndicatorCatalog,
  listIndicatorPresets,
  updateIndicatorPreset,
  type IndicatorCatalogItem,
} from '@/services/api';
import { Panel } from '@/ui/Panel';
import { Sparkline } from '@/ui/Sparkline';
import { fmtPrice } from '@/utils/format';

type CategoryFilter = 'all' | 'trend' | 'momentum' | 'volatility' | 'volume';

function defaultParamsFor(spec: IndicatorCatalogItem): Record<string, number | string> {
  const out: Record<string, number | string> = {};
  for (const p of spec.parameters) out[p.name] = p.default;
  return out;
}

export function IndicatorLibraryPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { rows: markets } = useLiveMarkets();

  const { data: catalogData, isLoading: catalogLoading } = useQuery({
    queryKey: ['indicator-catalog'],
    queryFn: fetchIndicatorCatalog,
  });

  const { data: presetsData } = useQuery({
    queryKey: ['indicator-presets'],
    queryFn: listIndicatorPresets,
  });

  const catalog = catalogData?.items ?? [];
  const presets = presetsData?.items ?? [];

  const [catFilter, setCatFilter] = useState<CategoryFilter>('all');
  const [selectedId, setSelectedId] = useState<string>('ema');
  const [paramValues, setParamValues] = useState<Record<string, number | string>>({});
  const [previewSymbol, setPreviewSymbol] = useState('BTC/USDT');
  const [previewTf, setPreviewTf] = useState('15m');
  const [presetName, setPresetName] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);

  const filteredCatalog = useMemo(
    () => (catFilter === 'all' ? catalog : catalog.filter((c) => c.category === catFilter)),
    [catalog, catFilter],
  );

  const selectedSpec = useMemo(
    () => catalog.find((c) => c.id === selectedId) ?? catalog[0] ?? null,
    [catalog, selectedId],
  );

  useEffect(() => {
    if (!selectedSpec) return;
    setParamValues(defaultParamsFor(selectedSpec));
    setPresetName(`${selectedSpec.id.toUpperCase()} (${Object.values(defaultParamsFor(selectedSpec))[0] ?? ''})`);
    setSaveError(null);
  }, [selectedSpec?.id]);

  const previewMut = useMutation({
    mutationFn: computeIndicators,
  });

  const runPreview = () => {
    if (!selectedSpec) return;
    previewMut.mutate({
      symbol: previewSymbol,
      timeframe: previewTf,
      limit: 150,
      candle_mode: 'standard',
      indicators: [{ instance_id: 'preview', indicator_id: selectedSpec.id, params: paramValues }],
    });
  };

  useEffect(() => {
    if (selectedSpec && Object.keys(paramValues).length > 0) {
      runPreview();
    }
  }, [selectedSpec?.id, previewSymbol, previewTf]);

  const createPresetMut = useMutation({
    mutationFn: createIndicatorPreset,
    onSuccess: () => {
      setSaveError(null);
      queryClient.invalidateQueries({ queryKey: ['indicator-presets'] });
    },
    onError: (err) => {
      setSaveError(err instanceof ApiError ? err.detail : 'Failed to save preset');
    },
  });

  const togglePresetMut = useMutation({
    mutationFn: ({ id, visible }: { id: string; visible: boolean }) =>
      updateIndicatorPreset(id, { visible }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['indicator-presets'] }),
  });

  const deletePresetMut = useMutation({
    mutationFn: deleteIndicatorPreset,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['indicator-presets'] }),
  });

  const onSavePreset = (e: FormEvent) => {
    e.preventDefault();
    if (!selectedSpec) return;
    createPresetMut.mutate({
      indicator_id: selectedSpec.id,
      name: presetName.trim() || selectedSpec.name,
      symbol: previewSymbol,
      timeframe: previewTf,
      params: paramValues,
      visible: true,
    });
  };

  const previewOutput = previewMut.data?.outputs[0];

  const categories: { id: CategoryFilter; label: string }[] = [
    { id: 'all', label: t('indLib.catAll') },
    { id: 'trend', label: t('indLib.catTrend') },
    { id: 'momentum', label: t('indLib.catMomentum') },
    { id: 'volatility', label: t('indLib.catVolatility') },
    { id: 'volume', label: t('indLib.catVolume') },
  ];

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Library className="h-5 w-5 text-cyan" aria-hidden="true" />
          <div>
            <h2 className="text-lg font-semibold">{t('indLib.title')}</h2>
            <p className="text-xs text-mute">{t('indLib.subtitle')}</p>
          </div>
        </div>
        <Link
          to={`/terminal?symbol=${encodeURIComponent(previewSymbol)}`}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs font-medium hover:border-cyan hover:text-cyan"
        >
          <CandlestickChart className="h-4 w-4" aria-hidden="true" />
          {t('indLib.openTerminal')}
        </Link>
      </div>

      {/* Category tabs */}
      <div className="flex flex-wrap gap-2">
        {categories.map((cat) => (
          <button
            key={cat.id}
            type="button"
            onClick={() => setCatFilter(cat.id)}
            className={`min-h-[34px] rounded border px-3 text-xs font-medium ${
              catFilter === cat.id
                ? 'border-cyan bg-elevated text-cyan'
                : 'border-line bg-surface text-mute hover:text-ink'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
        {/* Catalog list */}
        <Panel title={`${t('nav.indicatorLibrary')} (${filteredCatalog.length})`}>
          {catalogLoading ? (
            <p className="p-4 text-xs text-mute">{t('common.loading')}</p>
          ) : (
            <ul className="divide-y divide-line">
              {filteredCatalog.map((item) => {
                const active = selectedSpec?.id === item.id;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      className={`w-full border-s-2 px-3 py-2.5 text-start ${
                        active ? 'border-cyan bg-elevated' : 'border-transparent hover:bg-surface'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold">{item.name}</span>
                        <span className="rounded border border-line bg-surface px-1.5 py-0.5 text-[10px] uppercase text-mute">
                          {item.pane === 'overlay' ? t('indLib.paneOverlay') : t('indLib.paneOscillator')}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-mute">{item.description}</p>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        {/* Dynamic Parameter Configurator & Preview */}
        {selectedSpec && (
          <div className="flex flex-col gap-4">
            <Panel title={selectedSpec.name}>
              <div className="space-y-4 p-4">
                <p className="text-xs text-mute">{selectedSpec.description}</p>

                <div className="space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-mute">
                    {t('indLib.paramsTitle')}
                  </h3>
                  <DynamicParamFields
                    parameters={selectedSpec.parameters}
                    values={paramValues}
                    onChange={(name, val) => setParamValues((prev) => ({ ...prev, [name]: val }))}
                  />
                </div>

                <div className="flex flex-wrap items-end gap-3 border-t border-line pt-3">
                  <label className="space-y-1 text-xs">
                    <span className="text-mute">{t('mkt.pair')}</span>
                    <select
                      value={previewSymbol}
                      onChange={(e) => setPreviewSymbol(e.target.value)}
                      className="min-h-[36px] rounded border border-line bg-surface px-2.5 text-xs"
                    >
                      {markets.map((m) => (
                        <option key={m.symbol} value={m.symbol}>
                          {m.symbol}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-xs">
                    <span className="text-mute">{t('term.timeframe')}</span>
                    <select
                      value={previewTf}
                      onChange={(e) => setPreviewTf(e.target.value)}
                      className="min-h-[36px] rounded border border-line bg-surface px-2.5 text-xs"
                    >
                      {TIMEFRAMES.map((tf) => (
                        <option key={tf.id} value={tf.id}>
                          {tf.id}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    onClick={runPreview}
                    disabled={previewMut.isPending}
                    className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-cyan bg-surface px-3 text-xs font-medium text-cyan hover:bg-elevated"
                  >
                    <Play className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('indLib.previewCompute')}
                  </button>
                </div>

                {previewOutput && (
                  <div className="space-y-2 rounded border border-line bg-surface p-3">
                    <p className="text-xs font-semibold">{t('indLib.latestValues')}</p>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {previewOutput.outputs_meta.map((meta) => {
                        const pts = previewOutput.series[meta.key] ?? [];
                        const vals = pts.slice(-30).map((p) => p.value);
                        const latest = vals[vals.length - 1];
                        return (
                          <div key={meta.key} className="rounded border border-line bg-panel p-2.5">
                            <div className="flex items-center justify-between text-xs">
                              <span style={{ color: meta.color }} className="font-medium">
                                {meta.label}
                              </span>
                              <span className="num font-mono font-semibold" dir="ltr">
                                {latest !== undefined ? fmtPrice(latest) : '—'}
                              </span>
                            </div>
                            {vals.length >= 2 && (
                              <div className="mt-2">
                                <Sparkline values={vals} tone="neutral" />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <form onSubmit={onSavePreset} className="flex flex-wrap items-end gap-3 border-t border-line pt-3">
                  <label className="min-w-[200px] flex-1 space-y-1 text-xs">
                    <span className="text-mute">{t('indLib.presetName')}</span>
                    <input
                      type="text"
                      required
                      value={presetName}
                      onChange={(e) => setPresetName(e.target.value)}
                      className="min-h-[36px] w-full rounded border border-line bg-surface px-3 text-xs text-ink focus:border-cyan focus:outline-none"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={createPresetMut.isPending}
                    className="inline-flex min-h-[36px] items-center gap-1.5 rounded bg-cyan px-4 text-xs font-medium text-bg hover:opacity-90 disabled:opacity-50"
                  >
                    <Save className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('indLib.savePreset')}
                  </button>
                </form>
                {saveError && <p className="text-xs text-bear">{saveError}</p>}
              </div>
            </Panel>

            {/* Saved Presets Manager */}
            <Panel title={`${t('indLib.presetsTitle')} (${presets.length})`}>
              {presets.length === 0 ? (
                <p className="p-4 text-xs text-mute">{t('indLib.presetsEmpty')}</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-start text-xs">
                    <thead className="border-b border-line bg-surface text-mute">
                      <tr>
                        <th className="px-3 py-2 text-start font-medium">{t('indLib.presetName')}</th>
                        <th className="px-3 py-2 text-start font-medium">{t('indLib.paramsTitle')}</th>
                        <th className="px-3 py-2 text-center font-medium">{t('indLib.visibleOnChart')}</th>
                        <th className="px-3 py-2 text-end font-medium">{t('common.delete')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {presets.map((p) => (
                        <tr key={p.id}>
                          <td className="px-3 py-2">
                            <div className="font-semibold">{p.name}</div>
                            <div className="text-[11px] uppercase text-mute">{p.indicator_id}</div>
                          </td>
                          <td className="px-3 py-2 font-mono text-[11px] text-mute" dir="ltr">
                            {Object.entries(p.params)
                              .map(([k, v]) => `${k}=${v}`)
                              .join(', ')}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <button
                              type="button"
                              onClick={() => togglePresetMut.mutate({ id: p.id, visible: !p.visible })}
                              aria-pressed={p.visible}
                              className={`inline-flex min-h-[30px] items-center gap-1 rounded border px-2 text-[11px] ${
                                p.visible
                                  ? 'border-cyan/40 bg-cyan/10 text-cyan'
                                  : 'border-line bg-surface text-mute'
                              }`}
                            >
                              {p.visible ? (
                                <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                              ) : (
                                <EyeOff className="h-3.5 w-3.5" aria-hidden="true" />
                              )}
                              {p.indicator_id.toUpperCase()}
                            </button>
                          </td>
                          <td className="px-3 py-2 text-end">
                            <button
                              type="button"
                              onClick={() => deletePresetMut.mutate(p.id)}
                              aria-label={`${t('common.delete')} ${p.name}`}
                              className="inline-flex min-h-[30px] items-center gap-1 rounded border border-line bg-surface px-2 text-bear hover:border-bear"
                            >
                              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>
          </div>
        )}
      </div>
    </div>
  );
}
