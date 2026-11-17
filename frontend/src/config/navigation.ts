import {
  Activity,
  Bell,
  Bot,
  CandlestickChart,
  ClipboardList,
  Code2,
  Compass,
  FlaskConical,
  Globe,
  Layers,
  LayoutDashboard,
  Library,
  ListOrdered,
  Menu,
  Plug,
  Rewind,
  Settings,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  Star,
  TrendingUp,
  Wallet,
  Workflow,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import type { TKey } from '@/i18n/en';

export interface NavItem {
  id: string;
  path: string;
  labelKey: TKey;
  icon: LucideIcon;
  /** Phase of the approved roadmap (docs/PHASE0_ARCHITECTURE.md section 13.1) that builds the real module. */
  phase: number;
  /** true = a real page exists in this build (demo data where labelled). */
  built: boolean;
}

export interface NavGroup {
  id: string;
  labelKey: TKey;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'overview',
    labelKey: 'nav.group.overview',
    items: [
      { id: 'dashboard', path: '/', labelKey: 'nav.dashboard', icon: LayoutDashboard, phase: 1, built: true },
      { id: 'marketOverview', path: '/market-overview', labelKey: 'nav.marketOverview', icon: Globe, phase: 3, built: false },
    ],
  },
  {
    id: 'market',
    labelKey: 'nav.group.market',
    items: [
      { id: 'liveMarket', path: '/live-market', labelKey: 'nav.liveMarket', icon: Activity, phase: 3, built: false },
      { id: 'terminal', path: '/terminal', labelKey: 'nav.terminal', icon: CandlestickChart, phase: 4, built: true },
      { id: 'watchlist', path: '/watchlist', labelKey: 'nav.watchlist', icon: Star, phase: 3, built: false },
    ],
  },
  {
    id: 'strategyLab',
    labelKey: 'nav.group.strategyLab',
    items: [
      { id: 'aiStrategyBuilder', path: '/ai-strategy-builder', labelKey: 'nav.aiStrategyBuilder', icon: Sparkles, phase: 10, built: false },
      { id: 'pineStudio', path: '/pine-studio', labelKey: 'nav.pineStudio', icon: Code2, phase: 9, built: false },
      { id: 'indicatorLibrary', path: '/indicator-library', labelKey: 'nav.indicatorLibrary', icon: Library, phase: 5, built: false },
      { id: 'strategyLibrary', path: '/strategy-library', labelKey: 'nav.strategyLibrary', icon: Layers, phase: 6, built: false },
      { id: 'strategyComposer', path: '/strategy-composer', labelKey: 'nav.strategyComposer', icon: Workflow, phase: 6, built: false },
    ],
  },
  {
    id: 'testing',
    labelKey: 'nav.group.testing',
    items: [
      { id: 'backtesting', path: '/backtesting', labelKey: 'nav.backtesting', icon: FlaskConical, phase: 7, built: false },
      { id: 'replay', path: '/replay', labelKey: 'nav.replay', icon: Rewind, phase: 8, built: false },
      { id: 'paperTrading', path: '/paper-trading', labelKey: 'nav.paperTrading', icon: ClipboardList, phase: 11, built: false },
      { id: 'performance', path: '/performance', labelKey: 'nav.performance', icon: TrendingUp, phase: 7, built: false },
    ],
  },
  {
    id: 'execution',
    labelKey: 'nav.group.execution',
    items: [
      { id: 'liveTrading', path: '/live-trading', labelKey: 'nav.liveTrading', icon: Zap, phase: 13, built: false },
      { id: 'positions', path: '/positions', labelKey: 'nav.positions', icon: Layers, phase: 13, built: false },
      { id: 'orders', path: '/orders', labelKey: 'nav.orders', icon: ListOrdered, phase: 13, built: false },
      { id: 'portfolio', path: '/portfolio', labelKey: 'nav.portfolio', icon: Wallet, phase: 13, built: false },
    ],
  },
  {
    id: 'intelligence',
    labelKey: 'nav.group.intelligence',
    items: [
      { id: 'aiResearch', path: '/ai-research', labelKey: 'nav.aiResearch', icon: Bot, phase: 14, built: false },
      { id: 'marketIntelligence', path: '/market-intelligence', labelKey: 'nav.marketIntelligence', icon: Compass, phase: 14, built: false },
      { id: 'optimization', path: '/optimization', labelKey: 'nav.optimization', icon: SlidersHorizontal, phase: 14, built: false },
    ],
  },
  {
    id: 'system',
    labelKey: 'nav.group.system',
    items: [
      { id: 'notifications', path: '/notifications', labelKey: 'nav.notifications', icon: Bell, phase: 2, built: false },
      { id: 'exchanges', path: '/exchanges', labelKey: 'nav.exchanges', icon: Plug, phase: 3, built: false },
      { id: 'risk', path: '/risk', labelKey: 'nav.risk', icon: ShieldAlert, phase: 12, built: false },
      { id: 'settings', path: '/settings', labelKey: 'nav.settings', icon: Settings, phase: 2, built: true },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export interface MobileTab {
  id: string;
  path: string;
  labelKey: TKey;
  icon: LucideIcon;
}

/** Four direct destinations; the fifth tab ("More") opens the full navigation drawer. */
export const MOBILE_TABS: MobileTab[] = [
  { id: 'home', path: '/', labelKey: 'mobile.home', icon: LayoutDashboard },
  { id: 'markets', path: '/live-market', labelKey: 'mobile.markets', icon: Activity },
  { id: 'strategies', path: '/strategy-library', labelKey: 'mobile.strategies', icon: Layers },
  { id: 'backtesting', path: '/backtesting', labelKey: 'mobile.backtesting', icon: FlaskConical },
];

export const MORE_ICON = Menu;
