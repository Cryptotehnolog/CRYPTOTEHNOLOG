import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";
import type { UTCTimestamp } from "lightweight-charts";

import { useTerminalUiStore } from "../state/useTerminalUiStore";
import { terminalTheme } from "../styles/terminalTheme.css";

import { createLightweightChartModel, mountLightweightChartEngine } from "./lightweightChartEngine";
import type { TerminalChartDatum, TerminalChartRuntimeApi } from "./terminalChartEngine.types";
import {
  chartCanvas,
  chartCrosshairBar,
  chartCrosshairItem,
  chartCrosshairLabel,
  chartCrosshairMoveDown,
  chartCrosshairMoveUp,
  chartCrosshairValue,
  chartDrawingCapture,
  chartDrawingDeleteButton,
  chartDrawingEditor,
  chartDrawingField,
  chartDrawingFieldInput,
  chartDrawingFieldLabel,
  chartDrawingEditorGroup,
  chartDrawingHandle,
  chartDrawingLayer,
  chartDrawingSvg,
  chartDrawingSwatch,
  chartDrawingSwatchActive,
  chartDrawingToolButton,
  chartDrawingToolButtonActive,
  chartDrawingToolbar,
  chartDrawingWidthButton,
  chartDrawingWidthButtonActive,
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

type DrawingTool = "horizontal" | "vertical" | "trend" | "rectangle";
type DrawingStyle = {
  color: string;
  width: number;
};
type DrawingPoint = {
  time: UTCTimestamp;
  price: number;
};
type HorizontalDrawing = DrawingStyle & {
  id: string;
  kind: "horizontal";
  price: number;
};
type VerticalDrawing = DrawingStyle & {
  id: string;
  kind: "vertical";
  time: UTCTimestamp;
};
type TrendDrawing = DrawingStyle & {
  id: string;
  kind: "trend";
  start: DrawingPoint;
  end: DrawingPoint;
};
type RectangleDrawing = DrawingStyle & {
  id: string;
  kind: "rectangle";
  start: DrawingPoint;
  end: DrawingPoint;
};
type TerminalDrawing = HorizontalDrawing | VerticalDrawing | TrendDrawing | RectangleDrawing;
type RectangleHandle = "nw" | "ne" | "sw" | "se";
type DragState =
  | {
      kind: "horizontal";
      id: string;
      originClientY: number;
      originPrice: number;
    }
  | {
      kind: "vertical";
      id: string;
      originClientX: number;
      originTime: UTCTimestamp;
    }
  | {
      kind: "trend";
      id: string;
      originClientX: number;
      originClientY: number;
      start: DrawingPoint;
      end: DrawingPoint;
    }
  | {
      kind: "trend-start";
      id: string;
    }
  | {
      kind: "trend-end";
      id: string;
    }
  | {
      kind: "rectangle-move";
      id: string;
      originClientX: number;
      originClientY: number;
      start: DrawingPoint;
      end: DrawingPoint;
    }
  | {
      kind: "rectangle-resize";
      id: string;
      handle: RectangleHandle;
      originClientX: number;
      originClientY: number;
      start: DrawingPoint;
      end: DrawingPoint;
    };
type ScreenPoint = {
  x: number;
  y: number;
};
type DrawingBounds = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};
type EditorPosition = {
  left: number;
  top: number;
};

const drawingPalette = ["rgba(114, 212, 255, 0.92)", "rgba(255, 189, 89, 0.94)", "rgba(118, 255, 162, 0.92)", "rgba(255, 125, 125, 0.92)"];
const drawingWidths = [1, 2, 3];
const defaultDrawingStyle: DrawingStyle = {
  color: drawingPalette[0],
  width: 2,
};
const invisibleHitWidth = 14;
const rectangleHandleSize = 10;
const editorEstimate = {
  width: 320,
  height: 84,
};
const edgePanThreshold = 36;
const edgePanStep = 18;
const drawingsStoragePrefix = "cryptotechnolog.terminal.drawings.v2";
const toolLabels: Record<DrawingTool, string> = {
  horizontal: "Горизонтальный уровень",
  vertical: "Вертикальный уровень",
  trend: "Трендовая линия",
  rectangle: "Прямоугольник",
};

function clamp(value: number, min: number, max: number) {
  if (max < min) {
    return min;
  }

  return Math.min(Math.max(value, min), max);
}

function createDrawingId() {
  return `drawing-${Math.random().toString(36).slice(2, 10)}`;
}

function getDrawingsStorageKey(exchange: string, instrument: string) {
  return `${drawingsStoragePrefix}:${exchange}:${instrument}`;
}

function isDrawingPoint(value: unknown): value is DrawingPoint {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return typeof candidate.time === "number" && typeof candidate.price === "number";
}

