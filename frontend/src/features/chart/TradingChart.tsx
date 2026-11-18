import {
  ColorType,
  createChart,
  LineStyle,
  type CandlestickData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';
import { useT } from '@/i18n/useT';
import type { ComputedIndicatorOutput } from '@/services/api';
import type { Theme } from '@/stores/uiStore';
import type { Candle } from '@/types';
import { fmtPrice } from '@/utils/format';

export type DrawMode = 'none' | 'hline' | 'fib';

export type ChartDrawing =
  | { id: string; kind: 'hline'; price: number }
  | { id: string; kind: 'fib'; highPrice: number; lowPrice: number };

interface Props {
  candles: Candle[];
  theme: Theme;
  overlays?: ComputedIndicatorOutput[];
  oscillators?: ComputedIndicatorOutput[];
  drawMode?: DrawMode;
  drawings?: ChartDrawing[];
  pendingFibPrice?: number | null;
  onPendingFibChange?: (price: number | null) => void;
  onAddDrawing?: (drawing: ChartDrawing) => void;
}

const palette = {
  dark: { text: '#A5B3C5', grid: '#192536', border: '#253449', up: '#19C995', down: '#F05B70' },
  light: { text: '#57667A', grid: '#E4EBF4', border: '#D0DAE7', up: '#059669', down: '#CD283C' },
} as const;

const FIB_LEVELS: { ratio: number; label: string; color: string }[] = [
  { ratio: 0.0, label: '0.0%', color: '#94A3B8' },
  { ratio: 0.236, label: '23.6%', color: '#38BDF8' },
  { ratio: 0.382, label: '38.2%', color: '#19C995' },
  { ratio: 0.5, label: '50.0%', color: '#F59E0B' },
  { ratio: 0.618, label: '61.8%', color: '#F05B70' },
  { ratio: 1.0, label: '100.0%', color: '#94A3B8' },
];

interface Legend {
  open: number;
  high: number;
  low: number;
  close: number;
}

export function TradingChart({
  candles,
  theme,
  overlays = [],
  oscillators = [],
  drawMode = 'none',
  drawings = [],
  pendingFibPrice = null,
  onPendingFibChange,
  onAddDrawing,
}: Props) {
  const t = useT();
  const containerRef = useRef<HTMLDivElement>(null);
  const oscContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const oscChartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const overlaySeriesRef = useRef<ISeriesApi<'Line'>[]>([]);
  const oscSeriesRef = useRef<(ISeriesApi<'Line'> | ISeriesApi<'Histogram'>)[]>([]);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const syncingRangeRef = useRef(false);
  const [hover, setHover] = useState<Legend | null>(null);

  const drawInteractionRef = useRef({
    drawMode,
    pendingFibPrice,
    onPendingFibChange,
    onAddDrawing,
  });
  drawInteractionRef.current = {
    drawMode,
    pendingFibPrice,
    onPendingFibChange,
    onAddDrawing,
  };

  // Create main price chart once.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, { autoSize: true, crosshair: { mode: 1 } });
    const candleSeries = chart.addCandlestickSeries({ borderVisible: false });
    const volumeSeries = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '' });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    chart.subscribeCrosshairMove((param) => {
      const d = param.seriesData.get(candleSeries) as CandlestickData | undefined;
      setHover(d ? { open: d.open, high: d.high, low: d.low, close: d.close } : null);
    });

    chart.subscribeClick((param) => {
      const { drawMode: mode, pendingFibPrice: pending, onPendingFibChange: setPending, onAddDrawing: add } =
        drawInteractionRef.current;
      if (mode === 'none' || !param.point || !add) return;
      const price = candleSeries.coordinateToPrice(param.point.y);
      if (price === null || !Number.isFinite(price)) return;

      if (mode === 'hline') {
        add({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, kind: 'hline', price });
      } else if (mode === 'fib') {
        if (pending === null) {
          setPending?.(price);
        } else {
          add({
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            kind: 'fib',
            highPrice: Math.max(pending, price),
            lowPrice: Math.min(pending, price),
          });
          setPending?.(null);
        }
      }
    });

    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (syncingRangeRef.current || !range || !oscChartRef.current) return;
      syncingRangeRef.current = true;
      try {
        oscChartRef.current.timeScale().setVisibleLogicalRange(range);
      } catch {
        // ignore out-of-range during series switch
      } finally {
        syncingRangeRef.current = false;
      }
    });

    chartRef.current = chart;
    candleRef.current = candleSeries;
    volumeRef.current = volumeSeries;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      overlaySeriesRef.current = [];
      priceLinesRef.current = [];
    };
  }, []);

  // Create or destroy secondary oscillator pane when oscillators presence toggles.
  const hasOscillators = oscillators.length > 0;
  useEffect(() => {
    if (!hasOscillators) {
      if (oscChartRef.current) {
        oscChartRef.current.remove();
        oscChartRef.current = null;
        oscSeriesRef.current = [];
      }
      return;
    }

    const el = oscContainerRef.current;
    if (!el) return;
    const p = palette[theme];
    const oscChart = createChart(el, {
      autoSize: true,
      crosshair: { mode: 1 },
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: p.text },
      grid: { vertLines: { color: p.grid }, horzLines: { color: p.grid } },
      rightPriceScale: { borderColor: p.border },
      timeScale: { borderColor: p.border, timeVisible: true },
    });

    oscChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (syncingRangeRef.current || !range || !chartRef.current) return;
      syncingRangeRef.current = true;
      try {
        chartRef.current.timeScale().setVisibleLogicalRange(range);
      } catch {
        // ignore out-of-range
      } finally {
        syncingRangeRef.current = false;
      }
    });

    oscChartRef.current = oscChart;
    return () => {
      oscChart.remove();
      oscChartRef.current = null;
      oscSeriesRef.current = [];
    };
  }, [hasOscillators, theme]);

  // Theme colors.
  useEffect(() => {
    const p = palette[theme];
    chartRef.current?.applyOptions({
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: p.text },
      grid: { vertLines: { color: p.grid }, horzLines: { color: p.grid } },
      rightPriceScale: { borderColor: p.border },
      timeScale: { borderColor: p.border, timeVisible: true },
    });
    candleRef.current?.applyOptions({
      upColor: p.up,
      downColor: p.down,
      wickUpColor: p.up,
      wickDownColor: p.down,
    });
  }, [theme]);

  // Candles + Volume + Overlays.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const p = palette[theme];

    candleRef.current?.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    volumeRef.current?.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        value: c.volume,
        color: (c.close >= c.open ? p.up : p.down) + '66',
      })),
    );

    for (const s of overlaySeriesRef.current) {
      try {
        chart.removeSeries(s);
      } catch {
        // ignore already removed
      }
    }
    overlaySeriesRef.current = [];

    for (const out of overlays) {
      for (const meta of out.outputs_meta) {
        const pts = out.series[meta.key] ?? [];
        if (pts.length === 0) continue;
        const line = chart.addLineSeries({
          color: meta.color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        line.setData(pts.map((pt) => ({ time: pt.time as UTCTimestamp, value: pt.value })));
        overlaySeriesRef.current.push(line);
      }
    }

    chart.timeScale().fitContent();
  }, [candles, overlays, theme]);

  // Oscillator series.
  useEffect(() => {
    const oscChart = oscChartRef.current;
    if (!oscChart) return;
    const p = palette[theme];

    for (const s of oscSeriesRef.current) {
      try {
        oscChart.removeSeries(s);
      } catch {
        // ignore
      }
    }
    oscSeriesRef.current = [];

    for (const out of oscillators) {
      for (const meta of out.outputs_meta) {
        const pts = out.series[meta.key] ?? [];
        if (pts.length === 0) continue;

        if (meta.series_type === 'histogram') {
          const hist = oscChart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
          hist.setData(
            pts.map((pt) => ({
              time: pt.time as UTCTimestamp,
              value: pt.value,
              color: (pt.value >= 0 ? p.up : p.down) + '99',
            })),
          );
          oscSeriesRef.current.push(hist);
        } else {
          const line = oscChart.addLineSeries({
            color: meta.color,
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: true,
          });
          line.setData(pts.map((pt) => ({ time: pt.time as UTCTimestamp, value: pt.value })));
          if (out.indicator_id === 'rsi') {
            line.createPriceLine({
              price: Number(out.params.overbought ?? 70),
              color: '#F05B7066',
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: 'OB',
            });
            line.createPriceLine({
              price: Number(out.params.oversold ?? 30),
              color: '#19C99566',
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: 'OS',
            });
          }
          oscSeriesRef.current.push(line);
        }
      }
    }

    const mainRange = chartRef.current?.timeScale().getVisibleLogicalRange();
    if (mainRange) {
      try {
        oscChart.timeScale().setVisibleLogicalRange(mainRange);
      } catch {
        oscChart.timeScale().fitContent();
      }
    } else {
      oscChart.timeScale().fitContent();
    }
  }, [oscillators, theme]);

  // Drawings (horizontal lines & Fibonacci retracements).
  useEffect(() => {
    const cs = candleRef.current;
    if (!cs) return;
    for (const pl of priceLinesRef.current) {
      try {
        cs.removePriceLine(pl);
      } catch {
        // ignore
      }
    }
    priceLinesRef.current = [];

    if (pendingFibPrice !== null) {
      priceLinesRef.current.push(
        cs.createPriceLine({
          price: pendingFibPrice,
          color: '#F59E0B',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'Fib A',
        }),
      );
    }

    for (const d of drawings) {
      if (d.kind === 'hline') {
        priceLinesRef.current.push(
          cs.createPriceLine({
            price: d.price,
            color: '#38BDF8',
            lineWidth: 1,
            lineStyle: LineStyle.Solid,
            axisLabelVisible: true,
            title: 'HLine',
          }),
        );
      } else {
        const span = d.highPrice - d.lowPrice;
        for (const lvl of FIB_LEVELS) {
          const levelPrice = d.lowPrice + span * lvl.ratio;
          priceLinesRef.current.push(
            cs.createPriceLine({
              price: levelPrice,
              color: lvl.color,
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: `Fib ${lvl.label}`,
            }),
          );
        }
      }
    }
  }, [drawings, pendingFibPrice]);

  const last = candles[candles.length - 1];
  const shown = hover ?? (last ? { open: last.open, high: last.high, low: last.low, close: last.close } : null);

  return (
    <div className="flex h-full w-full flex-col">
      <div className={`relative min-h-0 flex-1 ${drawMode !== 'none' ? 'cursor-crosshair' : ''}`}>
        <div ref={containerRef} className="h-full w-full" />
        {shown && (
          <div
            className="pointer-events-none absolute start-2 top-2 z-10 flex flex-wrap gap-x-3 gap-y-1 rounded bg-panel/85 px-2 py-1 text-[11px]"
            dir="ltr"
          >
            <span className="text-mute">
              {t('chart.open')} <span className="num text-ink">{fmtPrice(shown.open)}</span>
            </span>
            <span className="text-mute">
              {t('chart.high')} <span className="num text-ink">{fmtPrice(shown.high)}</span>
            </span>
            <span className="text-mute">
              {t('chart.low')} <span className="num text-ink">{fmtPrice(shown.low)}</span>
            </span>
            <span className="text-mute">
              {t('chart.close')} <span className="num text-ink">{fmtPrice(shown.close)}</span>
            </span>
            {overlays.map((ov) =>
              ov.outputs_meta.map((m) => {
                const pts = ov.series[m.key] ?? [];
                const val = pts[pts.length - 1]?.value;
                return val !== undefined ? (
                  <span key={`${ov.instance_id}-${m.key}`} className="num" style={{ color: m.color }}>
                    {m.label}: {fmtPrice(val)}
                  </span>
                ) : null;
              }),
            )}
          </div>
        )}
      </div>

      {hasOscillators && (
        <div className="relative h-[165px] shrink-0 border-t border-line">
          <div ref={oscContainerRef} className="h-full w-full" />
          <div
            className="pointer-events-none absolute start-2 top-1 z-10 flex flex-wrap gap-x-3 rounded bg-panel/85 px-2 py-0.5 text-[11px]"
            dir="ltr"
          >
            {oscillators.map((osc) =>
              osc.outputs_meta.map((m) => {
                const pts = osc.series[m.key] ?? [];
                const val = pts[pts.length - 1]?.value;
                return (
                  <span key={`${osc.instance_id}-${m.key}`} className="num" style={{ color: m.color }}>
                    {osc.indicator_id.toUpperCase()} {m.label}: {val !== undefined ? val.toFixed(2) : '—'}
                  </span>
                );
              }),
            )}
          </div>
        </div>
      )}
    </div>
  );
}
