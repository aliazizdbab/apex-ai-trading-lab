import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Code2, Play, Save, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import {
  analyzePineScript,
  ApiError,
  executePineScript,
  listPineScripts,
  savePineScript,
  type PineAnalysisResponse,
} from '@/services/api';
import { Panel } from '@/ui/Panel';
import { fmtPrice } from '@/utils/format';

export function PineStudioPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { rows: markets } = useLiveMarkets();
  const { data: scriptsData } = useQuery({ queryKey: ['pine-scripts'], queryFn: listPineScripts });
  const scripts = scriptsData?.items ?? [];

  const [selectedId, setSelectedId] = useState<string>('');
  const [sourceCode, setSourceCode] = useState<string>('');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [inputOverrides, setInputOverrides] = useState<Record<string, number | string | boolean>>({});
  const [analysis, setAnalysis] = useState<PineAnalysisResponse | null>(null);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!sourceCode && scripts[0]?.current_version) {
      setSelectedId(scripts[0].id);
      setSourceCode(scripts[0].current_version.source_code);
    }
  }, [scripts, sourceCode]);

  const analyzeMut = useMutation({
    mutationFn: analyzePineScript,
    onSuccess: (res) => {
      setErrMsg(null);
      setAnalysis(res);
      const defs: Record<string, number | string | boolean> = {};
      for (const inp of res.inputs) defs[inp.name] = inp.default;
      setInputOverrides(defs);
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Analyze failed'),
  });

  const execMut = useMutation({
    mutationFn: executePineScript,
    onSuccess: (res) => {
      setErrMsg(null);
      setAnalysis(res.analysis);
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Execution failed'),
  });

  const saveMut = useMutation({
    mutationFn: savePineScript,
    onSuccess: () => {
      setErrMsg(null);
      queryClient.invalidateQueries({ queryKey: ['pine-scripts'] });
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Save failed'),
  });

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Code2 className="h-5 w-5 text-cyan" aria-hidden="true" />
          <div>
            <h2 className="text-lg font-semibold">{t('pine.title')}</h2>
            <p className="text-xs text-mute">{t('pine.subtitle')}</p>
          </div>
        </div>
        <select
          value={selectedId}
          onChange={(e) => {
            const id = e.target.value;
            setSelectedId(id);
            const found = scripts.find((s) => s.id === id);
            if (found?.current_version) setSourceCode(found.current_version.source_code);
          }}
          className="min-h-[36px] rounded border border-line bg-surface px-3 text-xs"
        >
          {scripts.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} (v{s.version_count})
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <Panel title="Pine Script Editor (v5 / v6)">
          <div className="space-y-3 p-4">
            <textarea
              dir="ltr"
              rows={15}
              value={sourceCode}
              onChange={(e) => setSourceCode(e.target.value)}
              className="w-full rounded border border-line bg-bg p-3 font-mono text-xs text-ink focus:border-cyan focus:outline-none"
            />
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => analyzeMut.mutate(sourceCode)}
                className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-cyan bg-surface px-3 text-xs font-medium text-cyan hover:bg-elevated"
              >
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                {t('pine.analyze')}
              </button>
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="min-h-[36px] rounded border border-line bg-surface px-2 text-xs">
                {markets.map((m) => (
                  <option key={m.symbol} value={m.symbol}>{m.symbol}</option>
                ))}
              </select>
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="min-h-[36px] rounded border border-line bg-surface px-2 text-xs">
                {TIMEFRAMES.map((tf) => (
                  <option key={tf.id} value={tf.id}>{tf.id}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() =>
                  execMut.mutate({ source_code: sourceCode, symbol, timeframe, limit: 150, input_overrides: inputOverrides })
                }
                className="inline-flex min-h-[36px] items-center gap-1.5 rounded bg-cyan px-3 text-xs font-medium text-bg hover:opacity-90"
              >
                <Play className="h-4 w-4" aria-hidden="true" />
                {t('pine.execute')}
              </button>
              <button
                type="button"
                onClick={() => saveMut.mutate({ script_id: selectedId || undefined, source_code: sourceCode })}
                className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs hover:border-cyan"
              >
                <Save className="h-4 w-4" aria-hidden="true" />
                {t('pine.save')}
              </button>
            </div>
            {errMsg && <p className="text-xs text-bear">{errMsg}</p>}
          </div>
        </Panel>

        <div className="flex flex-col gap-4">
          {analysis && (
            <Panel title="AST & Compatibility Report">
              <div className="space-y-3 p-4 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{analysis.title}</span>
                  <span className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono">
                    v{analysis.pine_version} · {analysis.script_type}
                  </span>
                </div>
                <p className={analysis.compat_report.supported ? 'font-medium text-bull' : 'font-medium text-bear'}>
                  {analysis.compat_report.supported ? t('pine.supported') : t('pine.unsupported')}
                </p>
                {analysis.compat_report.unsupported_features.length > 0 && (
                  <ul className="list-disc ps-4 text-bear">
                    {analysis.compat_report.unsupported_features.map((u, i) => (
                      <li key={i}>{u}</li>
                    ))}
                  </ul>
                )}
                {analysis.compat_report.repaint_warnings.length > 0 && (
                  <div className="rounded border border-amber/40 bg-amber/10 p-2 text-amber">
                    <div className="flex items-center gap-1 font-semibold">
                      <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
                      Repainting Warning
                    </div>
                    {analysis.compat_report.repaint_warnings.map((w, i) => (
                      <p key={i} className="mt-1">{w}</p>
                    ))}
                  </div>
                )}
                <div className="text-mute">
                  Built-ins: <span className="font-mono">{analysis.builtin_indicators.join(', ') || 'none'}</span>
                </div>
                <div className="text-mute">
                  AST Statements: <span className="num font-mono">{analysis.ast.statement_count}</span>
                </div>
              </div>
            </Panel>
          )}

          {analysis && analysis.inputs.length > 0 && (
            <Panel title={t('pine.inputsTitle')}>
              <div className="space-y-2 p-4 text-xs">
                {analysis.inputs.map((inp) => (
                  <label key={inp.name} className="block space-y-1">
                    <span className="text-mute">{inp.title} ({inp.name})</span>
                    <input
                      type={inp.type === 'int' || inp.type === 'float' ? 'number' : 'text'}
                      value={String(inputOverrides[inp.name] ?? inp.default)}
                      onChange={(e) =>
                        setInputOverrides((prev) => ({
                          ...prev,
                          [inp.name]:
                            inp.type === 'int'
                              ? parseInt(e.target.value, 10) || Number(inp.default)
                              : inp.type === 'float'
                                ? parseFloat(e.target.value) || Number(inp.default)
                                : e.target.value,
                        }))
                      }
                      className="min-h-[34px] w-full rounded border border-line bg-surface px-2.5 tabular-nums"
                    />
                  </label>
                ))}
              </div>
            </Panel>
          )}

          {execMut.data && (
            <Panel title="Execution Output">
              <div className="space-y-2 p-4 text-xs">
                <div className="flex gap-4 font-mono">
                  <span className="text-bull">Entries: {execMut.data.entry_count}</span>
                  <span className="text-bear">Exits: {execMut.data.exit_count}</span>
                </div>
                {Object.entries(execMut.data.plots).map(([title, pts]) => (
                  <div key={title} className="flex justify-between border-t border-line pt-1.5">
                    <span className="text-mute">{title}</span>
                    <span className="num font-mono">
                      {pts.length > 0 ? fmtPrice(pts[pts.length - 1]!.value) : '—'}
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
