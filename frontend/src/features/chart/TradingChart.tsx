import {
  ColorType,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';
import { useT } from '@/i18n/useT';
import type { Theme } from '@/stores/uiStore';
import type { Candle } from '@/types';
import { fmtPrice } from '@/utils/format';

interface Props {
  candles: Candle[];
  theme: Theme;
}

const palette = {
  dark: { text: '#A5B3C5', grid: '#192536', border: '#253449', up: '#19C995', down: '#F05B70' },
  light: { text: '#57667A', grid: '#E4EBF4', border: '#D0DAE7', up: '#059669', down: '#CD283C' },
} as const;

interface Legend {
  open: number;
  high: number;
  low: number;
  close: number;
}

export function TradingChart({ candles, theme }: Props) {
  const t = useT();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const [hover, setHover] = useState<Legend | null>(null);

  // Create the chart once.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, { autoSize: true, crosshair: { mode: 1 } });
    const candleSeries = chart.addCandlestickSeries({ borderVisible: false });
    const volumeSeries = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '' });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    chart.subscribeCrosshairMove((param) => {
      const d = param.seriesData.get(candleSeries) as CandlestickData | undefined;
      setHover(d ? { open: d.open, high: d.high, low: d.low, close: d.close } : null);
    });

    chartRef.current = chart;
    candleRef.current = candleSeries;
    volumeRef.current = volumeSeries;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
    };
  }, []);

  // Theme colours.
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

  // Data.
  useEffect(() => {
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
    chartRef.current?.timeScale().fitContent();
  }, [candles, theme]);

  const last = candles[candles.length - 1];
  const shown = hover ?? (last ? { open: last.open, high: last.high, low: last.low, close: last.close } : null);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {shown && (
        <div className="pointer-events-none absolute start-2 top-2 z-10 flex flex-wrap gap-x-3 rounded bg-panel/80 px-2 py-1 text-[11px]" dir="ltr">
          <span className="text-mute">{t('chart.open')} <span className="num text-ink">{fmtPrice(shown.open)}</span></span>
          <span className="text-mute">{t('chart.high')} <span className="num text-ink">{fmtPrice(shown.high)}</span></span>
          <span className="text-mute">{t('chart.low')} <span className="num text-ink">{fmtPrice(shown.low)}</span></span>
          <span className="text-mute">{t('chart.close')} <span className="num text-ink">{fmtPrice(shown.close)}</span></span>
        </div>
      )}
    </div>
  );
}
