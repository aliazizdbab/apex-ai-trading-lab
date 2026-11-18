import {
  Activity,
  BookOpen,
  Bot,
  CandlestickChart,
  CheckCircle2,
  ClipboardList,
  Code2,
  Compass,
  Download,
  FlaskConical,
  Globe,
  Layers,
  LayoutDashboard,
  Library,
  Rewind,
  Settings,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
  Wallet,
  Workflow,
  Zap,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useT } from '@/i18n/useT';
import { useUiStore } from '@/stores/uiStore';
import { Logo } from '@/ui/Logo';
import { Panel } from '@/ui/Panel';

export function GuidePage() {
  const t = useT();
  const lang = useUiStore((s) => s.lang);
  const toggleCopilot = useUiStore((s) => s.toggleCopilot);
  const isAr = lang === 'ar';

  const quickSteps = isAr
    ? [
        {
          n: '1',
          title: 'راقب السوق الحي وحمّل الشموع الحقيقية',
          desc: 'تصفح أسعار MEXC المباشرة من نظرة عامة على السوق أو شاشة السوق الحي واضغط أي عملة لفتحها في محطة التداول.',
          to: '/live-market',
          cta: 'فتح السوق الحي',
        },
        {
          n: '2',
          title: 'تحدث مع مساعد الذكاء الاصطناعي (AI Copilot)',
          desc: 'أضف مفتاح Gemini أو OpenAI أو Claude أو استخدم المحرك المدمج، ثم اطلب من البوت إنشاء استراتيجية واختبارها معك.',
          action: 'copilot',
          cta: 'فتح الشات بوت',
        },
        {
          n: '3',
          title: 'اختبر بالباك-تيست وWalk-Forward والـ Pine',
          desc: 'تحقق من الأرباح ونسبة السحب (Drawdown) وSharpe Ratio عبر المحرك الحتمي ثم تأكد خارج العينة (70% / 30%).',
          to: '/backtesting',
          cta: 'مختبر الاختبار الخلفي',
        },
        {
          n: '4',
          title: 'تدرّب على التداول الورقي ($10,000 افتراضي)',
          desc: 'جرّب الصفقات في الحساب الورقي المعزول تماماً قبل تفويض أي استراتيجية للتداول الفعلي.',
          to: '/paper-trading',
          cta: 'التداول الورقي',
        },
        {
          n: '5',
          title: 'اضبط حدود المخاطر والتحديث التلقائي من GitHub',
          desc: 'فعّل قواعد المخاطرة ومفتاح الإيقاف الطارئ (Emergency Stop) وتأكد من أحدث نسخة للتطبيق عبر GitHub.',
          to: '/settings#updates',
          cta: 'التحديثات والإعدادات',
        },
      ]
    : [
        {
          n: '1',
          title: 'Track Live MEXC Markets & Charts',
          desc: 'Explore real-time MEXC Spot pairs in Market Overview or Live Market, then launch the interactive charting Terminal.',
          to: '/live-market',
          cta: 'Open Live Market',
        },
        {
          n: '2',
          title: 'Collaborate with Agentic AI Copilot',
          desc: 'Connect your Gemini, OpenAI, Claude, DeepSeek, or OpenRouter API key (or use the built-in Quant Copilot) with full tool calling.',
          action: 'copilot',
          cta: 'Launch AI Copilot',
        },
        {
          n: '3',
          title: 'Validate with Backtests, Walk-Forward & Pine',
          desc: 'Run deterministic Event-Driven backtests, 70/30 In-Sample/Out-of-Sample optimization, or sandboxed Pine Script v5/v6.',
          to: '/backtesting',
          cta: 'Open Backtesting',
        },
        {
          n: '4',
          title: 'Practice Risk-Free in Paper Trading ($10,000)',
          desc: 'Execute virtual Spot orders in strictly separated paper accounts before authorizing real exchange capital.',
          to: '/paper-trading',
          cta: 'Open Paper Trading',
        },
        {
          n: '5',
          title: 'Enforce Risk Gates & GitHub Auto-Updates',
          desc: 'Configure per-trade risk caps, Emergency Stop, encrypted keys, and one-click GitHub updates across all devices.',
          to: '/settings#updates',
          cta: 'Settings & Updates',
        },
      ];

  const moduleGroups = isAr
    ? [
        {
          group: '1. لوحة القيادة والأسواق الحية',
          items: [
            { icon: LayoutDashboard, name: 'مركز التحكم', path: '/', desc: 'ملخص الأداء والمحفظة الورقية أو الحقيقية والأسواق والأنشطة الأخيرة.' },
            { icon: Globe, name: 'نظرة عامة على السوق', path: '/market-overview', desc: 'الأعلى صعوداً وهبوطاً وحجم التداول وخريطة السوق اللحظية.' },
            { icon: Activity, name: 'السوق الحي', path: '/live-market', desc: 'جدول الأسعار الفورية مع العرض والطلب (Bid/Ask) والسبريد.' },
            { icon: CandlestickChart, name: 'محطة التداول والشارت', path: '/terminal', desc: 'شموع يابانية وHeikin Ashi، مؤشرات فنية، أدوات رسم، وسجل الصفقات.' },
          ],
        },
        {
          group: '2. مختبر الاستراتيجيات والـ Pine والذكاء الاصطناعي',
          items: [
            { icon: Sparkles, name: 'منشئ الاستراتيجيات بالذكاء', path: '/ai-strategy-builder', desc: 'توليد مسودات استراتيجيات متعددة المؤشرات من وصف نصي.' },
            { icon: Code2, name: 'استوديو Pine Script', path: '/pine-studio', desc: 'محلل AST ومفسر آمن لكود Pine v5/v6 وكشف إعادة الطلاء (بدون eval).' },
            { icon: Library, name: 'مكتبة المؤشرات', path: '/indicator-library', desc: '10 مؤشرات كمية مع حساب فوري وحفظ إعدادات مخصصة (Presets).' },
            { icon: Layers, name: 'مكتبة ومنسّق الاستراتيجيات', path: '/strategy-composer', desc: 'تركيب 6+ مؤشرات بأطر زمنية مختلفة مع حفظ نسخ غير قابلة للتعديل.' },
          ],
        },
        {
          group: '3. الاختبار التاريخي والتحسين والإعادة',
          items: [
            { icon: FlaskConical, name: 'الاختبار الخلفي (Backtest)', path: '/backtesting', desc: 'اختبار Event-Driven مع تكافؤ Vectorized وكسر تعادل محافظ لوقف الخسارة.' },
            { icon: SlidersHorizontal, name: 'التحسين (Walk-Forward)', path: '/optimization', desc: 'فحص 70% داخل العينة / 30% خارج العينة لكشف فرط التخصيص (Overfitting).' },
            { icon: Rewind, name: 'الإعادة التاريخية (Replay)', path: '/replay', desc: 'شريط إعادة شمعة بشمعة من الخادم بدون أي تسريب لمستقبل الأسعار.' },
            { icon: TrendingUp, name: 'تحليلات الأداء', path: '/performance', desc: 'مقارنة شاملة لجميع جولات الباك-تيست المحفوظة.' },
          ],
        },
        {
          group: '4. التنفيذ الورقي والحقيقي والمخاطر والتحديث',
          items: [
            { icon: ClipboardList, name: 'التداول الورقي المعزول', path: '/paper-trading', desc: 'محفظة افتراضية $10,000 مفصولة تماماً عن الجداول الحقيقية.' },
            { icon: Zap, name: 'التداول الفوري الحي (MEXC)', path: '/live-trading', desc: 'تفويض صريح لكل نسخة استراتيجية + أوامر بـ clientOrderId مانع للتكرار.' },
            { icon: ShieldAlert, name: 'إدارة المخاطر وزر الطوارئ', path: '/risk', desc: 'حدود الخسارة اليومية والتراجع + زر إيقاف طارئ يلغي كل التفويضات فوراً.' },
            { icon: Compass, name: 'استخبارات وبحث السوق الذكي', path: '/ai-research', desc: 'تحليل نظام السوق + شات بوت كامل الصلاحيات مع اقتراحات معتمدة.' },
            { icon: Wallet, name: 'المراكز والأوامر والمحفظة', path: '/portfolio', desc: 'توزيع الأصول والربح المحقق وغير المحقق لكل حساب على حدة.' },
            { icon: Settings, name: 'الإعدادات والتحديث التلقائي', path: '/settings#updates', desc: 'تبديل العربية/الإنجليزية والوضع الداكن وتشفير المفاتيح وتحديثات GitHub.' },
          ],
        },
      ]
    : [
        {
          group: '1. Overview & Real-Time Markets',
          items: [
            { icon: LayoutDashboard, name: 'Control Center', path: '/', desc: 'Account KPIs, market snapshots, active strategies, and latest activities.' },
            { icon: Globe, name: 'Market Overview', path: '/market-overview', desc: 'Top gainers, losers, volume leaders, and global spot breadth.' },
            { icon: Activity, name: 'Live Market Feed', path: '/live-market', desc: 'Live Bid, Ask, spread, and 24h metrics streamed from MEXC Spot.' },
            { icon: CandlestickChart, name: 'Trading Terminal', path: '/terminal', desc: 'Candlesticks & Heikin Ashi, chart indicators, horizontal & Fibonacci tools.' },
          ],
        },
        {
          group: '2. Strategy Lab, Pine Studio & AI',
          items: [
            { icon: Sparkles, name: 'AI Strategy Builder', path: '/ai-strategy-builder', desc: 'Synthesize multi-indicator Draft strategies from plain language prompts.' },
            { icon: Code2, name: 'Pine Script Studio (v5/v6)', path: '/pine-studio', desc: 'Sandboxed AST parser & causal interpreter (zero eval/exec) with repaint checks.' },
            { icon: Library, name: 'Indicator Library', path: '/indicator-library', desc: '10 quantitative indicators with live preview calculation and saved presets.' },
            { icon: Layers, name: 'Strategy Library & Composer', path: '/strategy-composer', desc: 'Build 6+ indicator rules with causal HTF alignment and immutable versions.' },
          ],
        },
        {
          group: '3. Backtesting, Walk-Forward & Replay',
          items: [
            { icon: FlaskConical, name: 'Backtesting Lab', path: '/backtesting', desc: 'Event-driven simulation with vectorized parity and conservative SL tie-breaking.' },
            { icon: SlidersHorizontal, name: 'Walk-Forward Optimization', path: '/optimization', desc: '70% In-Sample / 30% Out-of-Sample validation and overfitting guardrails.' },
            { icon: Rewind, name: 'Bar-by-Bar Replay', path: '/replay', desc: 'Zero-future-leakage historical replay controlled server-side.' },
            { icon: TrendingUp, name: 'Performance Analytics', path: '/performance', desc: 'Cross-run metrics comparison table (Sharpe, Sortino, Max DD, Profit Factor).' },
          ],
        },
        {
          group: '4. Execution, Risk Gates & Auto-Updates',
          items: [
            { icon: ClipboardList, name: 'Paper Trading Engine', path: '/paper-trading', desc: 'Strictly isolated $10,000 virtual Spot wallet with live price fills.' },
            { icon: Zap, name: 'Live Spot Execution', path: '/live-trading', desc: 'Explicit version authorization + idempotent clientOrderId order staging.' },
            { icon: ShieldAlert, name: 'Risk & Emergency Stop', path: '/risk', desc: 'Global drawdown/exposure limits & instant Emergency Stop authorization revocation.' },
            { icon: Compass, name: 'AI Research & Intelligence', path: '/ai-research', desc: 'Full-screen AI Quant Copilot chat + market regime radar + approval queue.' },
            { icon: Wallet, name: 'Positions, Orders & Portfolio', path: '/portfolio', desc: 'Separated asset allocation and unrealized/realized PnL tracking.' },
            { icon: Settings, name: 'Settings & GitHub Updater', path: '/settings#updates', desc: 'Arabic RTL / English, encrypted vault, 2FA, and GitHub auto-updates for all OSes.' },
          ],
        },
      ];

  const metricsGuide = isAr
    ? [
        { k: 'Sharpe / Sortino', d: 'يقيس جودة العائد مقابل التقلب. كلما كان أكبر من 1.5 دلّ على أداء أكثر استقراراً.' },
        { k: 'Max Drawdown', d: 'أقصى نسبة انخفاض من القمة إلى القاع. يُنصح ألا يتجاوز حد المخاطرة المحدد في ملف المخاطر.' },
        { k: 'Profit Factor', d: 'إجمالي الأرباح مقسوماً على إجمالي الخسائر. فوق 1.3 يشير إلى أفضلية إحصائية إيجابية.' },
        { k: 'Walk-Forward 70/30', d: 'يختبر الإعدادات على 70% من التاريخ ثم يتأكد منها على 30% لم تَرَها الاستراتيجية لتجنب حفظ الماضي.' },
        { k: 'Emergency Stop', d: 'زر طوارئ أحمر يوقف جميع الأوامر فوراً ويلغي كل تفويضات التداول الحي.' },
        { k: 'Paper vs Real', d: 'الحساب الورقي منفصل برمجياً وفي قاعدة البيانات ولا يمكن خلطه مع رصيد MEXC الحقيقي.' },
      ]
    : [
        { k: 'Sharpe / Sortino', d: 'Measures risk-adjusted return relative to volatility; values above 1.5 indicate strong consistency.' },
        { k: 'Max Drawdown', d: 'Worst peak-to-trough equity drop. Keep below your configured Risk Management threshold.' },
        { k: 'Profit Factor', d: 'Gross winning trades divided by gross losing trades. Above 1.3 signals healthy expectancy.' },
        { k: 'Walk-Forward 70/30', d: 'Optimizes on 70% In-Sample bars then validates on unseen 30% Out-of-Sample data to detect overfitting.' },
        { k: 'Emergency Stop', d: 'Global circuit breaker that blocks all order execution and revokes active live authorizations.' },
        { k: 'Paper vs Real Isolation', d: 'Virtual $10,000 paper balances live in isolated tables and never mix with real exchange holdings.' },
      ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4">
      {/* Hero Header */}
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 sm:p-5">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <div className="shrink-0 pt-0.5">
              <Logo showText={false} />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-ink sm:text-xl">{t('guide.title')}</h2>
              <p className="mt-1 text-xs leading-relaxed text-mute sm:text-sm">{t('guide.intro')}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={toggleCopilot}
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded bg-cyan px-3 text-xs font-semibold text-base hover:bg-cyan/90"
            >
              <Bot className="h-4 w-4" aria-hidden="true" />
              {t('copilot.button')}
            </button>
            <Link
              to="/settings#updates"
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs font-medium text-ink hover:border-cyan"
            >
              <Download className="h-4 w-4 text-cyan" aria-hidden="true" />
              {t('upd.checkBtn')}
            </Link>
          </div>
        </div>
      </Panel>

      {/* 5-Step Quickstart */}
      <Panel title={t('guide.quickstartTitle')}>
        <div className="grid grid-cols-1 gap-3 p-3 sm:p-4 md:grid-cols-2 xl:grid-cols-5">
          {quickSteps.map((st) => (
            <div key={st.n} className="flex flex-col justify-between gap-3 rounded-md border border-line bg-surface p-3 text-xs">
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan/15 font-semibold text-cyan">
                    {st.n}
                  </span>
                  <h3 className="font-semibold text-ink">{st.title}</h3>
                </div>
                <p className="mt-2 leading-relaxed text-mute">{st.desc}</p>
              </div>
              {st.action === 'copilot' ? (
                <button
                  type="button"
                  onClick={toggleCopilot}
                  className="inline-flex min-h-[32px] items-center justify-center gap-1 rounded border border-cyan/40 bg-cyan/10 px-2.5 text-xs font-medium text-cyan hover:bg-cyan/20"
                >
                  {st.cta}
                </button>
              ) : (
                <Link
                  to={st.to!}
                  className="inline-flex min-h-[32px] items-center justify-center gap-1 rounded border border-line bg-panel px-2.5 text-xs font-medium text-ink hover:border-cyan hover:text-cyan"
                >
                  {st.cta}
                </Link>
              )}
            </div>
          ))}
        </div>
      </Panel>

      {/* AI Copilot Capabilities */}
      <Panel title={t('guide.copilotTitle')}>
        <div className="grid grid-cols-1 gap-3 p-3 text-xs sm:p-4 lg:grid-cols-3">
          <div className="rounded border border-line bg-surface p-3">
            <div className="flex items-center gap-1.5 font-semibold text-cyan">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              <span>{isAr ? 'دعم جميع مزودات الذكاء الاصطناعي' : 'Multi-Provider API Support'}</span>
            </div>
            <p className="mt-1.5 leading-relaxed text-mute">
              {isAr
                ? 'اربط Google Gemini أو OpenAI أو Anthropic Claude أو DeepSeek أو OpenRouter أو نقطة Base URL مخصصة مع تشفير AES-256-GCM، أو اعمل مباشرة بالمحرك المدمج.'
                : 'Connect Gemini, OpenAI, Anthropic Claude, DeepSeek, OpenRouter, or custom OpenAI-compatible endpoints (encrypted AES-256-GCM) or run locally built-in.'}
            </p>
          </div>
          <div className="rounded border border-line bg-surface p-3">
            <div className="flex items-center gap-1.5 font-semibold text-cyan">
              <Workflow className="h-4 w-4" aria-hidden="true" />
              <span>{isAr ? 'صلاحية تنفيذ أدوات التطبيق الكاملة' : 'Full-App Deterministic Tool Calling'}</span>
            </div>
            <p className="mt-1.5 leading-relaxed text-mute">
              {isAr
                ? 'ينشئ الاستراتيجيات، يعدّل الإصدارات، يشغل الباك-تيست، ينفذ Walk-Forward، يفحص الإشارات الحية، وينفذ صفقات ورقية بدون أي تخمين.'
                : 'Creates strategies, saves immutable versions, runs Backtests & Walk-Forward 70/30, evaluates MEXC signals, updates risk limits, and trades Paper accounts.'}
            </p>
          </div>
          <div className="rounded border border-line bg-surface p-3">
            <div className="flex items-center gap-1.5 font-semibold text-cyan">
              <BookOpen className="h-4 w-4" aria-hidden="true" />
              <span>{isAr ? 'أمثلة لأوامر يمكنك كتابتها للشات' : 'Example Copilot Prompts'}</span>
            </div>
            <p className="mt-1.5 leading-relaxed text-mute">
              {isAr
                ? '«أنشئ استراتيجية زخم على SOL/USDT 15m وشغل باك تيست ثم حسّنها بـ Walk-Forward وطبق أفضل إعدادات».'
                : '“Create a SOL/USDT 15m momentum strategy, backtest it, run Walk-Forward optimization, and apply best SL/TP.”'}
            </p>
          </div>
        </div>
      </Panel>

      {/* All Modules Directory */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {moduleGroups.map((grp) => (
          <Panel key={grp.group} title={grp.group}>
            <ul className="divide-y divide-line">
              {grp.items.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.name} className="flex items-start justify-between gap-3 p-3 text-xs">
                    <div className="flex min-w-0 flex-1 items-start gap-2.5">
                      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-cyan" aria-hidden="true" />
                      <div className="min-w-0">
                        <div className="font-semibold text-ink">{item.name}</div>
                        <p className="mt-0.5 leading-relaxed text-mute">{item.desc}</p>
                      </div>
                    </div>
                    <Link
                      to={item.path}
                      className="shrink-0 rounded border border-line bg-surface px-2.5 py-1 text-[11px] font-medium text-cyan hover:border-cyan"
                    >
                      {t('copilot.openPage')}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </Panel>
        ))}
      </div>

      {/* Metrics & Safety Glossary */}
      <Panel title={t('guide.metricsTitle')}>
        <div className="grid grid-cols-1 gap-2.5 p-3 text-xs sm:grid-cols-2 sm:p-4 lg:grid-cols-3">
          {metricsGuide.map((mg) => (
            <div key={mg.k} className="rounded border border-line bg-surface p-3">
              <div className="font-semibold text-cyan">{mg.k}</div>
              <p className="mt-1 leading-relaxed text-mute">{mg.d}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
