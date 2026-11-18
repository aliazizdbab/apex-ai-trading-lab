import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, ExternalLink, KeyRound, LogOut, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { useT } from '@/i18n/useT';
import {
  activateTotp,
  ApiError,
  applyGithubUpdate,
  checkGithubUpdates,
  createCredential,
  deleteCredential,
  enrollTotp,
  fetchAuditLogs,
  fetchAuthStatus,
  fetchServerSettings,
  fetchUpdateStatus,
  listCredentials,
  loginOwner,
  logoutOwner,
  setupOwner,
  updateServerSettings,
  type TotpEnrollResponse,
} from '@/services/api';
import { useUiStore, type Lang, type Theme } from '@/stores/uiStore';
import { Panel } from '@/ui/Panel';
import { Segmented } from '@/ui/Segmented';

export function SettingsPage() {
  const t = useT();
  const queryClient = useQueryClient();

  const theme = useUiStore((s) => s.theme);
  const lang = useUiStore((s) => s.lang);
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const setTheme = useUiStore((s) => s.setTheme);
  const setLang = useUiStore((s) => s.setLang);
  const setCollapsed = useUiStore((s) => s.setSidebarCollapsed);

  const { data: authStatus, isLoading: authLoading } = useQuery({
    queryKey: ['auth-status'],
    queryFn: fetchAuthStatus,
    retry: false,
  });

  const authenticated = Boolean(authStatus?.authenticated);
  const setupCompleted = Boolean(authStatus?.setup_completed);

  const { data: serverSettings } = useQuery({
    queryKey: ['server-settings'],
    queryFn: fetchServerSettings,
    enabled: authenticated,
    retry: false,
  });

  useEffect(() => {
    if (!serverSettings) return;
    setTheme(serverSettings.theme);
    setLang(serverSettings.lang);
    setCollapsed(serverSettings.sidebarCollapsed);
  }, [serverSettings, setTheme, setLang, setCollapsed]);

  const syncSettingsMut = useMutation({
    mutationFn: updateServerSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['server-settings'] }),
  });

  const handleThemeChange = (next: Theme) => {
    setTheme(next);
    if (authenticated) syncSettingsMut.mutate({ theme: next });
  };

  const handleLangChange = (next: Lang) => {
    setLang(next);
    if (authenticated) syncSettingsMut.mutate({ lang: next });
  };

  const handleCollapsedChange = (next: boolean) => {
    setCollapsed(next);
    if (authenticated) syncSettingsMut.mutate({ sidebarCollapsed: next });
  };

  // Auth form state
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('Owner');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [totpData, setTotpData] = useState<TotpEnrollResponse | null>(null);
  const [totpActivateInput, setTotpActivateInput] = useState('');
  const [totpMessage, setTotpMessage] = useState<string | null>(null);

  const refreshAuthAndSecurity = () => {
    queryClient.invalidateQueries({ queryKey: ['auth-status'] });
    queryClient.invalidateQueries({ queryKey: ['system-health'] });
    queryClient.invalidateQueries({ queryKey: ['credentials'] });
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
    queryClient.invalidateQueries({ queryKey: ['audit-logs'] });
  };

  const setupMut = useMutation({
    mutationFn: setupOwner,
    onSuccess: (res) => {
      setAuthError(null);
      setPassword('');
      setTotpData({
        totp_secret: res.totp_secret,
        totp_uri: res.totp_uri,
        totp_enabled: res.user.totp_enabled,
      });
      refreshAuthAndSecurity();
    },
    onError: (err) => {
      setAuthError(err instanceof ApiError ? err.detail : 'Setup failed');
    },
  });

  const loginMut = useMutation({
    mutationFn: loginOwner,
    onSuccess: () => {
      setAuthError(null);
      setPassword('');
      setTotpCode('');
      refreshAuthAndSecurity();
    },
    onError: (err) => {
      setAuthError(err instanceof ApiError ? err.detail : 'Login failed');
    },
  });

  const logoutMut = useMutation({
    mutationFn: logoutOwner,
    onSuccess: () => {
      setTotpData(null);
      setTotpMessage(null);
      refreshAuthAndSecurity();
    },
  });

  const enrollTotpMut = useMutation({
    mutationFn: enrollTotp,
    onSuccess: (res) => {
      setTotpData(res);
      setAuthError(null);
    },
  });

  const activateTotpMut = useMutation({
    mutationFn: activateTotp,
    onSuccess: () => {
      setTotpActivateInput('');
      setAuthError(null);
      setTotpMessage(t('auth.totpEnabled'));
      refreshAuthAndSecurity();
    },
    onError: (err) => {
      setAuthError(err instanceof ApiError ? err.detail : 'Invalid TOTP code');
    },
  });

  // Credentials Vault state
  const [credType, setCredType] = useState<'exchange' | 'ai'>('exchange');
  const [providerName, setProviderName] = useState('mexc');
  const [credLabel, setCredLabel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [credError, setCredError] = useState<string | null>(null);

  const { data: credsData } = useQuery({
    queryKey: ['credentials'],
    queryFn: listCredentials,
    enabled: authenticated,
    retry: false,
  });

  const createCredMut = useMutation({
    mutationFn: createCredential,
    onSuccess: () => {
      setCredError(null);
      setCredLabel('');
      setApiKey('');
      setApiSecret('');
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['audit-logs'] });
    },
    onError: (err) => {
      setCredError(err instanceof ApiError ? err.detail : 'Failed to store credential');
    },
  });

  const deleteCredMut = useMutation({
    mutationFn: deleteCredential,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['audit-logs'] });
    },
  });

  const { data: auditData } = useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => fetchAuditLogs(25),
    enabled: authenticated,
    retry: false,
  });

  const { data: updateStatus } = useQuery({
    queryKey: ['github-update-status'],
    queryFn: fetchUpdateStatus,
    retry: false,
  });

  const { data: updateCheck, isFetching: checkingUpdates, refetch: refetchUpdateCheck } = useQuery({
    queryKey: ['github-update-check'],
    queryFn: checkGithubUpdates,
    retry: false,
  });

  const applyUpdateMut = useMutation({
    mutationFn: applyGithubUpdate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-update-status'] });
      queryClient.invalidateQueries({ queryKey: ['github-update-check'] });
    },
  });

  const row = 'flex flex-wrap items-center justify-between gap-3 border-b border-line px-3 py-3 last:border-b-0';
  const inputCls =
    'min-h-[38px] w-full rounded border border-line bg-surface px-3 text-sm text-ink placeholder:text-mute focus:border-cyan focus:outline-none';

  const onSetupSubmit = (e: FormEvent) => {
    e.preventDefault();
    setupMut.mutate({ email, display_name: displayName, password });
  };

  const onLoginSubmit = (e: FormEvent) => {
    e.preventDefault();
    loginMut.mutate({ email, password, totp_code: totpCode.trim() || undefined });
  };

  const onCredSubmit = (e: FormEvent) => {
    e.preventDefault();
    createCredMut.mutate({
      provider_type: credType,
      provider_name: providerName,
      label: credLabel,
      api_key: apiKey,
      api_secret: apiSecret.trim() || undefined,
    });
  };

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <h2 className="text-lg font-semibold">{t('settings.title')}</h2>

      {/* GitHub Auto-Updater & Multi-Platform Downloads */}
      <div id="updates">
        <Panel
          title={t('upd.title')}
          actions={
            <a
              href={updateCheck?.repo_url ?? updateStatus?.repo_url ?? 'https://github.com/aliazizdbab/apex-ai-trading-lab'}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-cyan hover:underline"
            >
              <span>{updateStatus?.repo ?? 'aliazizdbab/apex-ai-trading-lab'}</span>
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </a>
          }
        >
          <div className="space-y-3 p-3 text-xs">
            <p className="text-mute">{t('upd.subtitle')}</p>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <div className="rounded border border-line bg-surface p-2.5">
                <div className="text-mute">{t('upd.currentVer')}</div>
                <div className="num mt-1 font-semibold text-ink">
                  v{updateCheck?.current_version ?? updateStatus?.current_version ?? '1.0.0'}{' '}
                  <span className="font-mono text-[11px] text-mute">
                    ({updateCheck?.local_commit ?? updateStatus?.local_commit ?? 'local'})
                  </span>
                </div>
              </div>
              <div className="rounded border border-line bg-surface p-2.5">
                <div className="text-mute">{t('upd.latestVer')}</div>
                <div className="num mt-1 font-semibold text-cyan">
                  {updateCheck?.latest_tag ?? updateStatus?.release_tag ?? 'v1.0.0'}{' '}
                  <span className="font-mono text-[11px] text-mute">
                    ({updateCheck?.remote_commit ?? 'main'})
                  </span>
                </div>
              </div>
              <div className="rounded border border-line bg-surface p-2.5">
                <div className="text-mute">GitHub Status</div>
                <div className={`mt-1 font-semibold ${updateCheck?.update_available ? 'text-warn' : 'text-bull'}`}>
                  {updateCheck?.update_available ? t('upd.available') : t('upd.upToDate')}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => refetchUpdateCheck()}
                disabled={checkingUpdates}
                className="inline-flex min-h-[34px] items-center gap-1.5 rounded bg-cyan px-3 text-xs font-semibold text-base hover:bg-cyan/90 disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${checkingUpdates ? 'animate-spin' : ''}`} aria-hidden="true" />
                {t('upd.checkBtn')}
              </button>

              <button
                type="button"
                onClick={() => applyUpdateMut.mutate()}
                disabled={applyUpdateMut.isPending}
                className="inline-flex min-h-[34px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs font-medium text-ink hover:border-cyan"
              >
                <Download className="h-3.5 w-3.5 text-cyan" aria-hidden="true" />
                {applyUpdateMut.isPending ? t('common.loading') : t('upd.applyBtn')}
              </button>
            </div>

            {applyUpdateMut.data && (
              <div
                className={`rounded border px-3 py-2 text-xs ${
                  applyUpdateMut.data.ok
                    ? 'border-bull/40 bg-bull/10 text-bull'
                    : 'border-bear/40 bg-bear/10 text-bear'
                }`}
              >
                {applyUpdateMut.data.before_commit} → {applyUpdateMut.data.after_commit}: {applyUpdateMut.data.output}
              </div>
            )}

            <div>
              <div className="mb-1.5 font-medium text-mute">{t('upd.downloads')}</div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {(
                  [
                    { key: 'windows', label: 'Windows (.zip)' },
                    { key: 'macos', label: 'macOS (.tar.gz)' },
                    { key: 'android', label: 'Android (.apk)' },
                    { key: 'web', label: 'Web Bundle (.zip)' },
                  ] as const
                ).map((item) => {
                  const href =
                    updateCheck?.platforms?.[item.key] ??
                    updateStatus?.platforms?.[item.key] ??
                    'https://github.com/aliazizdbab/apex-ai-trading-lab/releases/latest';
                  return (
                    <a
                      key={item.key}
                      href={href}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center justify-between gap-2 rounded border border-line bg-surface px-2.5 py-2 text-xs font-medium text-ink hover:border-cyan"
                    >
                      <span>{item.label}</span>
                      <Download className="h-3.5 w-3.5 text-cyan" aria-hidden="true" />
                    </a>
                  );
                })}
              </div>
            </div>
          </div>
        </Panel>
      </div>

      {/* Appearance & Server Sync */}
      <Panel
        title={t('settings.appearance')}
        actions={
          authenticated ? (
            <span className="text-xs text-bull">
              {syncSettingsMut.isPending ? t('common.loading') : t('settings.syncedServer')}
            </span>
          ) : null
        }
      >
        <div className={row}>
          <span className="text-sm">{t('settings.theme')}</span>
          <Segmented<Theme>
            ariaLabel={t('settings.theme')}
            value={theme}
            onChange={handleThemeChange}
            options={[
              { value: 'dark', label: t('settings.themeDark') },
              { value: 'light', label: t('settings.themeLight') },
            ]}
          />
        </div>
        <div className={row}>
          <span className="text-sm">{t('settings.language')}</span>
          <Segmented<Lang>
            ariaLabel={t('settings.language')}
            value={lang}
            onChange={handleLangChange}
            options={[
              { value: 'en', label: 'English' },
              { value: 'ar', label: 'العربية' },
            ]}
          />
        </div>
        <div className={row}>
          <label htmlFor="compact-sidebar" className="text-sm">
            {t('settings.sidebarCompact')}
          </label>
          <input
            id="compact-sidebar"
            type="checkbox"
            checked={collapsed}
            onChange={(e) => handleCollapsedChange(e.target.checked)}
            className="h-5 w-5 accent-cyan"
          />
        </div>
      </Panel>
      <p className="text-xs text-mute">{t('settings.persistNote')}</p>

      {/* Owner Auth & TOTP 2FA */}
      <Panel title={t('auth.panelTitle')}>
        {authLoading ? (
          <p className="p-4 text-sm text-mute">{t('common.loading')}</p>
        ) : !setupCompleted ? (
          <form onSubmit={onSetupSubmit} className="space-y-3 p-4">
            <div>
              <h3 className="text-sm font-semibold">{t('auth.setupTitle')}</h3>
              <p className="text-xs text-mute">{t('auth.setupHint')}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('auth.email')}</span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputCls}
                />
              </label>
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('auth.displayName')}</span>
                <input
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className={inputCls}
                />
              </label>
            </div>
            <label className="block space-y-1 text-xs">
              <span className="text-mute">{t('auth.password')}</span>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputCls}
              />
            </label>
            {authError && <p className="text-xs text-bear">{authError}</p>}
            <button
              type="submit"
              disabled={setupMut.isPending}
              className="min-h-[38px] rounded bg-cyan px-4 text-sm font-medium text-bg hover:opacity-90 disabled:opacity-50"
            >
              {t('auth.setupSubmit')}
            </button>
          </form>
        ) : !authenticated ? (
          <form onSubmit={onLoginSubmit} className="space-y-3 p-4">
            <h3 className="text-sm font-semibold">{t('auth.loginTitle')}</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('auth.email')}</span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputCls}
                />
              </label>
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('auth.password')}</span>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputCls}
                />
              </label>
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('auth.totpCode')}</span>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                  placeholder="000000"
                  className={`${inputCls} tabular-nums`}
                />
              </label>
            </div>
            {authError === 'TOTP_REQUIRED' ? (
              <p className="text-xs text-amber">{t('auth.totpRequiredHint')}</p>
            ) : (
              authError && <p className="text-xs text-bear">{authError}</p>
            )}
            <button
              type="submit"
              disabled={loginMut.isPending}
              className="min-h-[38px] rounded bg-cyan px-4 text-sm font-medium text-bg hover:opacity-90 disabled:opacity-50"
            >
              {t('auth.loginSubmit')}
            </button>
          </form>
        ) : (
          <div className="space-y-4 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-0.5">
                <p className="text-xs text-mute">{t('auth.signedInAs')}</p>
                <p className="text-sm font-semibold">
                  {authStatus?.user?.display_name} ({authStatus?.user?.email})
                </p>
                <p className="text-xs">
                  <span className="text-mute">{t('auth.totpStatus')}: </span>
                  <span className={authStatus?.user?.totp_enabled ? 'font-medium text-bull' : 'font-medium text-amber'}>
                    {authStatus?.user?.totp_enabled ? t('auth.totpEnabled') : t('auth.totpDisabled')}
                  </span>
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {!authStatus?.user?.totp_enabled && (
                  <button
                    type="button"
                    onClick={() => enrollTotpMut.mutate()}
                    className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs font-medium hover:border-cyan"
                  >
                    <ShieldCheck className="h-4 w-4 text-cyan" aria-hidden="true" />
                    {t('auth.totpEnroll')}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => logoutMut.mutate()}
                  className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs font-medium hover:border-bear hover:text-bear"
                >
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                  {t('auth.logout')}
                </button>
              </div>
            </div>

            {totpData && !authStatus?.user?.totp_enabled && (
              <div className="space-y-3 rounded border border-line bg-surface p-3">
                <div className="grid gap-2 text-xs">
                  <div>
                    <span className="text-mute">{t('auth.totpSecretLabel')}: </span>
                    <code dir="ltr" className="rounded bg-bg px-1.5 py-0.5 font-mono text-cyan">
                      {totpData.totp_secret}
                    </code>
                  </div>
                  <div className="break-all">
                    <span className="text-mute">{t('auth.totpUriLabel')}: </span>
                    <code dir="ltr" className="font-mono text-[11px] text-mute">
                      {totpData.totp_uri}
                    </code>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={totpActivateInput}
                    onChange={(e) => setTotpActivateInput(e.target.value)}
                    placeholder={t('auth.totpCode')}
                    className="min-h-[36px] w-44 rounded border border-line bg-bg px-3 text-sm tabular-nums focus:border-cyan focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => activateTotpMut.mutate(totpActivateInput)}
                    disabled={activateTotpMut.isPending || totpActivateInput.trim().length < 6}
                    className="min-h-[36px] rounded bg-cyan px-3 text-xs font-medium text-bg hover:opacity-90 disabled:opacity-50"
                  >
                    {t('auth.totpActivate')}
                  </button>
                </div>
                {authError && <p className="text-xs text-bear">{authError}</p>}
              </div>
            )}
            {totpMessage && <p className="text-xs text-bull">{totpMessage}</p>}
          </div>
        )}
      </Panel>

      {/* Encrypted Credentials Vault */}
      {authenticated && (
        <Panel title={t('vault.title')}>
          <div className="space-y-4 p-4">
            <p className="text-xs text-mute">{t('vault.subtitle')}</p>
            <form onSubmit={onCredSubmit} className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('vault.providerType')}</span>
                <select
                  value={credType}
                  onChange={(e) => {
                    const next = e.target.value as 'exchange' | 'ai';
                    setCredType(next);
                    setProviderName(next === 'exchange' ? 'mexc' : 'gemini');
                  }}
                  className={inputCls}
                >
                  <option value="exchange">{t('vault.typeExchange')}</option>
                  <option value="ai">{t('vault.typeAi')}</option>
                </select>
              </label>
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('vault.providerName')}</span>
                <input
                  type="text"
                  required
                  value={providerName}
                  onChange={(e) => setProviderName(e.target.value)}
                  className={inputCls}
                />
              </label>
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('vault.label')}</span>
                <input
                  type="text"
                  required
                  value={credLabel}
                  onChange={(e) => setCredLabel(e.target.value)}
                  placeholder="Main Account"
                  className={inputCls}
                />
              </label>
              <label className="space-y-1 text-xs">
                <span className="text-mute">{t('vault.apiKey')}</span>
                <input
                  type="password"
                  required
                  minLength={4}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className={inputCls}
                />
              </label>
              <label className="space-y-1 text-xs sm:col-span-2">
                <span className="text-mute">{t('vault.apiSecret')}</span>
                <input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  className={inputCls}
                />
              </label>
              {credError && <p className="text-xs text-bear sm:col-span-2">{credError}</p>}
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={createCredMut.isPending}
                  className="inline-flex min-h-[38px] items-center gap-1.5 rounded bg-cyan px-4 text-sm font-medium text-bg hover:opacity-90 disabled:opacity-50"
                >
                  <KeyRound className="h-4 w-4" aria-hidden="true" />
                  {t('vault.storeButton')}
                </button>
              </div>
            </form>

            <div className="border-t border-line pt-3">
              {(credsData?.items ?? []).length === 0 ? (
                <p className="text-xs text-mute">{t('vault.empty')}</p>
              ) : (
                <ul className="divide-y divide-line">
                  {credsData?.items.map((cred) => (
                    <li key={cred.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                      <div className="min-w-0 space-y-0.5">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <span>{cred.label}</span>
                          <span className="rounded border border-line bg-surface px-1.5 py-0.5 text-[11px] uppercase text-mute">
                            {cred.provider_name}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-mute">
                          <code dir="ltr" className="font-mono text-ink">
                            {cred.api_key_masked}
                          </code>
                          <span>•</span>
                          <span>{cred.has_secret ? t('vault.hasSecret') : t('vault.noSecret')}</span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => deleteCredMut.mutate(cred.id)}
                        aria-label={t('common.delete')}
                        className="inline-flex min-h-[32px] items-center gap-1 rounded border border-line bg-surface px-2.5 text-xs text-bear hover:border-bear"
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                        {t('common.delete')}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Panel>
      )}

      {/* Audit Log Hash Chain */}
      {authenticated && (
        <Panel
          title={t('audit.title')}
          actions={
            auditData ? (
              <div className="flex items-center gap-2 text-xs">
                <span className={auditData.chain_valid ? 'font-medium text-bull' : 'font-medium text-bear'}>
                  {auditData.chain_valid ? t('audit.chainValid') : t('audit.chainBroken')}
                </span>
                <span className="text-mute">
                  ({t('audit.entriesCount', { count: auditData.total_entries })})
                </span>
              </div>
            ) : null
          }
        >
          {!auditData || auditData.items.length === 0 ? (
            <p className="p-4 text-xs text-mute">{t('audit.empty')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-start text-xs">
                <thead className="border-b border-line bg-surface text-mute">
                  <tr>
                    <th className="px-3 py-2 text-start font-medium">{t('audit.action')}</th>
                    <th className="px-3 py-2 text-start font-medium">{t('audit.actor')}</th>
                    <th className="px-3 py-2 text-start font-medium">{t('audit.entity')}</th>
                    <th className="px-3 py-2 text-start font-medium">{t('audit.hash')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {auditData.items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-3 py-2 font-mono">{item.action}</td>
                      <td className="px-3 py-2 text-mute">{item.actor}</td>
                      <td className="px-3 py-2 font-mono text-mute">{item.entity}</td>
                      <td className="px-3 py-2 font-mono text-mute" dir="ltr">
                        {item.entry_hash.slice(0, 14)}…
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
