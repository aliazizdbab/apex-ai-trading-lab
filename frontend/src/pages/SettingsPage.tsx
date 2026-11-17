import { useT } from '@/i18n/useT';
import { useUiStore, type Lang, type Theme } from '@/stores/uiStore';
import { Panel } from '@/ui/Panel';
import { Segmented } from '@/ui/Segmented';

export function SettingsPage() {
  const t = useT();
  const theme = useUiStore((s) => s.theme);
  const lang = useUiStore((s) => s.lang);
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const setTheme = useUiStore((s) => s.setTheme);
  const setLang = useUiStore((s) => s.setLang);
  const setCollapsed = useUiStore((s) => s.setSidebarCollapsed);

  const row = 'flex flex-wrap items-center justify-between gap-3 border-b border-line px-3 py-3 last:border-b-0';

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <h2 className="text-lg font-semibold">{t('settings.title')}</h2>
      <Panel title={t('settings.appearance')}>
        <div className={row}>
          <span className="text-sm">{t('settings.theme')}</span>
          <Segmented<Theme>
            ariaLabel={t('settings.theme')}
            value={theme}
            onChange={setTheme}
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
            onChange={setLang}
            options={[
              { value: 'en', label: 'English' },
              { value: 'ar', label: 'العربية' },
            ]}
          />
        </div>
        <div className={row}>
          <label htmlFor="compact-sidebar" className="text-sm">{t('settings.sidebarCompact')}</label>
          <input
            id="compact-sidebar"
            type="checkbox"
            checked={collapsed}
            onChange={(e) => setCollapsed(e.target.checked)}
            className="h-5 w-5 accent-cyan"
          />
        </div>
      </Panel>
      <p className="text-xs text-mute">{t('settings.persistNote')}</p>
    </div>
  );
}
