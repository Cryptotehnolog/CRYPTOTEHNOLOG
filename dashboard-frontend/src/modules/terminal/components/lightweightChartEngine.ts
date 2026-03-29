import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type Time,
  type UTCTimestamp,
  createChart,
} from "lightweight-charts";

import { terminalTheme } from "../styles/terminalTheme.css";

import type {
  TerminalChartDatum,
  TerminalChartEngineInput,
  TerminalChartEngineModel,
  TerminalChartEngineMountParams,
  TerminalChartRuntimeApi,
} from "./terminalChartEngine.types";
import { buildTerminalChartData } from "./terminalChartData";

function isChartCandleData(value: unknown): value is TerminalChartDatum {
  if (!value || typeof value !== "object") {
    return false;
  }

  return ["open", "high", "low", "close"].every((key) => typeof (value as Record<string, unknown>)[key] === "number");
}

function parseResolutionToSeconds(resolution: string) {
  const match = resolution.match(/^(\d+)([a-zA-Z]+)$/);
  if (!match) {
    return 60;
  }

  const amount = Number.parseInt(match[1], 10);
  const unit = match[2];

  switch (unit) {
    case "s":
      return amount;
    case "m":
      return amount * 60;
    case "h":
      return amount * 60 * 60;
    case "D":
      return amount * 60 * 60 * 24;
    case "W":
      return amount * 60 * 60 * 24 * 7;
    case "M":
      return amount * 60 * 60 * 24 * 30;
    default:
      return 60;
  }
}

export function createLightweightChartModel(input: TerminalChartEngineInput): TerminalChartEngineModel {
  const candles = buildTerminalChartData(input.timeframe);

  return {
    instrument: input.instrument,
    timeframe: input.timeframe,
    resolution: input.timeframe,
    candles,
    initialCandle: candles.at(-1) ?? null,
  };
}

