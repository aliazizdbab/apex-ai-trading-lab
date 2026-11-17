import { Outlet } from 'react-router-dom';
import { AppSidebar } from './AppSidebar';
import { GlobalHeader } from './GlobalHeader';
import { MobileNavigation } from './MobileNavigation';

export function AppShell() {
  return (
    <div className="flex h-dvh overflow-hidden bg-bg text-ink">
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <GlobalHeader />
        <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3 pb-24 sm:p-4 sm:pb-24 lg:p-5 lg:pb-5">
          <Outlet />
        </main>
        <MobileNavigation />
      </div>
    </div>
  );
}
