import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  type CandlestickData,
  type Time,
  type UTCTimestamp,
  type IChartApi,
  createChart,
} from "lightweight-charts";
import { useTerminalUiStore } from "../state/useTerminalUiStore";
import { terminalTheme } from "../styles/terminalTheme.css";

import {
  chartCanvas,
  chartCrosshairBar,
  chartCrosshairItem,
  chartCrosshairLabel,
  chartCrosshairMoveDown,
  chartCrosshairMoveUp,
  chartCrosshairValue,
  chartRoot,
  chartViewport,
} from "./TerminalChartSurface.css";

const chartSeed = [
  { open: 63220, high: 63640, low: 62890, close: 63480, volume: 18240 },
  { open: 63480, high: 63940, low: 63220, close: 63720, volume: 19680 },
  { open: 63720, high: 64210, low: 63540, close: 64080, volume: 20510 },
  { open: 64080, high: 64430, low: 63680, close: 63910, volume: 17320 },
  { open: 63910, high: 64540, low: 63740, close: 64360, volume: 21490 },
  { open: 64360, high: 64680, low: 64010, close: 64120, volume: 18940 },
  { open: 64120, high: 64840, low: 63860, close: 64610, volume: 22810 },
  { open: 64610, high: 65180, low: 64200, close: 64890, volume: 23640 },
  { open: 64890, high: 65520, low: 64640, close: 65210, volume: 24880 },
  { open: 65210, high: 65380, low: 64590, close: 64930, volume: 19420 },
  { open: 64930, high: 66040, low: 64780, close: 65880, volume: 26790 },
  { open: 65880, high: 66720, low: 65590, close: 66450, volume: 30110 },
  { open: 66450, high: 67740, low: 66280, close: 67420, volume: 34280 },
];

const timeframeToSeconds: Record<string, number> = {
  "1s": 1,
  "1m": 60,
  "3m": 180,
  "5m": 300,
  "15m": 900,
  "30m": 1800,
  "1h": 3600,
  "2h": 7200,
  "4h": 14400,
  "6h": 21600,
  "12h": 43200,
  "1D": 86400,
  "2D": 172800,
  "3D": 259200,
  "1W": 604800,
  "1M": 2592000,
};

type TerminalChartCandle = CandlestickData<UTCTimestamp>;
type TerminalChartDatum = TerminalChartCandle & {
  volume: number;
};

function buildChartData(timeframe: string): TerminalChartDatum[] {
  const spacingSeconds = timeframeToSeconds[timeframe] ?? 900;
  const start = Date.UTC(2026, 2, 26, 0, 0, 0) / 1000;

  return chartSeed.map((candle, index) => ({
    time: (start + spacingSeconds * index) as UTCTimestamp,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
    volume: candle.volume,
  }));
}

function isChartCandleData(value: unknown): value is TerminalChartCandle {
  if (!value || typeof value !== "object") {
    return false;
  }

  return ["open", "high", "low", "close"].every((key) => typeof (value as Record<string, unknown>)[key] === "number");
}

function formatChartValue(value: number) {
  const hasFraction = Math.abs(value % 1) > Number.EPSILON;

  return value.toLocaleString("ru-RU", {
    minimumFractionDigits: hasFraction ? 2 : 0,
    maximumFractionDigits: hasFraction ? 2 : 0,
  });
}

function formatChartVolume(value: number) {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }

  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }

  return value.toLocaleString("ru-RU");
}

