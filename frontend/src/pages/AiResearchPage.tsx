import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, Check, Play, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { AiCopilotWorkspace } from '@/features/copilot/AiCopilotWorkspace';
import { useT } from '@/i18n/useT';
import {
  aiRunResearch,
  ApiError,
  decideAiSuggestion,
  listAiSuggestions,
  listBacktests,
  listStrategies,
} from '@/services/api';
import { Panel } from '@/ui/Panel';

export function AiResearchPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { data: btData } = useQuery({ queryKey: ['backtests'], queryFn: listBacktests });
  const { data: stratsData } = useQuery({ queryKey: ['strategies'], queryFn: listStrategies });
  const { data: sugData } = useQuery({ queryKey: ['ai-suggestions'], queryFn: listAiSuggestions });

  const backtests = btData?.items ?? [];
  const strategies = stratsData?.items ?? [];
  const suggestions = sugData?.items ?? [];

  const [backtestJobId, setBacktestJobId] = useState('');
  const [strategyId, setStrategyId] = useState('');
  const [prompt, setPrompt] = useState('Analyze drawdown, win rate, and propose safer parameter ranges.');
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const effectiveBtId = backtestJobId || backtests[0]?.id || '';
  const effectiveStratId = strategyId || strategies[0]?.id || '';

  const runMut = useMutation({
    mutationFn: aiRunResearch,
    onSuccess: () => {
      setErrMsg(null);
      queryClient.invalidateQueries({ queryKey: ['ai-suggestions'] });
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'AI research analysis failed'),
  });

  const decideMut = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: 'approved' | 'rejected' }) =>
      decideAiSuggestion(id, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-suggestions'] }),
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Decision update failed'),
  });

  const onAnalyze = (e: FormEvent) => {
    e.preventDefault();
    runMut.mutate({
      backtest_job_id: effectiveBtId || undefined,
      strategy_id: effectiveStratId || undefined,
      prompt: prompt.trim() || undefined,
    });
  };

  const inputCls =
    'min-h-[36px] w-full rounded border border-line bg-surface px-2.5 text-xs text-ink focus:border-cyan focus:outline-none';

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-cyan" aria-hidden="true" />
          <div>
            <h2 className="text-lg font-semibold">{t('ai.researchTitle')}</h2>
            <p className="text-xs text-mute">
              Interactive Quant Chatbot with Provider API settings & full-app tool calling + owner-approved suggestion queue.
            </p>
          </div>
        </div>
      </div>

      {/* Full-Screen Agentic AI Copilot Studio */}
      <AiCopilotWorkspace mode="page" />

      {errMsg && (
        <div className="rounded-md border border-bear/40 bg-bear/10 px-3 py-2 text-xs text-bear">{errMsg}</div>
      )}

      <Panel title={t('ai.analyzeBtn')}>
        <form onSubmit={onAnalyze} className="grid grid-cols-1 gap-3 p-4 md:grid-cols-12">
          <label className="text-xs text-mute md:col-span-4">
            Backtest Run
            <select value={effectiveBtId} onChange={(e) => setBacktestJobId(e.target.value)} className={`${inputCls} mt-1`}>
              <option value="">Latest / Optional</option>
              {backtests.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.strategy_name} ({b.symbol} {b.timeframe}) · {b.total_return_pct.toFixed(2)}%
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-mute md:col-span-3">
            Strategy
            <select value={effectiveStratId} onChange={(e) => setStrategyId(e.target.value)} className={`${inputCls} mt-1`}>
              <option value="">Select Strategy</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.status})
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-mute md:col-span-3">
            Research Focus
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className={`${inputCls} mt-1`}
            />
          </label>
          <div className="flex items-end md:col-span-2">
            <button
              type="submit"
              disabled={runMut.isPending}
              className="flex min-h-[36px] w-full items-center justify-center gap-1.5 rounded bg-cyan px-3 text-xs font-semibold text-base hover:bg-cyan/90 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" aria-hidden="true" />
              {runMut.isPending ? 'Analyzing…' : t('ai.analyzeBtn')}
            </button>
          </div>
        </form>

        {runMut.data && (
          <div className="mx-4 mb-4 rounded-md border border-cyan/30 bg-cyan/5 p-3 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2 font-semibold text-cyan">
              <span>
                {runMut.data.strategy_name} ({runMut.data.symbol})
              </span>
              <span className="rounded bg-surface px-2 py-0.5 text-[11px] text-mute">
                provider: {runMut.data.provider_used} · status: {runMut.data.status}
              </span>
            </div>
            <p className="mt-1.5 text-ink">{runMut.data.summary}</p>
          </div>
        )}
      </Panel>

      <Panel title={t('ai.suggestionsTitle')} actions={<span className="text-xs text-mute">{suggestions.length} total</span>}>
        {suggestions.length === 0 ? (
          <p className="p-4 text-xs text-mute">No AI suggestions generated yet.</p>
        ) : (
          <div className="flex flex-col gap-2 p-4">
            {suggestions.map((sug) => (
              <div
                key={sug.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-line bg-surface p-3 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-panel px-1.5 py-0.5 font-mono text-[11px] text-cyan">
                      {sug.kind}
                    </span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                        sug.status === 'approved'
                          ? 'bg-bull/15 text-bull'
                          : sug.status === 'rejected'
                            ? 'bg-bear/15 text-bear'
                            : 'bg-warn/15 text-warn'
                      }`}
                    >
                      {sug.status}
                    </span>
                    <span className="text-[11px] text-mute">{sug.created_at}</span>
                  </div>
                  <p className="mt-1.5 font-medium text-ink">{sug.prompt}</p>
                  <p className="mt-1 text-mute">{sug.explanation}</p>
                  {Object.keys(sug.proposal).length > 0 && (
                    <pre className="mt-2 overflow-x-auto rounded border border-line bg-base/60 p-2 text-[11px] text-ink/90">
                      {JSON.stringify(sug.proposal, null, 2)}
                    </pre>
                  )}
                </div>
                {sug.status === 'pending' && (
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      disabled={decideMut.isPending}
                      onClick={() => decideMut.mutate({ id: sug.id, decision: 'approved' })}
                      className="inline-flex min-h-[32px] items-center gap-1 rounded border border-bull/40 bg-bull/15 px-2.5 text-xs font-medium text-bull hover:bg-bull/25"
                    >
                      <Check className="h-3.5 w-3.5" aria-hidden="true" />
                      {t('ai.approve')}
                    </button>
                    <button
                      type="button"
                      disabled={decideMut.isPending}
                      onClick={() => decideMut.mutate({ id: sug.id, decision: 'rejected' })}
                      className="inline-flex min-h-[32px] items-center gap-1 rounded border border-bear/40 bg-bear/15 px-2.5 text-xs font-medium text-bear hover:bg-bear/25"
                    >
                      <X className="h-3.5 w-3.5" aria-hidden="true" />
                      {t('ai.reject')}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
