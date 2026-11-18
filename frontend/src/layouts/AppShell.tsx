import { Outlet } from 'react-router-dom';
import { AiCopilotDrawer } from '@/features/copilot/AiCopilotDrawer';
import { AppSidebar } from './AppSidebar';
import { GlobalHeader } from './GlobalHeader';
import { MobileNavigation } from './MobileNavigation';

export function AppShell() {
  return (
    <div className="flex h-dvh w-full max-w-full overflow-hidden bg-bg text-ink">
      <AppSidebar />
      <div className="flex min-w-0 w-full flex-1 flex-col overflow-x-hidden">
        <GlobalHeader />
        <main className="min-h-0 w-full flex-1 overflow-y-auto overflow-x-hidden p-2.5 pb-24 sm:p-4 sm:pb-24 lg:p-5 lg:pb-5">
          <Outlet />
        </main>
        <MobileNavigation />
      </div>
      <AiCopilotDrawer />
    </div>
  );
}