export function TerminalChartSurface(props: {
  instrument: string;
  move: string;
  timeframe: string;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const theme = useTerminalUiStore((state) => state.theme);
  const chartData = useMemo(() => buildChartData(props.timeframe), [props.timeframe]);
  const [activeCandle, setActiveCandle] = useState<TerminalChartDatum | null>(() => chartData.at(-1) ?? null);

  useEffect(() => {
    setActiveCandle(chartData.at(-1) ?? null);
  }, [chartData]);

  useEffect(() => {
    if (!rootRef.current || !viewportRef.current || !hostRef.current) {
      return;
    }

    const root = rootRef.current;
    const viewport = viewportRef.current;
    const host = hostRef.current;
    const colors = terminalTheme[theme];
    const candleByTime = new Map(chartData.map((candle) => [candle.time, candle]));
    const isSecondsTimeframe = props.timeframe.endsWith("s");
    const isIntradayTimeframe = props.timeframe.endsWith("s") || props.timeframe.endsWith("m") || props.timeframe.endsWith("h");
    const initialBounds = viewport.getBoundingClientRect();
    const initialWidth = Math.max(Math.round(initialBounds.width), 120);
    const initialHeight = Math.max(Math.round(initialBounds.height), 120);
    const chart: IChartApi = createChart(host, {
      width: initialWidth,
      height: initialHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: colors.textSecondary,
      },
      grid: {
        vertLines: { color: colors.border },
        horzLines: { color: colors.border },
      },
      rightPriceScale: {
        visible: true,
        borderColor: colors.divider,
        minimumWidth: 52,
        scaleMargins: { top: 0.04, bottom: 0.04 },
      },
      timeScale: {
        visible: true,
        borderColor: colors.divider,
        timeVisible: isIntradayTimeframe,
        secondsVisible: isSecondsTimeframe,
        barSpacing: 24,
        minBarSpacing: 6,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: colors.accentSoft,
          width: 1,
          style: LineStyle.Solid,
          labelVisible: true,
        },
        horzLine: {
          color: colors.accentSoft,
          width: 1,
          style: LineStyle.Solid,
          labelVisible: true,
        },
      },
      handleScale: {
        mouseWheel: false,
        pinch: true,
        axisPressedMouseMove: {
          time: false,
          price: true,
        },
        axisDoubleClickReset: true,
      },
      handleScroll: {
        mouseWheel: false,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: colors.success,
      downColor: colors.error,
      borderVisible: false,
      wickUpColor: colors.success,
      wickDownColor: colors.error,
      priceLineVisible: true,
      lastValueVisible: true,
      priceLineWidth: 1,
      priceLineColor: colors.accent,
    });
    series.setData(chartData.map(({ volume: _volume, ...candle }) => candle));
    chart.timeScale().fitContent();
    chart.applyOptions({
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: colors.accentSoft,
          width: 1,
          style: LineStyle.Solid,
          labelVisible: true,
        },
        horzLine: {
          color: colors.accentSoft,
          width: 1,
          style: LineStyle.Solid,
          labelVisible: true,
        },
      },
    });

    const priceScale = chart.priceScale("right");
    const timeScale = chart.timeScale();
    const syncDebugRanges = () => {
      const priceRange = priceScale.getVisibleRange();
      const logicalRange = timeScale.getVisibleLogicalRange();

      if (priceRange) {
        root.dataset.priceRange = `${priceRange.from.toFixed(2)}:${priceRange.to.toFixed(2)}`;
      }

      if (logicalRange) {
        root.dataset.timeRange = `${logicalRange.from.toFixed(2)}:${logicalRange.to.toFixed(2)}`;
      }
    };

    const syncDebugRangesSoon = () => {
      requestAnimationFrame(() => {
        syncDebugRanges();
      });
    };

    syncDebugRanges();
    chart.subscribeCrosshairMove((param) => {
      if (!param.point || !param.time) {
        delete root.dataset.crosshairX;
        delete root.dataset.crosshairY;
        delete root.dataset.crosshairTime;
        setActiveCandle(chartData.at(-1) ?? null);
        return;
      }

      root.dataset.crosshairX = `${Math.round(param.point.x)}`;
      root.dataset.crosshairY = `${Math.round(param.point.y)}`;
      root.dataset.crosshairTime =
        typeof param.time === "number" ? `${param.time}` : JSON.stringify(param.time as Time);

      const seriesData = param.seriesData.get(series);
      if (isChartCandleData(seriesData)) {
        const fullCandle = candleByTime.get(seriesData.time as UTCTimestamp);
        if (!fullCandle) {
          return;
        }

        setActiveCandle((current) => {
          if (
            current?.time === fullCandle.time &&
            current.open === fullCandle.open &&
            current.high === fullCandle.high &&
            current.low === fullCandle.low &&
            current.close === fullCandle.close &&
            current.volume === fullCandle.volume
          ) {
            return current;
          }

          return fullCandle;
        });
      }
    });

    const handleWheelOnScale = (event: WheelEvent) => {
      const bounds = viewport.getBoundingClientRect();
      const scaleWidth = Math.max(priceScale.width(), 72);
      const timeScaleHeight = 36;
      const isOverPriceScale = event.clientX >= bounds.right - scaleWidth;
      const isOverTimeScale =
        event.clientY >= bounds.bottom - timeScaleHeight &&
        event.clientX < bounds.right - scaleWidth;

      if (isOverPriceScale) {
        const visibleRange = priceScale.getVisibleRange();
        if (!visibleRange) {
          return;
        }

        event.preventDefault();
        event.stopPropagation();
        priceScale.setAutoScale(false);

        const center = (visibleRange.from + visibleRange.to) / 2;
        const span = visibleRange.to - visibleRange.from;
        const zoomFactor = event.deltaY < 0 ? 0.88 : 1.12;
        const nextSpan = Math.max(span * zoomFactor, 120);

        priceScale.setVisibleRange({
          from: center - nextSpan / 2,
          to: center + nextSpan / 2,
        });
        syncDebugRangesSoon();
        return;
      }

      if (isOverTimeScale) {
        const visibleRange = timeScale.getVisibleLogicalRange();
        const currentPriceRange = priceScale.getVisibleRange();
        if (!visibleRange) {
          return;
        }

        event.preventDefault();
        event.stopPropagation();

        const center = (visibleRange.from + visibleRange.to) / 2;
        const span = visibleRange.to - visibleRange.from;
        const zoomFactor = event.deltaY < 0 ? 0.9 : 1.1;
        const nextSpan = Math.max(span * zoomFactor, 6);

        timeScale.setVisibleLogicalRange({
          from: center - nextSpan / 2,
          to: center + nextSpan / 2,
        });

        if (currentPriceRange) {
          priceScale.setAutoScale(false);
          priceScale.setVisibleRange(currentPriceRange);
        }

        syncDebugRangesSoon();
        return;
      }

      const visibleRange = timeScale.getVisibleLogicalRange();
      const currentPriceRange = priceScale.getVisibleRange();
      if (!visibleRange) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      const center = (visibleRange.from + visibleRange.to) / 2;
      const span = visibleRange.to - visibleRange.from;
      const zoomFactor = event.deltaY < 0 ? 0.9 : 1.1;
      const nextSpan = Math.max(span * zoomFactor, 6);

      timeScale.setVisibleLogicalRange({
        from: center - nextSpan / 2,
        to: center + nextSpan / 2,
      });

      if (currentPriceRange) {
        priceScale.setAutoScale(false);
        priceScale.setVisibleRange(currentPriceRange);
      }

      syncDebugRangesSoon();
    };

    viewport.addEventListener("wheel", handleWheelOnScale, {
      passive: false,
    });

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }

      const nextWidth = Math.max(Math.round(entry.contentRect.width), 120);
      const nextHeight = Math.max(Math.round(entry.contentRect.height), 120);

      chart.resize(nextWidth, nextHeight, true);
      chart.applyOptions({
        rightPriceScale: {
          visible: true,
          minimumWidth: 52,
        },
        timeScale: {
          visible: true,
          timeVisible: isIntradayTimeframe,
          secondsVisible: isSecondsTimeframe,
          minBarSpacing: 6,
        },
      });
      syncDebugRangesSoon();
    });

    resizeObserver.observe(viewport);

    return () => {
      resizeObserver.disconnect();
      viewport.removeEventListener("wheel", handleWheelOnScale);
      chart.remove();
    };
  }, [chartData, props.timeframe, theme]);

  const openValue = activeCandle?.open ?? 0;
  const highValue = activeCandle?.high ?? 0;
  const lowValue = activeCandle?.low ?? 0;
  const closeValue = activeCandle?.close ?? 0;
  const volumeValue = activeCandle?.volume ?? 0;
  const moveValue = closeValue - openValue;
  const movePercent = openValue === 0 ? 0 : (moveValue / openValue) * 100;
  const moveToneClass = moveValue >= 0 ? chartCrosshairMoveUp : chartCrosshairMoveDown;
  const formattedMove = `${moveValue >= 0 ? "+" : ""}${formatChartValue(moveValue)}`;
  const formattedMovePercent = `${movePercent >= 0 ? "+" : ""}${movePercent.toFixed(2)}%`;

  return (
    <div ref={rootRef} className={chartRoot}>
      <div className={chartCrosshairBar}>
        <div className={chartCrosshairItem}>
          <span className={chartCrosshairLabel}>ОТКР</span>
          <span className={chartCrosshairValue}>{formatChartValue(openValue)}</span>
        </div>
        <div className={chartCrosshairItem}>
          <span className={chartCrosshairLabel}>МАКС</span>
          <span className={chartCrosshairValue}>{formatChartValue(highValue)}</span>
        </div>
        <div className={chartCrosshairItem}>
          <span className={chartCrosshairLabel}>МИН</span>
          <span className={chartCrosshairValue}>{formatChartValue(lowValue)}</span>
        </div>
        <div className={chartCrosshairItem}>
          <span className={chartCrosshairLabel}>ЗАКР</span>
          <span className={chartCrosshairValue}>{formatChartValue(closeValue)}</span>
        </div>
        <div className={chartCrosshairItem}>
          <span className={chartCrosshairLabel}>ИЗМ</span>
          <span className={moveToneClass}>{formattedMove}</span>
        </div>
        <div className={chartCrosshairItem}>
          <span className={chartCrosshairLabel}>%</span>
          <span className={moveToneClass}>{formattedMovePercent}</span>
        </div>
        <div className={chartCrosshairItem}>
          <span className={chartCrosshairLabel}>ОБЪЁМ</span>
          <span className={chartCrosshairValue}>{formatChartVolume(volumeValue)}</span>
        </div>
      </div>
      <div ref={viewportRef} className={chartViewport}>
        <div ref={hostRef} className={chartCanvas} />
      </div>
    </div>
  );
}
