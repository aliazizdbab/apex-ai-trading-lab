import type { ReactElement } from 'react';
import { Route, Routes } from 'react-router-dom';
import { ALL_NAV_ITEMS } from '@/config/navigation';
import { AppShell } from '@/layouts/AppShell';
import { DashboardPage } from '@/pages/DashboardPage';
import { ModulePage } from '@/pages/ModulePage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { TerminalPage } from '@/pages/TerminalPage';

/** Modules with a real page in this build. Every other module renders the honest "not built" placeholder. */
const BUILT_PAGES: Record<string, ReactElement> = {
  dashboard: <DashboardPage />,
  terminal: <TerminalPage />,
  settings: <SettingsPage />,
};

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {ALL_NAV_ITEMS.map((item) => {
          const element = BUILT_PAGES[item.id] ?? <ModulePage item={item} />;
          return item.path === '/' ? (
            <Route key={item.id} index element={element} />
          ) : (
            <Route key={item.id} path={item.path.slice(1)} element={element} />
          );
        })}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
