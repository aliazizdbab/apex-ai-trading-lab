import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Bot,
  CheckCircle2,
  ExternalLink,
  FlaskConical,
  KeyRound,
  Plus,
  Send,
  ShieldAlert,
  Sparkles,
  Trash2,
  Wrench,
  X,
  XCircle,
} from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useT } from '@/i18n/useT';
import {
  ApiError,
  createCopilotConversation,
  deleteCopilotConversation,
  fetchCopilotConfig,
  listCopilotConversations,
  listStrategies,
  sendCopilotChat,
  testCopilotConnection,
  updateCopilotConfig,
  type CopilotAutonomyLevel,
  type CopilotChatMessage,
  type CopilotProviderId,
  type CopilotToolAction,
} from '@/services/api';
import { useUiStore } from '@/stores/uiStore';

interface Props {
  mode?: 'drawer' | 'page';
  onClose?: () => void;
}

function ToolActionCard({
  action,
  openLabel,
  onNavigate,
}: {
  action: CopilotToolAction;
  openLabel: string;
  onNavigate: (route: string) => void;
}) {
  const data = action.data ?? {};
  const btMetrics =
    action.tool === 'run_backtest' && data.metrics && typeof data.metrics === 'object'
      ? (data.metrics as Record<string, number>)
      : null;
  const wfOos =
    action.tool === 'run_walk_forward' &&
    data.out_of_sample_metrics &&
    typeof data.out_of_sample_metrics === 'object'
      ? (data.out_of_sample_metrics as Record<string, number>)
      : null;

  return (
    <div
      className={`rounded border p-2 text-[11px] ${
        action.ok ? 'border-cyan/30 bg-panel/90' : 'border-bear/40 bg-bear/10'
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <div className="flex items-center gap-1.5 font-semibold text-ink">
          {action.ok ? (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-bull" aria-hidden="true" />
          ) : (
            <XCircle className="h-3.5 w-3.5 shrink-0 text-bear" aria-hidden="true" />
          )}
          <span>{action.title}</span>
        </div>
        {action.route && (
          <button
            type="button"
            onClick={() => onNavigate(action.route!)}
            className="inline-flex items-center gap-1 rounded border border-line bg-surface px-1.5 py-0.5 text-[10px] font-medium text-cyan hover:border-cyan"
          >
            {openLabel}
            <ExternalLink className="h-2.5 w-2.5" aria-hidden="true" />
          </button>
        )}
      </div>

      {action.error && <p className="mt-1 text-bear">{action.error}</p>}

      {btMetrics && (
        <div className="mt-1.5 grid grid-cols-4 gap-1.5 text-[10px]">
          <div className="rounded bg-surface px-1.5 py-1">
            <div className="text-mute">Return</div>
            <div className={`num font-semibold ${(btMetrics.total_return_pct ?? 0) >= 0 ? 'text-bull' : 'text-bear'}`}>
              {(btMetrics.total_return_pct ?? 0).toFixed(2)}%
            </div>
          </div>
          <div className="rounded bg-surface px-1.5 py-1">
            <div className="text-mute">Win Rate</div>
            <div className="num font-semibold">{(btMetrics.win_rate_pct ?? 0).toFixed(1)}%</div>
          </div>
          <div className="rounded bg-surface px-1.5 py-1">
            <div className="text-mute">Max DD</div>
            <div className="num font-semibold text-bear">-{(btMetrics.max_drawdown_pct ?? 0).toFixed(2)}%</div>
          </div>
          <div className="rounded bg-surface px-1.5 py-1">
            <div className="text-mute">Sharpe</div>
            <div className="num font-semibold text-cyan">{(btMetrics.sharpe_ratio ?? 0).toFixed(2)}</div>
          </div>
        </div>
      )}

      {wfOos && (
        <div className="mt-1.5 flex flex-wrap gap-2 text-[10px] text-mute">
          <span>
            Best SL/TP:{' '}
            <strong className="num text-ink">
              {String((data.best_params as Record<string, unknown>)?.stop_loss_pct ?? '-')}% /{' '}
              {String((data.best_params as Record<string, unknown>)?.take_profit_pct ?? '-')}%
            </strong>
          </span>
          <span>
            OOS Return:{' '}
            <strong className="num text-cyan">{(wfOos.total_return_pct ?? 0).toFixed(2)}%</strong>
          </span>
          {data.applied_version_no != null && (
            <span className="text-bull">Saved v{String(data.applied_version_no)}</span>
          )}
        </div>
      )}

      {(action.tool === 'create_strategy' || action.tool === 'modify_strategy') && action.ok && (
        <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-mute">
          <span>{String(data.symbol ?? '')}</span>
          <span>· {String(data.timeframe ?? '')}</span>
          <span>· SL {String(data.stop_loss_pct ?? '')}%</span>
          <span>· TP {String(data.take_profit_pct ?? '')}%</span>
          <span>· {String(data.status ?? '')}</span>
        </div>
      )}

      {action.tool === 'execute_paper_order' && action.ok && (
        <div className="mt-1 text-[10px] text-mute">
          Filled qty <strong className="num text-ink">{String(data.qty ?? '')}</strong> @{' '}
          <strong className="num text-ink">${String(data.price ?? '')}</strong> (Paper isolated)
        </div>
      )}
    </div>
  );
}

export function AiCopilotWorkspace({ mode = 'page', onClose }: Props) {
  const t = useT();
  const lang = useUiStore((s) => s.lang);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: cfg } = useQuery({ queryKey: ['copilot-config'], queryFn: fetchCopilotConfig });
  const { data: convData } = useQuery({
    queryKey: ['copilot-conversations'],
    queryFn: listCopilotConversations,
  });
  const { data: stratsData } = useQuery({ queryKey: ['strategies'], queryFn: listStrategies });

  const conversations = convData?.items ?? [];
  const strategies = stratsData?.items ?? [];

  const [showSettings, setShowSettings] = useState(false);
  const [activeConvId, setActiveConvId] = useState<string>('');
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>('');
  const [inputMsg, setInputMsg] = useState('');
  const [localMessages, setLocalMessages] = useState<CopilotChatMessage[]>([]);
  const [quickPrompts, setQuickPrompts] = useState<string[]>([]);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  // Provider config draft state
  const [provider, setProvider] = useState<CopilotProviderId>('builtin');
  const [modelName, setModelName] = useState('apex-quant-copilot-v1');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [autonomy, setAutonomy] = useState<CopilotAutonomyLevel>('full_copilot');
  const [sysInstructions, setSysInstructions] = useState('');

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (cfg) {
      setProvider(cfg.provider);
      setModelName(cfg.model_name);
      setBaseUrl(cfg.base_url);
      setAutonomy(cfg.autonomy_level);
      setSysInstructions(cfg.system_instructions);
    }
  }, [cfg]);

  useEffect(() => {
    if (!activeConvId && conversations.length > 0) {
      setActiveConvId(conversations[0].id);
      setLocalMessages(conversations[0].messages);
    } else if (activeConvId) {
      const matched = conversations.find((c) => c.id === activeConvId);
      if (matched) {
        setLocalMessages(matched.messages);
      }
    }
  }, [activeConvId, conversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [localMessages.length]);

  const saveCfgMut = useMutation({
    mutationFn: updateCopilotConfig,
    onSuccess: (updated) => {
      setErrMsg(null);
      setApiKeyInput('');
      queryClient.setQueryData(['copilot-config'], updated);
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Failed to save provider config'),
  });

  const testMut = useMutation({
    mutationFn: testCopilotConnection,
  });

  const newConvMut = useMutation({
    mutationFn: createCopilotConversation,
    onSuccess: (conv) => {
      setActiveConvId(conv.id);
      setLocalMessages([]);
      setQuickPrompts([]);
      queryClient.invalidateQueries({ queryKey: ['copilot-conversations'] });
    },
  });

  const delConvMut = useMutation({
    mutationFn: deleteCopilotConversation,
    onSuccess: () => {
      setActiveConvId('');
      setLocalMessages([]);
      queryClient.invalidateQueries({ queryKey: ['copilot-conversations'] });
    },
  });

  const chatMut = useMutation({
    mutationFn: sendCopilotChat,
    onSuccess: (res) => {
      setErrMsg(null);
      setActiveConvId(res.conversation_id);
      setLocalMessages(res.messages);
      setQuickPrompts(res.quick_prompts);
      queryClient.invalidateQueries({ queryKey: ['copilot-conversations'] });
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      queryClient.invalidateQueries({ queryKey: ['backtests'] });
      queryClient.invalidateQueries({ queryKey: ['paper-overview'] });
      queryClient.invalidateQueries({ queryKey: ['risk-profile'] });
      queryClient.invalidateQueries({ queryKey: ['ai-suggestions'] });
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Copilot turn failed'),
  });

  const handleProviderChange = (nextProv: CopilotProviderId) => {
    setProvider(nextProv);
    const meta = cfg?.providers.find((p) => p.id === nextProv);
    if (meta) {
      setModelName(meta.default_model);
      setBaseUrl(meta.default_base_url);
    }
  };

  const handleSaveConfig = (e: FormEvent) => {
    e.preventDefault();
    saveCfgMut.mutate({
      provider,
      model_name: modelName.trim() || 'apex-quant-copilot-v1',
      base_url: baseUrl.trim(),
      api_key: apiKeyInput.trim() || undefined,
      autonomy_level: autonomy,
      system_instructions: sysInstructions,
      enabled: true,
    });
  };

  const handleSendText = (text: string) => {
    const clean = text.trim();
    if (!clean || chatMut.isPending) return;
    setInputMsg('');
    setLocalMessages((prev) => [...prev, { role: 'user', content: clean }]);
    chatMut.mutate({
      conversation_id: activeConvId || undefined,
      message: clean,
      active_page: pathname,
      active_strategy_id: selectedStrategyId || undefined,
      language_hint: lang,
    });
  };

  const onSubmitChat = (e: FormEvent) => {
    e.preventDefault();
    handleSendText(inputMsg);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendText(inputMsg);
    }
  };

  const handleNavigate = (route: string) => {
    navigate(route);
    if (mode === 'drawer' && onClose) {
      onClose();
    }
  };

  const defaultStarters =
    lang === 'ar'
      ? [
          'حلل أداء استراتيجياتي الحالية واقترح تعديلاً بناءً على وضع السوق',
          'أنشئ استراتيجية زخم على SOL/USDT إطار 15m وشغل باك تيست',
          'شغل Walk-Forward Optimization على الاستراتيجية النشطة وطبق أفضل إعدادات',
          'افحص الإشارات الحية على ETH/USDT ثم نفذ شراء 0.25 في الحساب الورقي',
        ]
      : [
          'Analyze my current strategies and suggest improvements for current market regime',
          'Create a SOL/USDT 15m momentum strategy and run a backtest',
          'Run Walk-Forward 70/30 optimization and apply the best SL/TP',
          'Evaluate live signals on ETH/USDT and execute a 0.25 paper buy',
        ];

  const displayedPrompts = quickPrompts.length > 0 ? quickPrompts : defaultStarters;
  const inputCls =
    'min-h-[34px] w-full rounded border border-line bg-surface px-2.5 text-xs text-ink focus:border-cyan focus:outline-none';

  return (
    <div
      className={`flex flex-col overflow-hidden rounded-md border border-line bg-panel ${
        mode === 'drawer' ? 'h-full rounded-none border-0' : 'h-[680px]'
      }`}
    >
      {/* Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-cyan/15 text-cyan">
            <Bot className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h3 className="truncate text-sm font-semibold">{t('copilot.title')}</h3>
              <span className="hidden rounded bg-panel px-1.5 py-0.5 font-mono text-[10px] text-cyan sm:inline">
                {cfg ? `${cfg.provider}:${cfg.model_name}` : 'builtin'}
              </span>
            </div>
            <p className="truncate text-[11px] text-mute">{t('copilot.subtitle')}</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setShowSettings((v) => !v)}
            className={`inline-flex min-h-[32px] items-center gap-1 rounded border px-2 text-xs transition ${
              showSettings
                ? 'border-cyan bg-cyan/15 text-cyan'
                : 'border-line bg-panel text-ink hover:border-cyan/60'
            }`}
          >
            <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
            <span>{t('copilot.settingsToggle')}</span>
          </button>

          <button
            type="button"
            onClick={() => newConvMut.mutate(undefined)}
            title={t('copilot.newChat')}
            className="inline-flex min-h-[32px] items-center gap-1 rounded border border-line bg-panel px-2 text-xs text-ink hover:border-cyan/60"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">{t('copilot.newChat')}</span>
          </button>

          {mode === 'drawer' && onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close Copilot"
              className="flex h-8 w-8 items-center justify-center rounded text-mute hover:bg-panel hover:text-ink"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      {/* Conversation Selector + Page/Strategy Context */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-panel px-3 py-1.5 text-[11px]">
        <select
          value={activeConvId}
          onChange={(e) => {
            const id = e.target.value;
            setActiveConvId(id);
            const found = conversations.find((c) => c.id === id);
            setLocalMessages(found ? found.messages : []);
          }}
          aria-label="Conversation Thread"
          className="h-7 min-w-0 max-w-[200px] flex-1 rounded border border-line bg-surface px-2 text-[11px] text-ink"
        >
          {conversations.length === 0 && <option value="">{t('copilot.newChat')}</option>}
          {conversations.map((c) => (
            <option key={c.id} value={c.id}>
              {c.topic}
            </option>
          ))}
        </select>

        {activeConvId && (
          <button
            type="button"
            onClick={() => delConvMut.mutate(activeConvId)}
            aria-label="Delete session"
            className="flex h-7 w-7 items-center justify-center rounded border border-line bg-surface text-mute hover:border-bear/60 hover:text-bear"
          >
            <Trash2 className="h-3 w-3" aria-hidden="true" />
          </button>
        )}

        <select
          value={selectedStrategyId}
          onChange={(e) => setSelectedStrategyId(e.target.value)}
          aria-label="Target Strategy"
          className="h-7 min-w-0 max-w-[210px] rounded border border-line bg-surface px-2 text-[11px] text-ink"
        >
          <option value="">Auto Strategy Context ({strategies[0]?.name ?? 'Default'})</option>
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.status})
            </option>
          ))}
        </select>

        <span className="ms-auto hidden items-center gap-1 text-mute sm:inline-flex">
          <Wrench className="h-3 w-3 text-cyan" aria-hidden="true" />
          {pathname}
        </span>
      </div>

      {/* Expandable Multi-Provider + API Settings */}
      {showSettings && (
        <form onSubmit={handleSaveConfig} className="space-y-2.5 border-b border-line bg-surface/90 p-3 text-xs">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="text-[11px] text-mute">
              {t('copilot.provider')}
              <select
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value as CopilotProviderId)}
                className={`${inputCls} mt-1`}
              >
                {(cfg?.providers ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-[11px] text-mute">
              {t('copilot.model')}
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className={`${inputCls} mt-1 font-mono`}
              />
            </label>
          </div>

          {provider !== 'builtin' && (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="text-[11px] text-mute">
                {t('copilot.apiKey')}
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder={cfg?.has_api_key ? `Saved: ${cfg.api_key_masked}` : 'Paste API Key...'}
                  className={`${inputCls} mt-1 font-mono`}
                />
              </label>

              {(provider === 'custom' ||
                provider === 'openrouter' ||
                provider === 'openai' ||
                provider === 'deepseek') && (
                <label className="text-[11px] text-mute">
                  {t('copilot.baseUrl')}
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://api.openai.com/v1"
                    className={`${inputCls} mt-1 font-mono`}
                  />
                </label>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="text-[11px] text-mute">
              {t('copilot.autonomy')}
              <select
                value={autonomy}
                onChange={(e) => setAutonomy(e.target.value as CopilotAutonomyLevel)}
                className={`${inputCls} mt-1`}
              >
                <option value="full_copilot">{t('copilot.autonomyFull')}</option>
                <option value="research_and_paper">{t('copilot.autonomyPaper')}</option>
                <option value="research_only">{t('copilot.autonomyResearch')}</option>
              </select>
            </label>

            <label className="text-[11px] text-mute">
              {t('copilot.instructions')}
              <input
                type="text"
                value={sysInstructions}
                onChange={(e) => setSysInstructions(e.target.value)}
                placeholder="e.g. Prefer tight SL 1.5% and verify Walk-Forward"
                className={`${inputCls} mt-1`}
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button
              type="submit"
              disabled={saveCfgMut.isPending}
              className="min-h-[32px] rounded bg-cyan px-3 text-xs font-semibold text-base hover:bg-cyan/90 disabled:opacity-50"
            >
              {saveCfgMut.isPending ? 'Saving…' : t('copilot.saveConfig')}
            </button>

            <button
              type="button"
              disabled={testMut.isPending}
              onClick={() =>
                testMut.mutate({
                  provider,
                  model_name: modelName,
                  base_url: baseUrl,
                  api_key: apiKeyInput.trim() || undefined,
                })
              }
              className="min-h-[32px] rounded border border-line bg-panel px-3 text-xs font-medium text-ink hover:border-cyan"
            >
              {testMut.isPending ? 'Testing…' : t('copilot.testConn')}
            </button>

            {testMut.data && (
              <span className={`text-[11px] ${testMut.data.ok ? 'text-bull' : 'text-bear'}`}>
                {testMut.data.message}
              </span>
            )}
          </div>
        </form>
      )}

      {errMsg && (
        <div className="flex items-center gap-2 border-b border-bear/40 bg-bear/10 px-3 py-2 text-xs text-bear">
          <ShieldAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{errMsg}</span>
        </div>
      )}

      {/* Messages Stream */}
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {localMessages.length === 0 && (
          <div className="rounded-md border border-dashed border-line bg-surface/60 p-4 text-xs">
            <div className="flex items-center gap-2 font-semibold text-cyan">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              <span>{t('copilot.title')}</span>
            </div>
            <p className="mt-1.5 leading-relaxed text-mute">
              {lang === 'ar'
                ? 'لدي صلاحية كاملة للتناقش معك وتنفيذ كل المهام مباشرة داخل التطبيق: إنشاء وتعديل الاستراتيجيات، تشغيل الباك-تيست، تحسين Walk-Forward، فحص الإشارات الحية، والتنفيذ الورقي.'
                : 'I have full tool-calling access across APEX: synthesize & edit strategies, run deterministic backtests, execute 70/30 Walk-Forward optimization, evaluate live MEXC signals, tune RiskEngine limits, and trade in the Paper account.'}
            </p>
            <div className="mt-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {defaultStarters.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => handleSendText(prompt)}
                  className="rounded border border-line bg-panel px-2.5 py-2 text-start text-[11px] text-ink transition hover:border-cyan/60 hover:bg-surface"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {localMessages.map((msg, idx) => (
          <div
            key={`${idx}-${msg.created_at ?? 'm'}`}
            className={`flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div
              className={`max-w-[94%] rounded-md border px-3 py-2 text-xs ${
                msg.role === 'user'
                  ? 'border-cyan/40 bg-cyan/15 text-ink'
                  : 'border-line bg-surface text-ink'
              }`}
            >
              {msg.fallback_warning && (
                <div className="mb-1.5 rounded border border-warn/40 bg-warn/10 px-2 py-1 text-[10px] text-warn">
                  {msg.fallback_warning}
                </div>
              )}

              <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

              {msg.tool_actions && msg.tool_actions.length > 0 && (
                <div className="mt-2.5 space-y-1.5">
                  {msg.tool_actions.map((act, aIdx) => (
                    <ToolActionCard
                      key={`${act.tool}-${aIdx}`}
                      action={act}
                      openLabel={t('copilot.openPage')}
                      onNavigate={handleNavigate}
                    />
                  ))}
                </div>
              )}

              {msg.provider_used && (
                <div className="mt-1.5 flex items-center gap-1 text-[10px] text-mute">
                  <Activity className="h-3 w-3 text-cyan" aria-hidden="true" />
                  <span>{msg.provider_used}</span>
                </div>
              )}
            </div>
          </div>
        ))}

        {chatMut.isPending && (
          <div className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-xs text-mute">
            <FlaskConical className="h-3.5 w-3.5 animate-spin text-cyan" aria-hidden="true" />
            <span>{lang === 'ar' ? 'جاري التحليل وتنفيذ أدوات النظام…' : 'Analyzing & executing APEX tools…'}</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Follow-up Prompt Chips */}
      {localMessages.length > 0 && displayedPrompts.length > 0 && (
        <div className="flex gap-1.5 overflow-x-auto border-t border-line bg-surface/60 px-3 py-1.5">
          {displayedPrompts.map((qp) => (
            <button
              key={qp}
              type="button"
              onClick={() => handleSendText(qp)}
              className="shrink-0 rounded-full border border-line bg-panel px-2.5 py-1 text-[11px] text-mute hover:border-cyan hover:text-ink"
            >
              {qp}
            </button>
          ))}
        </div>
      )}

      {/* Composer Form */}
      <form onSubmit={onSubmitChat} className="flex items-end gap-2 border-t border-line bg-panel p-2.5">
        <textarea
          rows={2}
          value={inputMsg}
          onChange={(e) => setInputMsg(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t('copilot.placeholder')}
          className="min-h-[42px] flex-1 resize-none rounded border border-line bg-surface px-2.5 py-2 text-xs text-ink focus:border-cyan focus:outline-none"
        />
        <button
          type="submit"
          disabled={!inputMsg.trim() || chatMut.isPending}
          className="inline-flex min-h-[42px] shrink-0 items-center gap-1.5 rounded bg-cyan px-3.5 text-xs font-semibold text-base hover:bg-cyan/90 disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" aria-hidden="true" />
          <span>{t('copilot.send')}</span>
        </button>
      </form>
    </div>
  );
}