function isTerminalDrawing(value: unknown): value is TerminalDrawing {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.kind !== "string" ||
    typeof candidate.color !== "string" ||
    typeof candidate.width !== "number"
  ) {
    return false;
  }

  switch (candidate.kind) {
    case "horizontal":
      return typeof candidate.price === "number";
    case "vertical":
      return typeof candidate.time === "number";
    case "trend":
    case "rectangle":
      return isDrawingPoint(candidate.start) && isDrawingPoint(candidate.end);
    default:
      return false;
  }
}

function loadPersistedDrawings(storageKey: string) {
  if (typeof window === "undefined") {
    return [] as TerminalDrawing[];
  }

  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return [] as TerminalDrawing[];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [] as TerminalDrawing[];
    }

    return parsed.filter(isTerminalDrawing);
  } catch {
    return [] as TerminalDrawing[];
  }
}

function toTranslucentFill(color: string) {
  const rgbaMatch = color.match(/^rgba?\(([^)]+)\)$/i);
  if (!rgbaMatch) {
    return "rgba(114, 212, 255, 0.10)";
  }

  const parts = rgbaMatch[1].split(",").map((part) => part.trim());
  if (parts.length < 3) {
    return "rgba(114, 212, 255, 0.10)";
  }

  const [red, green, blue] = parts;
  return `rgba(${red}, ${green}, ${blue}, 0.12)`;
}

function normalizeRectangle(start: DrawingPoint, end: DrawingPoint) {
  const leftTime = start.time <= end.time ? start.time : end.time;
  const rightTime = start.time <= end.time ? end.time : start.time;
  const topPrice = Math.max(start.price, end.price);
  const bottomPrice = Math.min(start.price, end.price);

  return {
    start: { time: leftTime, price: topPrice },
    end: { time: rightTime, price: bottomPrice },
  };
}

function getScreenPoint(point: DrawingPoint, runtime: TerminalChartRuntimeApi): ScreenPoint | null {
  const x = runtime.timeToX(point.time);
  const y = runtime.priceToY(point.price);

  if (x === null || y === null) {
    return null;
  }

  return { x, y };
}

function getPointFromClient(clientX: number, clientY: number, viewportEl: HTMLDivElement, runtime: TerminalChartRuntimeApi): DrawingPoint | null {
  const bounds = viewportEl.getBoundingClientRect();
  const x = clamp(clientX - bounds.left, 0, bounds.width);
  const y = clamp(clientY - bounds.top, 0, bounds.height);
  const time = runtime.xToTime(x);
  const price = runtime.yToPrice(y);

  if (time === null || price === null) {
    return null;
  }

  return { time, price };
}

function shiftPoint(point: DrawingPoint, dx: number, dy: number, viewportEl: HTMLDivElement, runtime: TerminalChartRuntimeApi) {
  const origin = getScreenPoint(point, runtime);
  if (!origin) {
    return point;
  }

  const bounds = viewportEl.getBoundingClientRect();
  const nextTime = runtime.xToTime(clamp(origin.x + dx, 0, bounds.width));
  const nextPrice = runtime.yToPrice(clamp(origin.y + dy, 0, bounds.height));

  if (nextTime === null || nextPrice === null) {
    return point;
  }

  return {
    time: nextTime,
    price: nextPrice,
  };
}

function getDrawingPointFromClient(
  clientX: number,
  clientY: number,
  viewportEl: HTMLDivElement,
  runtime: TerminalChartRuntimeApi,
) {
  const rawPoint = getPointFromClient(clientX, clientY, viewportEl, runtime);
  return rawPoint;
}

function getEdgePanDelta(clientX: number, viewportBounds: DOMRect) {
  const localX = clientX - viewportBounds.left;
  if (localX >= viewportBounds.width - edgePanThreshold) {
    const progress = (localX - (viewportBounds.width - edgePanThreshold)) / edgePanThreshold;
    return edgePanStep * clamp(progress, 0.2, 1);
  }

  if (localX <= edgePanThreshold) {
    const progress = (edgePanThreshold - localX) / edgePanThreshold;
    return -edgePanStep * clamp(progress, 0.2, 1);
  }

  return 0;
}

function getDrawingBounds(drawing: TerminalDrawing, runtime: TerminalChartRuntimeApi, viewportEl: HTMLDivElement): DrawingBounds | null {
  if (drawing.kind === "horizontal") {
    const y = runtime.priceToY(drawing.price);
    if (y === null) {
      return null;
    }
    return { left: 0, top: y, right: viewportEl.clientWidth, bottom: y };
  }

  if (drawing.kind === "vertical") {
    const x = runtime.timeToX(drawing.time);
    if (x === null) {
      return null;
    }
    return { left: x, top: 0, right: x, bottom: viewportEl.clientHeight };
  }

  const start = getScreenPoint(drawing.start, runtime);
  const end = getScreenPoint(drawing.end, runtime);

  if (!start || !end) {
    return null;
  }

  return {
    left: Math.min(start.x, end.x),
    top: Math.min(start.y, end.y),
    right: Math.max(start.x, end.x),
    bottom: Math.max(start.y, end.y),
  };
}

