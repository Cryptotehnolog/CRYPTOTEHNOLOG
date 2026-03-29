import { useEffect, useMemo, useRef, useState } from "react";

import { useTerminalUiStore } from "../state/useTerminalUiStore";

import { createLightweightChartModel, mountLightweightChartEngine } from "./lightweightChartEngine";
import type { TerminalChartDatum } from "./terminalChartEngine.types";
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
  const chartModel = useMemo(
    () =>
      createLightweightChartModel({
        instrument: props.instrument,
        timeframe: props.timeframe,
      }),
    [props.instrument, props.timeframe],
  );
  const [activeCandle, setActiveCandle] = useState<TerminalChartDatum | null>(chartModel.initialCandle);

  useEffect(() => {
    setActiveCandle(chartModel.initialCandle);
  }, [chartModel]);

  useEffect(() => {
    if (!rootRef.current || !viewportRef.current || !hostRef.current) {
      return;
    }

    const host = {
      rootEl: rootRef.current,
      viewportEl: viewportRef.current,
      hostEl: hostRef.current,
    };
    const cleanup = mountLightweightChartEngine({
      host,
      model: chartModel,
      theme,
      onActiveCandleChange: setActiveCandle,
    });
    host.rootEl.dataset.chartEngine = "lightweight";

    return () => {
      cleanup();
    };
  }, [chartModel, theme]);

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
