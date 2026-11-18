import type { ReactElement } from 'react';
import { Route, Routes } from 'react-router-dom';
import { ALL_NAV_ITEMS } from '@/config/navigation';
import { AppShell } from '@/layouts/AppShell';
import { AiResearchPage } from '@/pages/AiResearchPage';
import { AiStrategyBuilderPage } from '@/pages/AiStrategyBuilderPage';
import { BacktestingPage } from '@/pages/BacktestingPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { ExchangesPage } from '@/pages/ExchangesPage';
import { IndicatorLibraryPage } from '@/pages/IndicatorLibraryPage';
import { LiveMarketPage } from '@/pages/LiveMarketPage';
import { LiveTradingPage } from '@/pages/LiveTradingPage';
import { MarketIntelligencePage } from '@/pages/MarketIntelligencePage';
import { MarketOverviewPage } from '@/pages/MarketOverviewPage';
import { ModulePage } from '@/pages/ModulePage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { NotificationsPage } from '@/pages/NotificationsPage';
import { OptimizationPage } from '@/pages/OptimizationPage';
import { OrdersPage } from '@/pages/OrdersPage';
import { PaperTradingPage } from '@/pages/PaperTradingPage';
import { PerformancePage } from '@/pages/PerformancePage';
import { PineStudioPage } from '@/pages/PineStudioPage';
import { PortfolioPage } from '@/pages/PortfolioPage';
import { PositionsPage } from '@/pages/PositionsPage';
import { ReplayPage } from '@/pages/ReplayPage';
import { RiskManagementPage } from '@/pages/RiskManagementPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { StrategyComposerPage } from '@/pages/StrategyComposerPage';
import { StrategyLibraryPage } from '@/pages/StrategyLibraryPage';
import { TerminalPage } from '@/pages/TerminalPage';
import { WatchlistPage } from '@/pages/WatchlistPage';

/** All 25 navigation modules registered in this build. */
const BUILT_PAGES: Record<string, ReactElement> = {
  dashboard: <DashboardPage />,
  marketOverview: <MarketOverviewPage />,
  liveMarket: <LiveMarketPage />,
  terminal: <TerminalPage />,
  watchlist: <WatchlistPage />,
  aiStrategyBuilder: <AiStrategyBuilderPage />,
  pineStudio: <PineStudioPage />,
  indicatorLibrary: <IndicatorLibraryPage />,
  strategyLibrary: <StrategyLibraryPage />,
  strategyComposer: <StrategyComposerPage />,
  backtesting: <BacktestingPage />,
  replay: <ReplayPage />,
  paperTrading: <PaperTradingPage />,
  performance: <PerformancePage />,
  liveTrading: <LiveTradingPage />,
  positions: <PositionsPage />,
  orders: <OrdersPage />,
  portfolio: <PortfolioPage />,
  aiResearch: <AiResearchPage />,
  marketIntelligence: <MarketIntelligencePage />,
  optimization: <OptimizationPage />,
  notifications: <NotificationsPage />,
  exchanges: <ExchangesPage />,
  risk: <RiskManagementPage />,
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
