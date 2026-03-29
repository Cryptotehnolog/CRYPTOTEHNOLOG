import type { TerminalChartDatum } from "./terminalChartEngine.types";

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

export function buildTerminalChartData(timeframe: string): TerminalChartDatum[] {
  const spacingSeconds = timeframeToSeconds[timeframe] ?? 900;
  const start = Date.UTC(2026, 2, 26, 0, 0, 0) / 1000;

  return chartSeed.map((candle, index) => ({
    time: (start + spacingSeconds * index) as TerminalChartDatum["time"],
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
    volume: candle.volume,
  }));
}
