import type { CandlestickData, UTCTimestamp } from "lightweight-charts";

import type { TerminalTheme } from "../state/useTerminalUiStore";

export type TerminalChartDatum = CandlestickData<UTCTimestamp> & {
  volume: number;
};

export type TerminalChartEngineInput = {
  instrument: string;
  timeframe: string;
};

export type TerminalChartEngineModel = {
  instrument: string;
  timeframe: string;
  resolution: string;
  candles: TerminalChartDatum[];
  initialCandle: TerminalChartDatum | null;
};

export type TerminalChartHostElements = {
  rootEl: HTMLDivElement;
  viewportEl: HTMLDivElement;
  hostEl: HTMLDivElement;
};

export type TerminalChartEngineMountParams = {
  host: TerminalChartHostElements;
  model: TerminalChartEngineModel;
  theme: TerminalTheme;
  onActiveCandleChange: (candle: TerminalChartDatum | null) => void;
};