function getRectangleCorners(rectangle: RectangleDrawing, runtime: TerminalChartRuntimeApi) {
  const topLeft = getScreenPoint(rectangle.start, runtime);
  const bottomRight = getScreenPoint(rectangle.end, runtime);

  if (!topLeft || !bottomRight) {
    return null;
  }

  const topRight = getScreenPoint({ time: rectangle.end.time, price: rectangle.start.price }, runtime);
  const bottomLeft = getScreenPoint({ time: rectangle.start.time, price: rectangle.end.price }, runtime);

  if (!topRight || !bottomLeft) {
    return null;
  }

  return {
    nw: topLeft,
    ne: topRight,
    sw: bottomLeft,
    se: bottomRight,
  };
}

function createToolIcon(tool: DrawingTool): ReactNode {
  switch (tool) {
    case "horizontal":
      return (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path d="M3 9H15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      );
    case "vertical":
      return (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path d="M9 3V15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      );
    case "trend":
      return (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path d="M4 13L13.5 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          <circle cx="4" cy="13" r="1.35" fill="currentColor" />
          <circle cx="13.5" cy="4.5" r="1.35" fill="currentColor" />
        </svg>
      );
    case "rectangle":
      return (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <rect x="4.1" y="4.1" width="9.8" height="9.8" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
        </svg>
      );
  }
}

function DrawingToolbar(props: {
  activeTool: DrawingTool | null;
  onSelect: (tool: DrawingTool) => void;
  onClearAll: () => void;
  hasDrawings: boolean;
}) {
  const tools: DrawingTool[] = ["horizontal", "vertical", "trend", "rectangle"];

  return (
    <div className={chartDrawingToolbar}>
      {tools.map((tool) => (
        <button
          key={tool}
          type="button"
          className={`${chartDrawingToolButton} ${props.activeTool === tool ? chartDrawingToolButtonActive : ""}`}
          aria-label={toolLabels[tool]}
          aria-pressed={props.activeTool === tool}
          title={toolLabels[tool]}
          onClick={() => props.onSelect(tool)}
        >
          {createToolIcon(tool)}
        </button>
      ))}
      <button
        type="button"
        className={chartDrawingToolButton}
        aria-label="Очистить все объекты"
        title="Очистить все объекты"
        disabled={!props.hasDrawings}
        onClick={props.onClearAll}
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path d="M5 5.5L13 13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M13 5.5L5 13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}

export function TerminalChartSurface(props: {
  instrument: string;
  exchange: string;
  move: string;
  timeframe: string;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<HTMLDivElement | null>(null);
  const theme = useTerminalUiStore((state) => state.theme);
  const colors = terminalTheme[theme];
  const storageKey = useMemo(
    () => getDrawingsStorageKey(props.exchange, props.instrument),
    [props.exchange, props.instrument],
  );
  const chartModel = useMemo(
    () =>
      createLightweightChartModel({
        instrument: props.instrument,
        timeframe: props.timeframe,
      }),
    [props.instrument, props.timeframe],
  );
  const [activeCandle, setActiveCandle] = useState<TerminalChartDatum | null>(chartModel.initialCandle);
  const [runtimeApi, setRuntimeApi] = useState<TerminalChartRuntimeApi | null>(null);
  const [_viewportVersion, setViewportVersion] = useState(0);
  const [selectedTool, setSelectedTool] = useState<DrawingTool | null>(null);
  const [drawings, setDrawings] = useState<TerminalDrawing[]>(() => loadPersistedDrawings(storageKey));
  const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null);
  const [draftPoint, setDraftPoint] = useState<DrawingPoint | null>(null);
  const [previewPoint, setPreviewPoint] = useState<DrawingPoint | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [editorPosition, setEditorPosition] = useState<EditorPosition | null>(null);
  const [horizontalPriceInput, setHorizontalPriceInput] = useState("");
  const [rectangleTopInput, setRectangleTopInput] = useState("");
  const [rectangleBottomInput, setRectangleBottomInput] = useState("");
  const selectedDrawing = drawings.find((drawing) => drawing.id === selectedDrawingId) ?? null;

  useEffect(() => {
    setActiveCandle(chartModel.initialCandle);
  }, [chartModel]);

  useEffect(() => {
    setDrawings(loadPersistedDrawings(storageKey));
    setSelectedDrawingId(null);
    setDraftPoint(null);
    setPreviewPoint(null);
    setSelectedTool(null);
    setDragState(null);
  }, [storageKey]);

  useEffect(() => {
    if (!selectedDrawing) {
      setHorizontalPriceInput("");
      setRectangleTopInput("");
      setRectangleBottomInput("");
      return;
    }

    if (selectedDrawing.kind === "horizontal") {
      setHorizontalPriceInput(selectedDrawing.price.toFixed(2));
      setRectangleTopInput("");
      setRectangleBottomInput("");
      return;
    }

    if (selectedDrawing.kind === "rectangle") {
      setHorizontalPriceInput("");
      setRectangleTopInput(selectedDrawing.start.price.toFixed(2));
      setRectangleBottomInput(selectedDrawing.end.price.toFixed(2));
      return;
    }

    setHorizontalPriceInput("");
    setRectangleTopInput("");
    setRectangleBottomInput("");
  }, [selectedDrawing]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      window.localStorage.setItem(storageKey, JSON.stringify(drawings));
    } catch {
      // Ignore quota/storage errors and keep the in-memory editor responsive.
    }
  }, [drawings, storageKey]);

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
      onRuntimeReady: setRuntimeApi,
      onViewportChange: () => setViewportVersion((current) => current + 1),
    });
    host.rootEl.dataset.chartEngine = "lightweight";

    return () => {
      cleanup();
    };
  }, [chartModel, theme]);

  useEffect(() => {
    if (!selectedDrawing || !runtimeApi || !viewportRef.current) {
      setEditorPosition(null);
      return;
    }

    const viewportEl = viewportRef.current;
    const bounds = getDrawingBounds(selectedDrawing, runtimeApi, viewportEl);
    if (!bounds) {
      setEditorPosition(null);
      return;
    }

    const computePosition = (panelWidth: number, panelHeight: number) => {
      const anchorX = (bounds.left + bounds.right) / 2;
      const left = clamp(anchorX - panelWidth / 2, 8, viewportEl.clientWidth - panelWidth - 8);
      const preferredTop = bounds.top - panelHeight - 12;
      const top =
        preferredTop >= 8
          ? preferredTop
          : clamp(bounds.bottom + 12, 8, viewportEl.clientHeight - panelHeight - 8);

      return { left, top };
    };

    setEditorPosition(computePosition(editorEstimate.width, editorEstimate.height));

    const frame = requestAnimationFrame(() => {
      const panelEl = editorRef.current;
      if (!panelEl) {
        return;
      }

      setEditorPosition(computePosition(panelEl.offsetWidth, panelEl.offsetHeight));
    });

    return () => {
      cancelAnimationFrame(frame);
    };
  }, [selectedDrawing, runtimeApi, drawings]);

  useEffect(() => {
    if (!dragState || !runtimeApi || !viewportRef.current) {
      return;
    }

    const viewportEl = viewportRef.current;
    const viewportBounds = viewportEl.getBoundingClientRect();

    const handleMouseMove = (event: MouseEvent) => {
      const shouldPan =
        dragState.kind === "trend" ||
        dragState.kind === "trend-start" ||
        dragState.kind === "trend-end" ||
        dragState.kind === "rectangle-move" ||
        dragState.kind === "rectangle-resize" ||
        dragState.kind === "vertical";

      if (shouldPan) {
        const panDelta = getEdgePanDelta(event.clientX, viewportBounds);
        if (panDelta !== 0) {
          runtimeApi.panByPixels(panDelta);
        }
      }

      setDrawings((current) =>
        current.map((drawing) => {
          if (drawing.id !== dragState.id) {
            return drawing;
          }

          if (dragState.kind === "horizontal" && drawing.kind === "horizontal") {
            const originY = runtimeApi.priceToY(dragState.originPrice);
            if (originY === null) {
              return drawing;
            }

            const nextPrice = runtimeApi.yToPrice(clamp(originY + (event.clientY - dragState.originClientY), 0, viewportBounds.height));
            if (nextPrice === null) {
              return drawing;
            }

            return { ...drawing, price: nextPrice };
          }

          if (dragState.kind === "vertical" && drawing.kind === "vertical") {
            const originX = runtimeApi.timeToX(dragState.originTime);
            if (originX === null) {
              return drawing;
            }

            const nextTime = runtimeApi.xToTime(
              clamp(
                originX + (event.clientX - dragState.originClientX),
                0,
                viewportBounds.width,
              ),
            );
            if (nextTime === null) {
              return drawing;
            }

            return { ...drawing, time: nextTime };
          }

          if (dragState.kind === "trend" && drawing.kind === "trend") {
            const dx = event.clientX - dragState.originClientX;
            const dy = event.clientY - dragState.originClientY;
            const nextStart = shiftPoint(dragState.start, dx, dy, viewportEl, runtimeApi);
            const nextEnd = shiftPoint(dragState.end, dx, dy, viewportEl, runtimeApi);
            return {
              ...drawing,
              start: nextStart,
              end: nextEnd,
            };
          }

          if (dragState.kind === "trend-start" && drawing.kind === "trend") {
            const nextPoint = getDrawingPointFromClient(
              event.clientX,
              event.clientY,
              viewportEl,
              runtimeApi,
            );
            return nextPoint ? { ...drawing, start: nextPoint } : drawing;
          }

          if (dragState.kind === "trend-end" && drawing.kind === "trend") {
            const nextPoint = getDrawingPointFromClient(
              event.clientX,
              event.clientY,
              viewportEl,
              runtimeApi,
            );
            return nextPoint ? { ...drawing, end: nextPoint } : drawing;
          }

          if (dragState.kind === "rectangle-move" && drawing.kind === "rectangle") {
            const dx = event.clientX - dragState.originClientX;
            const dy = event.clientY - dragState.originClientY;
            const nextStart = shiftPoint(dragState.start, dx, dy, viewportEl, runtimeApi);
            const nextEnd = shiftPoint(dragState.end, dx, dy, viewportEl, runtimeApi);
            return { ...drawing, ...normalizeRectangle(nextStart, nextEnd) };
          }

          if (dragState.kind === "rectangle-resize" && drawing.kind === "rectangle") {
            const original = { ...drawing, ...normalizeRectangle(dragState.start, dragState.end) };
            const corners = getRectangleCorners(original, runtimeApi);
            if (!corners) {
              return drawing;
            }

            const oppositeHandle: Record<RectangleHandle, RectangleHandle> = {
              nw: "se",
              ne: "sw",
              sw: "ne",
              se: "nw",
            };
            const movedCorner = corners[dragState.handle];
            const fixedCorner = corners[oppositeHandle[dragState.handle]];
            const movedPoint = getDrawingPointFromClient(
              clamp(movedCorner.x + (event.clientX - dragState.originClientX), 0, viewportBounds.width) + viewportBounds.left,
              clamp(movedCorner.y + (event.clientY - dragState.originClientY), 0, viewportBounds.height) + viewportBounds.top,
              viewportEl,
              runtimeApi,
            );
            const fixedPoint = getDrawingPointFromClient(
              fixedCorner.x + viewportBounds.left,
              fixedCorner.y + viewportBounds.top,
              viewportEl,
              runtimeApi,
            );

            if (!movedPoint || !fixedPoint) {
              return drawing;
            }

            return { ...drawing, ...normalizeRectangle(movedPoint, fixedPoint) };
          }

          return drawing;
        }),
      );
    };

    const handleMouseUp = () => {
      setDragState(null);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [dragState, runtimeApi]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isEditable =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT" ||
        target?.isContentEditable;

      if (isEditable) {
        return;
      }

      if (event.key === "Escape") {
        setSelectedTool(null);
        setDraftPoint(null);
        setPreviewPoint(null);
        setSelectedDrawingId(null);
        setDragState(null);
      }

      if (event.key === "Delete" && selectedDrawingId) {
        setDrawings((current) => current.filter((drawing) => drawing.id !== selectedDrawingId));
        setSelectedDrawingId(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [selectedDrawingId]);

  useEffect(() => {
    if (!selectedDrawingId) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) {
        return;
      }

      if (editorRef.current?.contains(target)) {
        return;
      }

      if (target.closest("[data-drawing-interactive='true']")) {
        return;
      }

      setSelectedDrawingId(null);
    };

    document.addEventListener("pointerdown", handlePointerDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [selectedDrawingId]);

  const handleToolSelect = (tool: DrawingTool) => {
    setSelectedTool((current) => (current === tool ? null : tool));
    setDraftPoint(null);
    setPreviewPoint(null);
    setSelectedDrawingId(null);
  };

  const handleClearAll = () => {
    setDrawings([]);
    setSelectedDrawingId(null);
    setDraftPoint(null);
    setPreviewPoint(null);
    setSelectedTool(null);
    setDragState(null);
  };

  const updateSelectedDrawing = (updater: (drawing: TerminalDrawing) => TerminalDrawing) => {
    if (!selectedDrawingId) {
      return;
    }

    setDrawings((current) =>
      current.map((drawing) => (drawing.id === selectedDrawingId ? updater(drawing) : drawing)),
    );
  };

  const parseNumericInput = (value: string) => {
    const normalized = value.replace(",", ".").trim();
    if (!normalized) {
      return null;
    }

    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const handleHorizontalPriceInput = (value: string) => {
    setHorizontalPriceInput(value);
    const parsed = parseNumericInput(value);
    if (parsed === null) {
      return;
    }

    updateSelectedDrawing((drawing) => (drawing.kind === "horizontal" ? { ...drawing, price: parsed } : drawing));
  };

  const handleRectanglePriceInput = (bound: "top" | "bottom", value: string) => {
    if (bound === "top") {
      setRectangleTopInput(value);
    } else {
      setRectangleBottomInput(value);
    }

    const parsed = parseNumericInput(value);
    if (parsed === null) {
      return;
    }

    updateSelectedDrawing((drawing) => {
      if (drawing.kind !== "rectangle") {
        return drawing;
      }

      const nextTop = bound === "top" ? parsed : drawing.start.price;
      const nextBottom = bound === "bottom" ? parsed : drawing.end.price;
      return {
        ...drawing,
        ...normalizeRectangle(
          { time: drawing.start.time, price: nextTop },
          { time: drawing.end.time, price: nextBottom },
        ),
      };
    });
  };

  const handleCaptureClick = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!selectedTool || !runtimeApi || !viewportRef.current) {
      return;
    }

    const point = getDrawingPointFromClient(
      event.clientX,
      event.clientY,
      viewportRef.current,
      runtimeApi,
    );
    if (!point) {
      return;
    }

    if (selectedTool === "horizontal") {
      const drawing: HorizontalDrawing = {
        id: createDrawingId(),
        kind: "horizontal",
        price: point.price,
        ...defaultDrawingStyle,
      };
      setDrawings((current) => [...current, drawing]);
      setSelectedDrawingId(drawing.id);
      setSelectedTool(null);
      return;
    }

    if (selectedTool === "vertical") {
      const drawing: VerticalDrawing = {
        id: createDrawingId(),
        kind: "vertical",
        time: point.time,
        ...defaultDrawingStyle,
      };
      setDrawings((current) => [...current, drawing]);
      setSelectedDrawingId(drawing.id);
      setSelectedTool(null);
      return;
    }

    if (!draftPoint) {
      setDraftPoint(point);
      setPreviewPoint(point);
      return;
    }

    if (selectedTool === "trend") {
      const drawing: TrendDrawing = {
        id: createDrawingId(),
        kind: "trend",
        start: draftPoint,
        end: point,
        ...defaultDrawingStyle,
      };
      setDrawings((current) => [...current, drawing]);
      setSelectedDrawingId(drawing.id);
    }

    if (selectedTool === "rectangle") {
      const drawing: RectangleDrawing = {
        id: createDrawingId(),
        kind: "rectangle",
        ...normalizeRectangle(draftPoint, point),
        ...defaultDrawingStyle,
      };
      setDrawings((current) => [...current, drawing]);
      setSelectedDrawingId(drawing.id);
    }

    setDraftPoint(null);
    setPreviewPoint(null);
    setSelectedTool(null);
  };

  const handleCaptureMove = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!selectedTool || !runtimeApi || !viewportRef.current) {
      return;
    }

    const point = getDrawingPointFromClient(
      event.clientX,
      event.clientY,
      viewportRef.current,
      runtimeApi,
    );
    if (point) {
      if (draftPoint) {
        setPreviewPoint(point);
      }
      return;
    }
  };

  const handleDrawingSelect = (event: ReactMouseEvent<SVGElement>, drawingId: string) => {
    event.preventDefault();
    event.stopPropagation();
    setSelectedTool(null);
    setDraftPoint(null);
    setPreviewPoint(null);
    setSelectedDrawingId(drawingId);
  };

  const startDrag = (event: ReactMouseEvent<SVGElement>, nextDragState: DragState) => {
    event.preventDefault();
    event.stopPropagation();
    setSelectedTool(null);
    setDraftPoint(null);
    setPreviewPoint(null);
    setSelectedDrawingId(nextDragState.id);
    setDragState(nextDragState);
  };

  const renderDrawing = (drawing: TerminalDrawing) => {
    if (!runtimeApi || !viewportRef.current) {
      return null;
    }

    const isSelected = drawing.id === selectedDrawingId;
    const strokeWidth = isSelected ? drawing.width + 1 : drawing.width;

    if (drawing.kind === "horizontal") {
      const y = runtimeApi.priceToY(drawing.price);
      if (y === null) {
        return null;
      }

      return (
        <g key={drawing.id}>
          <line
            x1={0}
            y1={y}
            x2={viewportRef.current.clientWidth}
            y2={y}
            stroke="transparent"
            strokeWidth={Math.max(invisibleHitWidth, strokeWidth + 8)}
            pointerEvents="stroke"
            data-drawing-interactive="true"
            onClick={(event) => handleDrawingSelect(event, drawing.id)}
            onMouseDown={(event) =>
              startDrag(event, {
                kind: "horizontal",
                id: drawing.id,
                originClientY: event.clientY,
                originPrice: drawing.price,
              })
            }
          />
          <line
            x1={0}
            y1={y}
            x2={viewportRef.current.clientWidth}
            y2={y}
            stroke={drawing.color}
            strokeWidth={strokeWidth}
            strokeDasharray={isSelected ? "6 4" : undefined}
            pointerEvents="none"
          />
        </g>
      );
    }

    if (drawing.kind === "vertical") {
      const x = runtimeApi.timeToX(drawing.time);
      if (x === null) {
        return null;
      }

      return (
        <g key={drawing.id}>
          <line
            x1={x}
            y1={0}
            x2={x}
            y2={viewportRef.current.clientHeight}
            stroke="transparent"
            strokeWidth={Math.max(invisibleHitWidth, strokeWidth + 8)}
            pointerEvents="stroke"
            data-drawing-interactive="true"
            onClick={(event) => handleDrawingSelect(event, drawing.id)}
            onMouseDown={(event) =>
              startDrag(event, {
                kind: "vertical",
                id: drawing.id,
                originClientX: event.clientX,
                originTime: drawing.time,
              })
            }
          />
          <line
            x1={x}
            y1={0}
            x2={x}
            y2={viewportRef.current.clientHeight}
            stroke={drawing.color}
            strokeWidth={strokeWidth}
            strokeDasharray={isSelected ? "6 4" : undefined}
            pointerEvents="none"
          />
        </g>
      );
    }

    if (drawing.kind === "trend") {
      const start = getScreenPoint(drawing.start, runtimeApi);
      const end = getScreenPoint(drawing.end, runtimeApi);
      if (!start || !end) {
        return null;
      }

      return (
        <g key={drawing.id}>
          <line
            x1={start.x}
            y1={start.y}
            x2={end.x}
            y2={end.y}
            stroke="transparent"
            strokeWidth={Math.max(invisibleHitWidth, strokeWidth + 8)}
            pointerEvents="stroke"
            data-drawing-interactive="true"
            onClick={(event) => handleDrawingSelect(event, drawing.id)}
            onMouseDown={(event) =>
              startDrag(event, {
                kind: "trend",
                id: drawing.id,
                originClientX: event.clientX,
                originClientY: event.clientY,
                start: drawing.start,
                end: drawing.end,
              })
            }
          />
          <line
            x1={start.x}
            y1={start.y}
            x2={end.x}
            y2={end.y}
            stroke={drawing.color}
            strokeWidth={strokeWidth}
            strokeDasharray={isSelected ? "6 4" : undefined}
            pointerEvents="none"
          />
          {isSelected ? (
            <>
              <circle
                cx={start.x}
                cy={start.y}
                r={rectangleHandleSize / 2}
                fill={drawing.color}
                stroke={colors.panelBackground}
                strokeWidth={1}
                className={chartDrawingHandle}
                style={{ cursor: "grab" }}
                pointerEvents="all"
                data-drawing-interactive="true"
                onMouseDown={(event) =>
                  startDrag(event, {
                    kind: "trend-start",
                    id: drawing.id,
                  })
                }
              />
              <circle
                cx={end.x}
                cy={end.y}
                r={rectangleHandleSize / 2}
                fill={drawing.color}
                stroke={colors.panelBackground}
                strokeWidth={1}
                className={chartDrawingHandle}
                style={{ cursor: "grab" }}
                pointerEvents="all"
                data-drawing-interactive="true"
                onMouseDown={(event) =>
                  startDrag(event, {
                    kind: "trend-end",
                    id: drawing.id,
                  })
                }
              />
            </>
          ) : null}
        </g>
      );
    }

    const corners = getRectangleCorners(drawing, runtimeApi);
    if (!corners) {
      return null;
    }

    const width = Math.max(corners.se.x - corners.nw.x, 1);
    const height = Math.max(corners.se.y - corners.nw.y, 1);

    return (
      <g key={drawing.id}>
        <rect
          x={corners.nw.x}
          y={corners.nw.y}
          width={width}
          height={height}
          fill="transparent"
          stroke="transparent"
          strokeWidth={Math.max(invisibleHitWidth, strokeWidth + 8)}
          pointerEvents="all"
          data-drawing-interactive="true"
          onClick={(event) => handleDrawingSelect(event, drawing.id)}
          onMouseDown={(event) =>
            startDrag(event, {
              kind: "rectangle-move",
              id: drawing.id,
              originClientX: event.clientX,
              originClientY: event.clientY,
              start: drawing.start,
              end: drawing.end,
            })
          }
        />
        <rect
          x={corners.nw.x}
          y={corners.nw.y}
          width={width}
          height={height}
          fill={toTranslucentFill(drawing.color)}
          stroke={drawing.color}
          strokeWidth={strokeWidth}
          strokeDasharray={isSelected ? "6 4" : undefined}
          pointerEvents="none"
        />
        {isSelected
          ? ([
              { key: "nw", point: corners.nw, cursor: "nwse-resize" },
              { key: "ne", point: corners.ne, cursor: "nesw-resize" },
              { key: "sw", point: corners.sw, cursor: "nesw-resize" },
              { key: "se", point: corners.se, cursor: "nwse-resize" },
            ] as const).map((handle) => (
              <rect
                key={handle.key}
                x={handle.point.x - rectangleHandleSize / 2}
                y={handle.point.y - rectangleHandleSize / 2}
                width={rectangleHandleSize}
                height={rectangleHandleSize}
                rx={3}
                ry={3}
                fill={drawing.color}
                stroke={colors.panelBackground}
                strokeWidth={1}
                className={chartDrawingHandle}
                style={{ cursor: handle.cursor }}
                pointerEvents="all"
                data-drawing-interactive="true"
                onMouseDown={(event) =>
                  startDrag(event, {
                    kind: "rectangle-resize",
                    id: drawing.id,
                    handle: handle.key,
                    originClientX: event.clientX,
                    originClientY: event.clientY,
                    start: drawing.start,
                    end: drawing.end,
                  })
                }
              />
            ))
          : null}
      </g>
    );
  };

  const renderPreview = () => {
    if (!runtimeApi || !selectedTool || !draftPoint || !previewPoint) {
      return null;
    }

    if (selectedTool === "trend") {
      const start = getScreenPoint(draftPoint, runtimeApi);
      const end = getScreenPoint(previewPoint, runtimeApi);
      if (!start || !end) {
        return null;
      }

      return (
        <line
          x1={start.x}
          y1={start.y}
          x2={end.x}
          y2={end.y}
          stroke={defaultDrawingStyle.color}
          strokeWidth={defaultDrawingStyle.width}
          strokeDasharray="5 5"
          pointerEvents="none"
        />
      );
    }

    if (selectedTool === "rectangle") {
      const normalized = normalizeRectangle(draftPoint, previewPoint);
      const topLeft = getScreenPoint(normalized.start, runtimeApi);
      const bottomRight = getScreenPoint(normalized.end, runtimeApi);
      if (!topLeft || !bottomRight) {
        return null;
      }

      return (
        <rect
          x={topLeft.x}
          y={topLeft.y}
          width={Math.max(bottomRight.x - topLeft.x, 1)}
          height={Math.max(bottomRight.y - topLeft.y, 1)}
          fill="rgba(114, 212, 255, 0.08)"
          stroke={defaultDrawingStyle.color}
          strokeWidth={defaultDrawingStyle.width}
          strokeDasharray="5 5"
          pointerEvents="none"
        />
      );
    }

    return null;
  };

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
        <DrawingToolbar
          activeTool={selectedTool}
          onSelect={handleToolSelect}
          onClearAll={handleClearAll}
          hasDrawings={drawings.length > 0}
        />
        <div ref={hostRef} className={chartCanvas} />
        <div className={chartDrawingLayer}>
          <svg className={chartDrawingSvg}>
            {drawings.map(renderDrawing)}
            {renderPreview()}
          </svg>
        </div>
        {selectedDrawing ? (
          <div
            ref={editorRef}
            className={chartDrawingEditor}
            data-drawing-interactive="true"
            style={{
              left: `${editorPosition?.left ?? 12}px`,
              top: `${editorPosition?.top ?? 12}px`,
            }}
          >
            {selectedDrawing.kind === "horizontal" ? (
              <label className={chartDrawingField}>
                <span className={chartDrawingFieldLabel}>Цена</span>
                <input
                  type="number"
                  step="0.01"
                  className={chartDrawingFieldInput}
                  value={horizontalPriceInput}
                  onChange={(event) => handleHorizontalPriceInput(event.target.value)}
                />
              </label>
            ) : null}
            {selectedDrawing.kind === "rectangle" ? (
              <>
                <label className={chartDrawingField}>
                  <span className={chartDrawingFieldLabel}>Верх</span>
                  <input
                    type="number"
                    step="0.01"
                    className={chartDrawingFieldInput}
                    value={rectangleTopInput}
                    onChange={(event) => handleRectanglePriceInput("top", event.target.value)}
                  />
                </label>
                <label className={chartDrawingField}>
                  <span className={chartDrawingFieldLabel}>Низ</span>
                  <input
                    type="number"
                    step="0.01"
                    className={chartDrawingFieldInput}
                    value={rectangleBottomInput}
                    onChange={(event) => handleRectanglePriceInput("bottom", event.target.value)}
                  />
                </label>
              </>
            ) : null}
            <div className={chartDrawingEditorGroup}>
              {drawingPalette.map((color) => (
                <button
                  key={color}
                  type="button"
                  className={`${chartDrawingSwatch} ${selectedDrawing.color === color ? chartDrawingSwatchActive : ""}`}
                  style={{ backgroundColor: color }}
                  aria-label={`Выбрать цвет ${color}`}
                  onClick={() => updateSelectedDrawing((drawing) => ({ ...drawing, color }))}
                />
              ))}
            </div>
            <div className={chartDrawingEditorGroup}>
              {drawingWidths.map((width) => (
                <button
                  key={width}
                  type="button"
                  className={`${chartDrawingWidthButton} ${selectedDrawing.width === width ? chartDrawingWidthButtonActive : ""}`}
                  onClick={() => updateSelectedDrawing((drawing) => ({ ...drawing, width }))}
                >
                  {width}
                </button>
              ))}
            </div>
            <button
              type="button"
              className={chartDrawingDeleteButton}
              onClick={() => {
                setDrawings((current) => current.filter((drawing) => drawing.id !== selectedDrawing.id));
                setSelectedDrawingId(null);
              }}
            >
              Удалить
            </button>
          </div>
        ) : null}
        {selectedTool ? (
          <div
            className={chartDrawingCapture}
            onClick={handleCaptureClick}
            onMouseMove={handleCaptureMove}
            onMouseLeave={() => setPreviewPoint(null)}
          />
        ) : null}
      </div>
    </div>
  );
}