export function mountLightweightChartEngine(params: TerminalChartEngineMountParams) {
  const { host, model, theme, onActiveCandleChange, onRuntimeReady, onViewportChange } = params;
  const { rootEl, viewportEl, hostEl } = host;
  const colors = terminalTheme[theme];
  const candleByTime = new Map(model.candles.map((candle) => [candle.time, candle]));
  const baseTime = model.candles[0]?.time ?? (Math.floor(Date.now() / 1000) as UTCTimestamp);
  const timeStepSeconds =
    model.candles.length >= 2
      ? Math.max(1, Math.round(Number(model.candles[1].time) - Number(model.candles[0].time)))
      : parseResolutionToSeconds(model.resolution);
  const isSecondsTimeframe = model.resolution.endsWith("s");
  const isIntradayTimeframe =
    model.resolution.endsWith("s") || model.resolution.endsWith("m") || model.resolution.endsWith("h");
  const initialBounds = viewportEl.getBoundingClientRect();
  const initialWidth = Math.max(Math.round(initialBounds.width), 120);
  const initialHeight = Math.max(Math.round(initialBounds.height), 120);
  const chart: IChartApi = createChart(hostEl, {
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

  series.setData(model.candles.map(({ volume: _volume, ...candle }) => candle));
  chart.timeScale().fitContent();

  const priceScale = chart.priceScale("right");
  const timeScale = chart.timeScale();
  const syncDebugRanges = () => {
    const priceRange = priceScale.getVisibleRange();
    const logicalRange = timeScale.getVisibleLogicalRange();

    if (priceRange) {
      rootEl.dataset.priceRange = `${priceRange.from.toFixed(2)}:${priceRange.to.toFixed(2)}`;
    }

    if (logicalRange) {
      rootEl.dataset.timeRange = `${logicalRange.from.toFixed(2)}:${logicalRange.to.toFixed(2)}`;
    }
  };
  const syncDebugRangesSoon = () => {
    requestAnimationFrame(() => {
      syncDebugRanges();
    });
  };

  syncDebugRanges();
  onActiveCandleChange(model.initialCandle);

  const getVisibleLogicalRange = () =>
    timeScale.getVisibleLogicalRange() ?? {
      from: 0,
      to: Math.max(model.candles.length - 1, 1),
    };

  const logicalToTime = (logical: number) =>
    Math.round(Number(baseTime) + logical * timeStepSeconds) as UTCTimestamp;

  const timeToLogical = (time: UTCTimestamp) => (Number(time) - Number(baseTime)) / timeStepSeconds;

  const runtimeApi: TerminalChartRuntimeApi = {
    timeToX: (time) => {
      const logicalRange = getVisibleLogicalRange();
      const span = logicalRange.to - logicalRange.from;
      const width = Math.max(viewportEl.clientWidth, 1);

      if (!Number.isFinite(span) || span === 0) {
        return width / 2;
      }

      const logical = timeToLogical(time);
      return ((logical - logicalRange.from) / span) * width;
    },
    xToTime: (x) => {
      const logicalRange = getVisibleLogicalRange();
      const span = logicalRange.to - logicalRange.from;
      const width = Math.max(viewportEl.clientWidth, 1);

      if (!Number.isFinite(span) || span === 0) {
        return baseTime;
      }

      const logical = logicalRange.from + (x / width) * span;
      return logicalToTime(logical);
    },
    priceToY: (price) => series.priceToCoordinate(price),
    yToPrice: (y) => {
      const price = series.coordinateToPrice(y);

      return typeof price === "number" ? price : null;
    },
    panByPixels: (deltaX) => {
      const visibleRange = timeScale.getVisibleLogicalRange();
      const viewportWidth = Math.max(viewportEl.clientWidth, 1);
      if (!visibleRange || Math.abs(deltaX) < 0.1) {
        return;
      }

      const span = visibleRange.to - visibleRange.from;
      if (!Number.isFinite(span) || span <= 0) {
        return;
      }

      const logicalShift = (deltaX / viewportWidth) * span;
      timeScale.setVisibleLogicalRange({
        from: visibleRange.from + logicalShift,
        to: visibleRange.to + logicalShift,
      });
      syncDebugRangesSoon();
      onViewportChange?.();
    },
    getVisiblePriceRange: () => priceScale.getVisibleRange(),
  };

  onRuntimeReady?.(runtimeApi);

  chart.subscribeCrosshairMove((param) => {
    if (!param.point || !param.time) {
      delete rootEl.dataset.crosshairX;
      delete rootEl.dataset.crosshairY;
      delete rootEl.dataset.crosshairTime;
      onActiveCandleChange(model.initialCandle);
      onViewportChange?.();
      return;
    }

    rootEl.dataset.crosshairX = `${Math.round(param.point.x)}`;
    rootEl.dataset.crosshairY = `${Math.round(param.point.y)}`;
    rootEl.dataset.crosshairTime =
      typeof param.time === "number" ? `${param.time}` : JSON.stringify(param.time as Time);

    const seriesData = param.seriesData.get(series);
    if (!isChartCandleData(seriesData)) {
      return;
    }

    const fullCandle = candleByTime.get(seriesData.time as UTCTimestamp);
    if (fullCandle) {
      onActiveCandleChange(fullCandle);
    }
    onViewportChange?.();
  });

  timeScale.subscribeVisibleLogicalRangeChange(() => {
    onViewportChange?.();
  });

  const handleWheelOnScale = (event: WheelEvent) => {
    const bounds = viewportEl.getBoundingClientRect();
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
      onViewportChange?.();
      return;
    }

    const visibleRange = timeScale.getVisibleLogicalRange();
    const currentPriceRange = priceScale.getVisibleRange();
    if (!visibleRange) {
      return;
    }

    if (isOverTimeScale) {
      event.preventDefault();
      event.stopPropagation();
    } else {
      event.preventDefault();
      event.stopPropagation();
    }

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
    onViewportChange?.();
  };

  viewportEl.addEventListener("wheel", handleWheelOnScale, {
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
    onViewportChange?.();
  });

  resizeObserver.observe(viewportEl);

  return () => {
    onRuntimeReady?.(null);
    resizeObserver.disconnect();
    viewportEl.removeEventListener("wheel", handleWheelOnScale);
    chart.remove();
  };
}
