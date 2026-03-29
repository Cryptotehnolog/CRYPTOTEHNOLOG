import { type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent, type ReactNode, type Ref, useEffect, useRef, useState } from "react";
import GridLayoutBase, { type Layout } from "react-grid-layout/legacy";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { TerminalChartSurface } from "../components/TerminalChartSurface";
import { useTerminalWidgetStore } from "../state/useTerminalWidgetStore";
import { type TerminalWidget, type TerminalWidgetId } from "../state/terminalWidgets";
import {
  attentionHeader,
  attentionItem,
  attentionList,
  attentionMeta,
  attentionSeverity,
  attentionSeverityHigh,
  attentionSeverityMedium,
  attentionStatus,
  attentionSummary,
  attentionTimestamp,
  card,
  chartHeader,
  chartHeaderControlsColumn,
  chartHeaderLead,
  chartSurfaceSlot,
  chartStat,
  chartStatLabel,
  chartStatValue,
  chartToolbar,
  chartToolbarGroup,
  chartToolbarMenu,
  chartToolbarMenuAnchor,
  chartToolbarMenuButton,
  chartToolbarMenuDivider,
  chartToolbarMenuForm,
  chartToolbarMenuFormAction,
  chartToolbarMenuFormField,
  chartToolbarMenuFormInput,
  chartToolbarMenuFormLabel,
  chartToolbarMenuFormRow,
  chartToolbarMenuItem,
  chartToolbarMenuItemActive,
  chartToolbarMenuItemWrap,
  chartToolbarMenuRemoveButton,
  chartToolbarMenuTrigger,
  chartToolbarTimeframes,
  compactCard,
  compactListContent,
  compactStatContent,
  displayModeButton,
  displayModeButtonActive,
  marketChangeUpStrong,
  marketGrid,
  marketHeaderMeta,
  marketInstrumentLabel,
  marketPairDetails,
  marketPairBody,
  marketPairContext,
  marketPairExchange,
  marketPairHeader,
  marketPairMain,
  marketPair,
  marketPairActive,
  marketPairPriceMain,
  marketPairQuote,
  marketPairMoveDown,
  marketPairMoveUp,
  marketPairPrice,
  marketPairSignal,
  marketPriceCluster,
  marketPrimaryValue,
  pageRoot,
  positionsTable,
  positionsTableActionOpen,
  positionMetricCell,
  positionModeButton,
  positionModeButtonActive,
  positionModeSwitch,
  positionInstrumentActive,
  positionActionPanel,
  positionActionPanelActions,
  positionActionPanelCancel,
  positionActionPanelConfirm,
  positionActionPanelMeta,
  positionActionPanelText,
  positionActionPanelTitle,
  positionActionOverlayLayer,
  positionActionsAnchor,
  positionActionsCell,
  positionActionsMenu,
  positionActionsMenuItem,
  positionActionsTrigger,
  positionsWidgetHeader,
  positionsWidgetHeaderMain,
  positionPairCell,
  positionPnlNegative,
  positionPnlPositive,
  positionPrimaryValue,
  positionSecondaryValue,
  positionStrategyCell,
  positionSideLong,
  positionSideShort,
  positionStatusCell,
  positionStatusMeta,
  positionStatusValue,
  positionsTableViewport,
  positionsTableViewportActionOpen,
  positionsTableBodyViewport,
  positionsWidgetContentExpanded,
  positionsWidgetFrameExpanded,
  positionsWidgetContent,
  positionTimestampCell,
  positionsHistoryControls,
  positionsHistoryControlsGroup,
  positionsHistorySearchInput,
  positionsHistorySelect,
  tableCell,
  tableHeader,
  tableRow,
  tableRowActive,
  tableRowInteractive,
  widgetDragDots,
  widgetDragHandle,
  widgetFocusControl,
  widgetFocusControlActive,
  widgetHeaderControls,
  widgetTitle,
  widgetCanvas,
  chartWidgetContent,
  scrollableWidgetContent,
  widgetFrame,
  widgetFrameContent,
  widgetHeaderMeta,
  widgetHeaderRow,
  widgetShell,
  workspaceCard,
} from "./TerminalPage.css";

const GridLayout = GridLayoutBase;
const widgetGridColumns = 96;
const widgetGridRowHeight = 6;
const widgetGridMargin: [number, number] = [2, 2];

const marketWatch = [
  {
    pair: "BTC/USDT",
    exchange: "OKX",
    price: "67 420",
    spread: "спред 4.2",
    signal: "лидер роста",
    context: "bid 67 418 · ask 67 422",
    move: "+1.8%",
    tone: "up",
  },
  {
    pair: "ETH/USDT",
    exchange: "Bybit",
    price: "3 540",
    spread: "спред 2.8",
    signal: "спрос держится",
    context: "bid 3 538 · ask 3 541",
    move: "+0.9%",
    tone: "up",
  },
  {
    pair: "SOL/USDT",
    exchange: "Binance",
    price: "178.4",
    spread: "спред 1.6",
    signal: "давление вниз",
    context: "bid 178.3 · ask 178.5",
    move: "-0.6%",
    tone: "down",
  },
  {
    pair: "BNB/USDT",
    exchange: "OKX",
    price: "611.8",
    spread: "спред 1.1",
    signal: "баланс в норме",
    context: "bid 611.7 · ask 611.9",
    move: "+0.4%",
    tone: "up",
  },
  {
    pair: "XRP/USDT",
    exchange: "Bybit",
    price: "0.642",
    spread: "спред 0.3",
    signal: "продавец активен",
    context: "bid 0.641 · ask 0.643",
    move: "-1.2%",
    tone: "down",
  },
];

const positions = [
  {
    pair: "BTC/USDT",
    exchange: "OKX",
    strategy: "Momentum Core",
    side: "LONG",
    entry: "66 910",
    last: "67 420",
    size: "0.42 BTC",
    stop: "65 980",
    risk: "в норме",
    pnl: "+2.14%",
    pnlValue: "+$1 436",
    tone: "up",
  },
  {
    pair: "ETH/USDT",
    exchange: "Bybit",
    strategy: "Session Follow",
    side: "LONG",
    entry: "3 488",
    last: "3 540",
    size: "3.10 ETH",
    stop: "3 420",
    risk: "под контролем",
    pnl: "+1.47%",
    pnlValue: "+$161",
    tone: "up",
  },
  {
    pair: "SOL/USDT",
    exchange: "Binance",
    strategy: "Risk Fade",
    side: "SHORT",
    entry: "179.9",
    last: "178.4",
    size: "124 SOL",
    stop: "182.2",
    risk: "наблюдение",
    pnl: "-0.31%",
    pnlValue: "-$69",
    tone: "down",
  },
];

const positionHistory = [
  {
    pair: "BTC/USDT",
    exchange: "OKX",
    strategy: "Breakout Pulse",
    side: "LONG",
    entry: "65 880",
    exit: "66 540",
    size: "0.35 BTC",
    result: "+1.00%",
    resultValue: "+$742",
    closedAt: "сегодня · 14:28",
    closedAtSort: "2026-03-29T14:28:00+03:00",
    tone: "up",
  },
  {
    pair: "ETH/USDT",
    exchange: "Bybit",
    strategy: "Range Return",
    side: "SHORT",
    entry: "3 612",
    exit: "3 575",
    size: "2.20 ETH",
    result: "+0.82%",
    resultValue: "+$81",
    closedAt: "сегодня · 12:16",
    closedAtSort: "2026-03-29T12:16:00+03:00",
    tone: "up",
  },
  {
    pair: "SOL/USDT",
    exchange: "Binance",
    strategy: "Risk Fade",
    side: "LONG",
    entry: "181.6",
    exit: "180.9",
    size: "96 SOL",
    result: "-0.39%",
    resultValue: "-$67",
    closedAt: "вчера · 21:04",
    closedAtSort: "2026-03-28T21:04:00+03:00",
    tone: "down",
  },
];

const positionQuickActions = ["закрыть", "перевернуть", "stop-loss", "в безубыток"] as const;
type PositionQuickAction = (typeof positionQuickActions)[number];
const positionActionMenuEstimate = { width: 156, height: 156 };
const positionActionConfirmEstimate = { width: 240, height: 158 };

const positionQuickActionLabels: Record<PositionQuickAction, string> = {
  "закрыть": "Закрыть позицию",
  "перевернуть": "Перевернуть позицию",
  "stop-loss": "Обновить stop-loss",
  "в безубыток": "Перевести в безубыток",
};

const positionQuickActionDescriptions: Record<PositionQuickAction, string> = {
  "закрыть": "Mock-действие: позиция будет подготовлена к закрытию без реального исполнения.",
  "перевернуть": "Mock-действие: позиция будет подготовлена к развороту в противоположную сторону.",
  "stop-loss": "Mock-действие: для позиции будет подготовлен защитный stop-loss.",
  "в безубыток": "Mock-действие: stop-loss будет перенесён в точку безубытка.",
};

const attentionItems = [
  {
    severity: "Высокий",
    status: "Требует действия",
    scope: "OKX · связность",
    time: "сейчас",
    title: "Подтвердить ручной режим по OKX",
    meta: "Связность биржи прогревается, нужен взгляд оператора.",
  },
  {
    severity: "Средний",
    status: "Под наблюдением",
    scope: "SOL · риск",
    time: "2 мин назад",
    title: "Риск по SOL приблизился к лимиту",
    meta: "Позиция короткая, плечо выросло выше утреннего профиля.",
  },
  {
    severity: "Средний",
    status: "Ожидает проверки",
    scope: "Отчётность · контур",
    time: "5 мин назад",
    title: "Отчётность не собрала итоговый пакет",
    meta: "Артефакты есть, но итоговый пакет ещё не выведен.",
  },
];

const baseTimeframes = ["1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1D", "2D", "3D", "1W", "1M"];
const initialSelectedTimeframes = ["1m", "5m", "15m", "1h", "4h", "1D"];
const customTimeframesStorageKey = "cryptotechnolog.terminal.custom-timeframes";
const selectedTimeframesStorageKey = "cryptotechnolog.terminal.selected-timeframes";
const timeframeUnitOptions = [
  { value: "s", label: "Секунды" },
  { value: "m", label: "Минуты" },
  { value: "h", label: "Часы" },
  { value: "D", label: "Дни" },
  { value: "W", label: "Недели" },
  { value: "M", label: "Месяцы" },
];

const timeframeUnitWeight: Record<string, number> = {
  s: 0,
  m: 1,
  h: 2,
  D: 3,
  W: 4,
  M: 5,
};

function parseTimeframe(value: string) {
  const match = value.match(/^(\d+)([a-zA-Z]+)$/);
  if (!match) {
    return { amount: Number.MAX_SAFE_INTEGER, unit: "Z", weight: Number.MAX_SAFE_INTEGER };
  }

  const unit = match[2];
  return {
    amount: Number.parseInt(match[1], 10),
    unit,
    weight: timeframeUnitWeight[unit] ?? Number.MAX_SAFE_INTEGER,
  };
}

function compareTimeframes(left: string, right: string) {
  const leftParsed = parseTimeframe(left);
  const rightParsed = parseTimeframe(right);

  if (leftParsed.weight !== rightParsed.weight) {
    return leftParsed.weight - rightParsed.weight;
  }

  if (leftParsed.amount !== rightParsed.amount) {
    return leftParsed.amount - rightParsed.amount;
  }

  return left.localeCompare(right);
}

function loadPersistedCustomTimeframes() {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(customTimeframesStorageKey);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .filter((value): value is string => typeof value === "string")
      .filter((value) => !baseTimeframes.includes(value))
      .sort(compareTimeframes);
  } catch {
    return [];
  }
}

function loadPersistedSelectedTimeframes(availableTimeframes: string[]) {
  if (typeof window === "undefined") {
    return initialSelectedTimeframes;
  }

  try {
    const raw = window.localStorage.getItem(selectedTimeframesStorageKey);
    if (!raw) {
      return initialSelectedTimeframes;
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return initialSelectedTimeframes;
    }

    const sanitized = parsed
      .filter((value): value is string => typeof value === "string")
      .filter((value) => availableTimeframes.includes(value))
      .sort(compareTimeframes);

    return sanitized.length > 0 ? sanitized : initialSelectedTimeframes;
  } catch {
    return initialSelectedTimeframes;
  }
}

function WidgetShell(props: {
  title?: string;
  dragLabel: string;
  cardClassName: string;
  contentClassName?: string;
  frameClassName?: string;
  frameStyle?: CSSProperties;
  isFocused?: boolean;
  onToggleFocus?: () => void;
  children: ReactNode;
}) {
  return (
    <div className={widgetShell}>
      <section
        className={`${props.cardClassName} ${widgetFrame} ${props.frameClassName ?? ""}`}
        style={props.frameStyle}
      >
        {props.title ? (
          <div className={widgetHeaderRow}>
            <span
              className={`${widgetDragHandle} terminal-widget-drag-handle`}
              role="button"
              tabIndex={0}
              aria-label={`Переместить ${props.dragLabel}`}
            >
              {Array.from({ length: 9 }).map((_, index) => (
                <span key={index} className={widgetDragDots} />
              ))}
              </span>
              <div className={widgetHeaderMeta}>
                <h2 className={widgetTitle}>{props.title}</h2>
              </div>
              {props.onToggleFocus ? (
                <div className={widgetHeaderControls}>
                  <button
                    type="button"
                    className={`${widgetFocusControl} terminal-widget-no-drag ${props.isFocused ? widgetFocusControlActive : ""}`}
                    aria-label={props.isFocused ? `Свернуть ${props.dragLabel}` : `Вывести поверх ${props.dragLabel}`}
                    onClick={props.onToggleFocus}
                  >
                    {props.isFocused ? "×" : "⤢"}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
        <div className={props.contentClassName ?? widgetFrameContent}>{props.children}</div>
      </section>
    </div>
  );
}

export function TerminalPage() {
  const widgets = useTerminalWidgetStore((state) => state.widgets);
  const updateWidgetLayouts = useTerminalWidgetStore((state) => state.updateWidgetLayouts);
  const initialAllTimeframes = [...baseTimeframes, ...loadPersistedCustomTimeframes()].sort(compareTimeframes);
  const [timeframe, setTimeframe] = useState("15m");
  const [allTimeframes, setAllTimeframes] = useState(initialAllTimeframes);
  const [selectedTimeframes, setSelectedTimeframes] = useState(() =>
    loadPersistedSelectedTimeframes(initialAllTimeframes),
  );
  const [activeInstrument, setActiveInstrument] = useState("BTC/USDT");
  const [marketSelectedInstrument, setMarketSelectedInstrument] = useState<string | null>("BTC/USDT");
  const [positionsSelectedInstrument, setPositionsSelectedInstrument] = useState<string | null>(null);
  const [positionsView, setPositionsView] = useState<"open" | "history">("open");
  const [openPositionActionsFor, setOpenPositionActionsFor] = useState<string | null>(null);
  const [pendingPositionAction, setPendingPositionAction] = useState<{
    rowKey: string;
    action: PositionQuickAction;
  } | null>(null);
  const [positionActionExpandPx, setPositionActionExpandPx] = useState(0);
  const [positionActionOverlayPosition, setPositionActionOverlayPosition] = useState<{ top: number; left: number } | null>(null);
  const [historyPairQuery, setHistoryPairQuery] = useState("");
  const [historyExchangeFilter, setHistoryExchangeFilter] = useState("all");
  const [historySort, setHistorySort] = useState<"recent" | "result-desc" | "result-asc">("recent");
  const [focusedWidgetId, setFocusedWidgetId] = useState<TerminalWidgetId | null>(null);
  const [isTimeframeMenuOpen, setIsTimeframeMenuOpen] = useState(false);
  const [customTimeframeUnit, setCustomTimeframeUnit] = useState("m");
  const [customTimeframeValue, setCustomTimeframeValue] = useState("2");
  const [gridWidth, setGridWidth] = useState(1200);
  const timeframeMenuRef = useRef<HTMLDivElement | null>(null);
  const positionActionsLayerRef = useRef<HTMLDivElement | null>(null);
  const positionsTableViewportRef = useRef<HTMLDivElement | null>(null);
  const positionActionAnchorRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const widgetCanvasRef = useRef<HTMLDivElement | null>(null);

  const marketContext =
    marketWatch.find((item) => item.pair === activeInstrument) ??
    {
      pair: activeInstrument,
      price: "67 420",
      move: "+0.0%",
      signal: "волатильность выше средней",
    };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setFocusedWidgetId(null);
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    if (!isTimeframeMenuOpen) {
      return undefined;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!timeframeMenuRef.current?.contains(event.target as Node)) {
        setIsTimeframeMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsTimeframeMenuOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isTimeframeMenuOpen]);

  useEffect(() => {
    if (!openPositionActionsFor && !pendingPositionAction) {
      return undefined;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      const activeRowKey = openPositionActionsFor ?? pendingPositionAction?.rowKey ?? null;
      const activeAnchor = activeRowKey ? positionActionAnchorRefs.current[activeRowKey] : null;

      if (!positionActionsLayerRef.current?.contains(target) && !activeAnchor?.contains(target)) {
        setOpenPositionActionsFor(null);
        setPendingPositionAction(null);
        setPositionActionExpandPx(0);
        setPositionActionOverlayPosition(null);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpenPositionActionsFor(null);
        setPendingPositionAction(null);
        setPositionActionExpandPx(0);
        setPositionActionOverlayPosition(null);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [openPositionActionsFor, pendingPositionAction]);

  useEffect(() => {
    if (positionsView === "history") {
      setOpenPositionActionsFor(null);
      setPendingPositionAction(null);
      setPositionActionExpandPx(0);
      setPositionActionOverlayPosition(null);
    }
  }, [positionsView]);

  useEffect(() => {
    const activeRowKey = pendingPositionAction?.rowKey ?? openPositionActionsFor;
    if (!activeRowKey) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      const layer = positionActionsLayerRef.current;
      if (!layer) {
        resolvePositionActionPlacement(
          activeRowKey,
          pendingPositionAction ? positionActionConfirmEstimate : positionActionMenuEstimate,
        );
        return;
      }

      resolvePositionActionPlacement(activeRowKey, {
        width: layer.offsetWidth,
        height: layer.offsetHeight,
      });
    });

    return () => {
      cancelAnimationFrame(frame);
    };
  }, [openPositionActionsFor, pendingPositionAction]);

  useEffect(() => {
    const syncWidth = () => {
      const nextWidth = widgetCanvasRef.current?.getBoundingClientRect().width ?? 1200;
      setGridWidth(Math.max(Math.round(nextWidth), 320));
    };

    syncWidth();
    window.addEventListener("resize", syncWidth);

    return () => {
      window.removeEventListener("resize", syncWidth);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const customTimeframes = allTimeframes.filter((item) => !baseTimeframes.includes(item));
    window.localStorage.setItem(customTimeframesStorageKey, JSON.stringify(customTimeframes));
  }, [allTimeframes]);

  useEffect(() => {
    setSelectedTimeframes((current) => {
      const sanitized = current.filter((item) => allTimeframes.includes(item)).sort(compareTimeframes);

      if (sanitized.length > 0) {
        return sanitized;
      }

      return initialSelectedTimeframes.filter((item) => allTimeframes.includes(item));
    });
  }, [allTimeframes]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(selectedTimeframesStorageKey, JSON.stringify(selectedTimeframes));
  }, [selectedTimeframes]);

  const orderedAllTimeframes = [...allTimeframes].sort(compareTimeframes);
  const orderedSelectedTimeframes = orderedAllTimeframes.filter((item) =>
    selectedTimeframes.includes(item),
  );
  const historyExchangeOptions = [...new Set(positionHistory.map((row) => row.exchange))].sort();
  const filteredHistoryRows = positionHistory
    .filter((row) => {
      const normalizedQuery = historyPairQuery.trim().toLowerCase();
      const matchesPair = normalizedQuery.length === 0 || row.pair.toLowerCase().includes(normalizedQuery);
      const matchesExchange = historyExchangeFilter === "all" || row.exchange === historyExchangeFilter;
      return matchesPair && matchesExchange;
    })
    .sort((left, right) => {
      if (historySort === "recent") {
        return new Date(right.closedAtSort).getTime() - new Date(left.closedAtSort).getTime();
      }

      const leftResult = Number.parseFloat(left.result.replace("%", ""));
      const rightResult = Number.parseFloat(right.result.replace("%", ""));

      if (historySort === "result-desc") {
        return rightResult - leftResult;
      }

      return leftResult - rightResult;
    });
  const visibleToolbarTimeframes = orderedSelectedTimeframes;
  const activePositionActionRowKey = openPositionActionsFor ?? pendingPositionAction?.rowKey ?? null;
  const isPositionActionLayerActive = activePositionActionRowKey !== null;
  const openPositionActionRow = openPositionActionsFor
    ? positions.find((row) => `${row.exchange}-${row.pair}` === openPositionActionsFor) ?? null
    : null;
  const pendingPositionRow = pendingPositionAction
    ? positions.find((row) => `${row.exchange}-${row.pair}` === pendingPositionAction.rowKey) ?? null
    : null;
  const visibleWidgets = widgets.filter((widget) => widget.visible);
  const gridLayout: Layout = visibleWidgets.map((widget) => ({
    i: widget.id,
    x: widget.layout.x,
    y: widget.layout.y,
    w: widget.layout.w,
    h: widget.layout.h,
    maxW: widget.layout.maxW,
    maxH: widget.layout.maxH,
  }));

  const toggleTimeframe = (target: string) => {
    setSelectedTimeframes((current) => {
      const isSelected = current.includes(target);

      if (isSelected) {
        if (current.length === 1) {
          return current;
        }

        const next = current.filter((item) => item !== target);

        if (timeframe === target) {
          const fallback = orderedAllTimeframes.find((item) => next.includes(item));
          if (fallback) {
            setTimeframe(fallback);
          }
        }

        return next;
      }

      return orderedAllTimeframes.filter((item) => [...current, target].includes(item));
    });
  };

  const removeCustomTimeframe = (target: string) => {
    setAllTimeframes((current) => current.filter((item) => item !== target));
    setSelectedTimeframes((current) => {
      if (!current.includes(target)) {
        return current;
      }

      const next = current.filter((item) => item !== target);

      if (timeframe === target) {
        const fallback = orderedAllTimeframes.find((item) => item !== target && next.includes(item));
        if (fallback) {
          setTimeframe(fallback);
        }
      }

      return next;
    });
  };

  const addCustomTimeframe = () => {
    const numericValue = Number.parseInt(customTimeframeValue, 10);
    if (!Number.isFinite(numericValue) || numericValue <= 0) {
      return;
    }

    const normalized = `${numericValue}${customTimeframeUnit}`;
    setAllTimeframes((current) => {
      if (current.includes(normalized)) {
        return current;
      }

      return [...current, normalized].sort(compareTimeframes);
    });
    setCustomTimeframeValue("2");
  };

  const resolvePositionActionPlacement = (
    rowKey: string,
    layerSize?: { width: number; height: number },
  ) => {
    const anchor = positionActionAnchorRefs.current[rowKey];
    const viewport = positionsTableViewportRef.current;

    if (!anchor || !viewport) {
      setPositionActionExpandPx(0);
      setPositionActionOverlayPosition(null);
      return;
    }

    const overlayGap = 6;
    const safeX = 12;
    const safeY = 10;
    const anchorRect = anchor.getBoundingClientRect();
    const viewportRect = viewport.getBoundingClientRect();
    const layerWidth = layerSize?.width ?? 240;
    const layerHeight = layerSize?.height ?? 158;
    const viewportWidth = viewportRect.width;
    const viewportHeight = viewportRect.height;
    const anchorTop = Math.min(
      Math.max(anchorRect.top, viewportRect.top + safeY),
      viewportRect.bottom - safeY - anchorRect.height,
    );
    const anchorBottom = anchorTop + anchorRect.height;
    const preferredLeft = anchorRect.right - viewportRect.left - layerWidth;
    const maxLeft = Math.max(safeX, viewportWidth - layerWidth - safeX);
    const left = Math.min(Math.max(preferredLeft, safeX), maxLeft);
    const topForDown = anchorBottom - viewportRect.top + overlayGap;
    const topForUp = anchorTop - viewportRect.top - layerHeight - overlayGap;
    const fitsBelow = topForDown + layerHeight <= viewportHeight - safeY;
    const fitsAbove = topForUp >= safeY;

    if (fitsBelow) {
      setPositionActionExpandPx(0);
      setPositionActionOverlayPosition({ top: topForDown, left });
      return;
    }

    if (fitsAbove) {
      setPositionActionExpandPx(0);
      setPositionActionOverlayPosition({ top: topForUp, left });
      return;
    }

    const clampedTop = Math.min(
      Math.max(anchorTop - viewportRect.top - Math.max(layerHeight - anchorRect.height, 0) / 2, safeY),
      Math.max(safeY, viewportHeight - layerHeight - safeY),
    );
    const expandPx = Math.max(
      layerHeight + safeY * 2 - viewportHeight,
      topForDown + layerHeight + safeY - viewportHeight + 4,
      0,
    );

    setPositionActionExpandPx(expandPx);
    setPositionActionOverlayPosition({ top: clampedTop, left });
  };

  const handleInstrumentActivate = (pair: string, source: "market" | "positions") => {
    setActiveInstrument(pair);
    if (source === "market") {
      setMarketSelectedInstrument(pair);
      setPositionsSelectedInstrument(null);
      return;
    }

    setPositionsSelectedInstrument(pair);
    setMarketSelectedInstrument(null);
  };

  const handleInstrumentKeyDown = (
    event: ReactKeyboardEvent<HTMLElement>,
    pair: string,
    source: "market" | "positions",
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleInstrumentActivate(pair, source);
    }
  };

  const handlePositionActionsToggle = (
    event: ReactMouseEvent<HTMLButtonElement>,
    rowKey: string,
  ) => {
    event.stopPropagation();
    const isClosingCurrent = openPositionActionsFor === rowKey && !pendingPositionAction;

    if (isClosingCurrent) {
      setOpenPositionActionsFor(null);
      setPendingPositionAction(null);
      setPositionActionExpandPx(0);
      setPositionActionOverlayPosition(null);
      return;
    }

    setPendingPositionAction(null);
    resolvePositionActionPlacement(rowKey, positionActionMenuEstimate);
    setOpenPositionActionsFor(rowKey);
  };

  const handlePositionActionSelect = (
    event: ReactMouseEvent<HTMLButtonElement>,
    rowKey: string,
    action: PositionQuickAction,
  ) => {
    event.stopPropagation();
    setOpenPositionActionsFor(null);
    resolvePositionActionPlacement(rowKey, positionActionConfirmEstimate);
    setPendingPositionAction({ rowKey, action });
  };

  const handlePositionActionCancel = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setPendingPositionAction(null);
    setPositionActionExpandPx(0);
    setPositionActionOverlayPosition(null);
  };

  const handlePositionActionConfirm = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setPendingPositionAction(null);
    setPositionActionExpandPx(0);
    setPositionActionOverlayPosition(null);
  };

  const renderWidget = (widget: TerminalWidget) => {
    const isFocused = focusedWidgetId === widget.id;
    const handleToggleFocus = () => {
      setFocusedWidgetId((current) => (current === widget.id ? null : widget.id));
    };

    switch (widget.id) {
      case "chart":
        return (
          <WidgetShell
            dragLabel="график BTC/USDT"
            cardClassName={workspaceCard}
            contentClassName={chartWidgetContent}
            isFocused={isFocused}
            onToggleFocus={handleToggleFocus}
            >
              <div className={chartHeader}>
                <div className={chartHeaderLead}>
                  <div className={marketPriceCluster}>
                    <span
                    className={`${widgetDragHandle} terminal-widget-drag-handle`}
                    role="button"
                    tabIndex={0}
                    aria-label="Переместить график BTC/USDT"
                  >
                    {Array.from({ length: 9 }).map((_, index) => (
                      <span key={index} className={widgetDragDots} />
                    ))}
                  </span>
                  <span className={marketInstrumentLabel}>{marketContext.pair}</span>
                  <span className={marketPrimaryValue}>{marketContext.price}</span>
                  <span className={marketContext.move.startsWith("-") ? marketPairMoveDown : marketChangeUpStrong}>
                    {marketContext.move}
                  </span>
                </div>
                  <div className={marketHeaderMeta}>
                    <span>{marketContext.signal}</span>
                  </div>
                </div>
                  <div className={chartHeaderControlsColumn}>
                    <div className={`${widgetHeaderControls} terminal-widget-no-drag`}>
                      <button
                        type="button"
                        className={`${widgetFocusControl} ${isFocused ? widgetFocusControlActive : ""}`}
                        aria-label={isFocused ? "Свернуть график BTC/USDT" : "Вывести поверх график BTC/USDT"}
                        onClick={handleToggleFocus}
                      >
                        {isFocused ? "×" : "⤢"}
                      </button>
                    </div>

                    <div className={`${chartToolbar} terminal-widget-no-drag`}>
                      <div className={chartToolbarGroup}>
                        <div className={chartToolbarMenuAnchor} ref={timeframeMenuRef}>
                          <div className={chartToolbarTimeframes}>
                            {visibleToolbarTimeframes.map((option) => (
                              <button
                                key={option}
                                type="button"
                                className={`${displayModeButton} ${timeframe === option ? displayModeButtonActive : ""}`}
                                onClick={() => setTimeframe(option)}
                              >
                                {option}
                              </button>
                            ))}
                            <button
                              type="button"
                              className={chartToolbarMenuTrigger}
                              aria-label="Управление таймфреймами"
                              aria-expanded={isTimeframeMenuOpen}
                              aria-haspopup="dialog"
                              onClick={() => setIsTimeframeMenuOpen((current) => !current)}
                            >
                              ▾
                            </button>
                          </div>
                          {isTimeframeMenuOpen ? (
                            <div className={chartToolbarMenu} role="dialog" aria-label="Выбор таймфреймов">
                              {orderedAllTimeframes.map((option) => {
                                const isSelected = orderedSelectedTimeframes.includes(option);
                                const isCustom = !baseTimeframes.includes(option);

                                return (
                                  <div key={option} className={chartToolbarMenuItemWrap}>
                                    <button
                                      type="button"
                                      className={`${chartToolbarMenuButton} ${isSelected ? chartToolbarMenuItemActive : chartToolbarMenuItem}`}
                                      aria-pressed={isSelected}
                                      onClick={() => toggleTimeframe(option)}
                                    >
                                      {option}
                                    </button>
                                    {isCustom ? (
                                      <button
                                        type="button"
                                        className={chartToolbarMenuRemoveButton}
                                        aria-label={`Удалить ${option}`}
                                        onClick={() => removeCustomTimeframe(option)}
                                      >
                                        ×
                                      </button>
                                    ) : null}
                                  </div>
                                );
                              })}

                              <div className={chartToolbarMenuDivider} />
                              <div className={chartToolbarMenuForm}>
                                <div className={chartToolbarMenuFormLabel}>Добавить интервал</div>
                                <div className={chartToolbarMenuFormRow}>
                                  <select
                                    className={chartToolbarMenuFormField}
                                    aria-label="Тип интервала"
                                    name="timeframe-unit"
                                    value={customTimeframeUnit}
                                    onChange={(event) => setCustomTimeframeUnit(event.target.value)}
                                  >
                                    {timeframeUnitOptions.map((option) => (
                                      <option key={option.value} value={option.value}>
                                        {option.label}
                                      </option>
                                    ))}
                                  </select>

                                  <input
                                    className={chartToolbarMenuFormInput}
                                    aria-label="Числовой интервал"
                                    name="timeframe-value"
                                    inputMode="numeric"
                                    min="1"
                                    step="1"
                                    value={customTimeframeValue}
                                    onChange={(event) => setCustomTimeframeValue(event.target.value.replace(/[^\d]/g, ""))}
                                  />
                                </div>
                                <button
                                  type="button"
                                  className={chartToolbarMenuFormAction}
                                  onClick={addCustomTimeframe}
                                >
                                  Добавить
                                </button>
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
  
              <div className={`${chartSurfaceSlot} terminal-widget-no-drag`}>
              <TerminalChartSurface
                instrument={marketContext.pair}
                move={marketContext.move}
                timeframe={timeframe}
              />
            </div>
          </WidgetShell>
        );

      case "market-watch":
        return (
          <WidgetShell
            title="Рынок"
            dragLabel="рынок"
            cardClassName={compactCard}
              contentClassName={`${compactListContent} ${scrollableWidgetContent} terminal-widget-no-drag`}
              isFocused={isFocused}
              onToggleFocus={handleToggleFocus}
            >
              <div className={marketGrid}>
                {marketWatch.map((item) => (
                  <div
                    key={item.pair}
                    className={`${marketPair} terminal-widget-no-drag ${marketSelectedInstrument === item.pair ? marketPairActive : ""}`}
                    role="button"
                    tabIndex={0}
                    aria-label={`Открыть ${item.pair} на главном графике`}
                    onClick={() => handleInstrumentActivate(item.pair, "market")}
                    onKeyDown={(event) => handleInstrumentKeyDown(event, item.pair, "market")}
                  >
                    <div className={marketPairBody}>
                      <div className={marketPairHeader}>
                        <div className={marketPairMain}>
                          <span className={marketSelectedInstrument === item.pair ? positionInstrumentActive : marketPairPrice}>
                            {item.pair}
                          </span>
                          <span className={marketPairExchange}>{item.exchange}</span>
                        </div>
                        <div className={marketPairQuote}>
                          <div className={marketPairPriceMain}>{item.price}</div>
                          <div className={item.tone === "up" ? marketPairMoveUp : marketPairMoveDown}>
                            {item.move}
                          </div>
                        </div>
                      </div>
                      <div className={marketPairSignal}>{item.signal}</div>
                      <div className={marketPairContext}>
                        <span>{item.spread}</span>
                        <span className={marketPairDetails}>{item.context}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </WidgetShell>
        );

      case "focus-alerts":
        return (
          <WidgetShell
            title="Фокус"
            dragLabel="фокус"
            cardClassName={compactCard}
            contentClassName={`${compactListContent} ${scrollableWidgetContent} terminal-widget-no-drag`}
            isFocused={isFocused}
            onToggleFocus={handleToggleFocus}
            >
              <div className={attentionList}>
                {attentionItems.map((item) => (
                  <div key={item.title} className={attentionItem}>
                    <div className={attentionHeader}>
                      <span
                        className={`${attentionSeverity} ${item.severity === "Высокий" ? attentionSeverityHigh : attentionSeverityMedium}`}
                      >
                        {item.severity}
                      </span>
                      <span className={attentionStatus}>{item.status}</span>
                      <span className={attentionTimestamp}>{item.time}</span>
                    </div>
                    <div className={attentionSummary}>{item.title}</div>
                    <div className={attentionMeta}>{item.meta}</div>
                    <div className={attentionStatus}>{item.scope}</div>
                  </div>
                ))}
              </div>
            </WidgetShell>
        );

      case "trend":
        return (
          <WidgetShell
            title="Тренд"
            dragLabel="тренд"
            cardClassName={compactCard}
            contentClassName={compactStatContent}
            isFocused={isFocused}
            onToggleFocus={handleToggleFocus}
          >
            <div className={chartStat}>
              <span className={chartStatValue}>умеренный рост</span>
            </div>
          </WidgetShell>
        );

      case "volume":
        return (
          <WidgetShell
            title="Объём"
            dragLabel="объём"
            cardClassName={compactCard}
            contentClassName={compactStatContent}
            isFocused={isFocused}
            onToggleFocus={handleToggleFocus}
          >
            <div className={chartStat}>
              <span className={chartStatValue}>выше средней сессии</span>
            </div>
          </WidgetShell>
        );

      case "signal":
        return (
          <WidgetShell
            title="Сигнал"
            dragLabel="сигнал"
            cardClassName={compactCard}
            contentClassName={compactStatContent}
            isFocused={isFocused}
            onToggleFocus={handleToggleFocus}
          >
            <div className={chartStat}>
              <span className={chartStatValue}>наблюдать вход</span>
            </div>
          </WidgetShell>
        );

      case "positions":
        return (
          <WidgetShell
            dragLabel="позиции"
            cardClassName={card}
            contentClassName={`${positionsWidgetContent} ${isPositionActionLayerActive ? positionsWidgetContentExpanded : ""}`}
            frameClassName={isPositionActionLayerActive ? positionsWidgetFrameExpanded : undefined}
            frameStyle={positionActionExpandPx > 0 ? { minHeight: `calc(100% + ${positionActionExpandPx}px)` } : undefined}
            isFocused={isFocused}
            onToggleFocus={handleToggleFocus}
          >
            <div className={positionsWidgetHeader}>
              <div className={positionsWidgetHeaderMain}>
                <span
                  className={`${widgetDragHandle} terminal-widget-drag-handle`}
                  role="button"
                  tabIndex={0}
                  aria-label="Переместить позиции"
                >
                  {Array.from({ length: 9 }).map((_, index) => (
                    <span key={index} className={widgetDragDots} />
                  ))}
                </span>

                <div className={`${positionModeSwitch} terminal-widget-no-drag`}>
                  <button
                    type="button"
                    className={`${positionModeButton} ${positionsView === "open" ? positionModeButtonActive : ""}`}
                    onClick={() => setPositionsView("open")}
                  >
                    Открытые позиции
                  </button>
                  <button
                    type="button"
                    className={`${positionModeButton} ${positionsView === "history" ? positionModeButtonActive : ""}`}
                    onClick={() => setPositionsView("history")}
                  >
                    История позиций
                  </button>
                </div>
              </div>
              <button
                type="button"
                className={`${widgetFocusControl} terminal-widget-no-drag ${isFocused ? widgetFocusControlActive : ""}`}
                aria-label={isFocused ? "Свернуть позиции" : "Вывести поверх позиции"}
                onClick={handleToggleFocus}
              >
                {isFocused ? "×" : "⤢"}
              </button>
            </div>

            <div
              ref={positionsTableViewportRef}
              className={`${positionsTableViewport} ${isPositionActionLayerActive ? positionsTableViewportActionOpen : ""} terminal-widget-no-drag`}
              style={positionActionExpandPx > 0 ? { paddingBottom: `${positionActionExpandPx}px` } : undefined}
            >
              <div className={`${positionsTable} ${isPositionActionLayerActive ? positionsTableActionOpen : ""}`}>
                {positionsView === "history" ? (
                  <div className={`${positionsHistoryControls} terminal-widget-no-drag`}>
                    <input
                      type="text"
                      className={positionsHistorySearchInput}
                      placeholder="Поиск по паре"
                      aria-label="Поиск в истории позиций по паре"
                      name="positions-history-search"
                      value={historyPairQuery}
                      onChange={(event) => setHistoryPairQuery(event.target.value)}
                    />
                    <div className={positionsHistoryControlsGroup}>
                      <select
                        className={positionsHistorySelect}
                        aria-label="Фильтр истории по бирже"
                        name="positions-history-exchange"
                        value={historyExchangeFilter}
                        onChange={(event) => setHistoryExchangeFilter(event.target.value)}
                      >
                        <option value="all">Все биржи</option>
                        {historyExchangeOptions.map((exchange) => (
                          <option key={exchange} value={exchange}>
                            {exchange}
                          </option>
                        ))}
                      </select>
                      <select
                        className={positionsHistorySelect}
                        aria-label="Сортировка истории позиций"
                        name="positions-history-sort"
                        value={historySort}
                        onChange={(event) => setHistorySort(event.target.value as typeof historySort)}
                      >
                        <option value="recent">Сначала новые</option>
                        <option value="result-desc">Лучший результат</option>
                        <option value="result-asc">Худший результат</option>
                      </select>
                    </div>
                  </div>
                ) : null}
                <div className={tableHeader}>
                  <span>Биржа</span>
                  <span>Пара</span>
                  <span>Стратегия</span>
                  <span>Сторона</span>
                  <span>{positionsView === "open" ? "Вход / рынок" : "Вход / выход"}</span>
                  <span>Размер</span>
                  <span>{positionsView === "open" ? "Стоп / риск" : "Закрыта"}</span>
                  <span>Результат</span>
                </div>

                <div className={`${positionsTableBodyViewport} terminal-widget-no-drag`}>
                    {positionsView === "open"
                      ? positions.map((row) => {
                        const rowKey = `${row.exchange}-${row.pair}`;
                        const isActionsOpen = openPositionActionsFor === rowKey;

                        return (
                        <div
                          key={rowKey}
                          className={`${tableRow} ${tableRowInteractive} terminal-widget-no-drag ${positionsSelectedInstrument === row.pair ? tableRowActive : ""}`}
                          role="button"
                          tabIndex={0}
                          aria-label={`Открыть ${row.pair} на главном графике`}
                          onClick={() => handleInstrumentActivate(row.pair, "positions")}
                          onKeyDown={(event) => handleInstrumentKeyDown(event, row.pair, "positions")}
                        >
                        <div className={positionStrategyCell}>
                          <span className={positionPrimaryValue}>{row.exchange}</span>
                        </div>
                        <div className={positionPairCell}>
                          <span className={`${positionPrimaryValue} ${positionsSelectedInstrument === row.pair ? positionInstrumentActive : ""}`}>
                            {row.pair}
                          </span>
                        </div>
                        <div className={positionStrategyCell}>
                          <span className={positionPrimaryValue}>{row.strategy}</span>
                        </div>
                        <div className={tableCell}>
                          <span className={row.side === "LONG" ? positionSideLong : positionSideShort}>
                            {row.side}
                          </span>
                        </div>
                        <div className={positionMetricCell}>
                          <span className={positionPrimaryValue}>{row.entry}</span>
                          <span className={positionSecondaryValue}>рынок {row.last}</span>
                        </div>
                        <div className={positionMetricCell}>
                          <span className={positionPrimaryValue}>{row.size}</span>
                        </div>
                        <div className={positionStatusCell}>
                          <span className={positionStatusValue}>стоп {row.stop}</span>
                          <span className={positionStatusMeta}>{row.risk}</span>
                        </div>
                        <div className={positionActionsCell}>
                          <div className={row.tone === "up" ? positionPnlPositive : positionPnlNegative}>
                            <span className={positionPrimaryValue}>{row.pnl}</span>
                            <span className={positionSecondaryValue}>{row.pnlValue}</span>
                          </div>
                          <div
                            ref={(node) => {
                              positionActionAnchorRefs.current[rowKey] = node;
                            }}
                            className={`${positionActionsAnchor} terminal-widget-no-drag`}
                          >
                            <button
                              type="button"
                              className={`${positionActionsTrigger} terminal-widget-no-drag`}
                              aria-label={`Быстрые действия для ${row.pair}`}
                              aria-haspopup="menu"
                              aria-expanded={isActionsOpen}
                              onClick={(event) => handlePositionActionsToggle(event, rowKey)}
                            >
                              ⋯
                            </button>
                          </div>
                        </div>
                      </div>
                        );
                      })
                      : filteredHistoryRows.map((row) => (
                        <div
                          key={`${row.exchange}-${row.pair}-${row.closedAt}`}
                        className={`${tableRow} ${tableRowInteractive} terminal-widget-no-drag ${positionsSelectedInstrument === row.pair ? tableRowActive : ""}`}
                          role="button"
                          tabIndex={0}
                          aria-label={`Открыть ${row.pair} на главном графике`}
                        onClick={() => handleInstrumentActivate(row.pair, "positions")}
                        onKeyDown={(event) => handleInstrumentKeyDown(event, row.pair, "positions")}
                        >
                        <div className={positionStrategyCell}>
                          <span className={positionPrimaryValue}>{row.exchange}</span>
                        </div>
                        <div className={positionPairCell}>
                          <span className={`${positionPrimaryValue} ${positionsSelectedInstrument === row.pair ? positionInstrumentActive : ""}`}>
                            {row.pair}
                          </span>
                        </div>
                        <div className={positionStrategyCell}>
                          <span className={positionPrimaryValue}>{row.strategy}</span>
                        </div>
                        <div className={tableCell}>
                          <span className={row.side === "LONG" ? positionSideLong : positionSideShort}>
                            {row.side}
                          </span>
                        </div>
                        <div className={positionMetricCell}>
                          <span className={positionPrimaryValue}>{row.entry}</span>
                          <span className={positionSecondaryValue}>выход {row.exit}</span>
                        </div>
                        <div className={positionMetricCell}>
                          <span className={positionPrimaryValue}>{row.size}</span>
                        </div>
                        <div className={positionTimestampCell}>
                          <span className={positionStatusValue}>{row.closedAt}</span>
                          <span className={positionStatusMeta}>зафиксировано</span>
                        </div>
                        <div className={row.tone === "up" ? positionPnlPositive : positionPnlNegative}>
                          <span className={positionPrimaryValue}>{row.result}</span>
                          <span className={positionSecondaryValue}>{row.resultValue}</span>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
              {openPositionActionsFor && openPositionActionRow && positionActionOverlayPosition ? (
                <div
                  className={`${positionActionOverlayLayer} terminal-widget-no-drag`}
                  style={{
                    top: `${positionActionOverlayPosition.top}px`,
                    left: `${positionActionOverlayPosition.left}px`,
                    width: `${positionActionMenuEstimate.width}px`,
                  }}
                >
                  <div
                    ref={positionActionsLayerRef}
                    className={`${positionActionsMenu} terminal-widget-no-drag`}
                    role="menu"
                    aria-label={`Действия для ${openPositionActionRow.pair}`}
                    onClick={(event) => event.stopPropagation()}
                  >
                    {positionQuickActions.map((action) => (
                      <button
                        key={action}
                        type="button"
                        role="menuitem"
                        className={`${positionActionsMenuItem} terminal-widget-no-drag`}
                        onClick={(event) => handlePositionActionSelect(event, openPositionActionsFor, action)}
                      >
                        {action}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {pendingPositionAction && pendingPositionRow && positionActionOverlayPosition ? (
                <div
                  className={`${positionActionOverlayLayer} terminal-widget-no-drag`}
                  style={{
                    top: `${positionActionOverlayPosition.top}px`,
                    left: `${positionActionOverlayPosition.left}px`,
                    width: `${positionActionConfirmEstimate.width}px`,
                  }}
                >
                  <div
                    ref={positionActionsLayerRef}
                    className={`${positionActionPanel} terminal-widget-no-drag`}
                    role="dialog"
                    aria-label={`${positionQuickActionLabels[pendingPositionAction.action]} для ${pendingPositionRow.pair}`}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <div className={positionActionPanelMeta}>
                      <div className={positionActionPanelTitle}>{positionQuickActionLabels[pendingPositionAction.action]}</div>
                      <div className={positionActionPanelText}>
                        {pendingPositionRow.pair} · {pendingPositionRow.exchange} · {pendingPositionRow.side}
                      </div>
                      <div className={positionActionPanelText}>
                        {positionQuickActionDescriptions[pendingPositionAction.action]}
                      </div>
                    </div>
                    <div className={positionActionPanelActions}>
                      <button
                        type="button"
                        className={`${positionActionPanelCancel} terminal-widget-no-drag`}
                        onClick={handlePositionActionCancel}
                      >
                        Отменить
                      </button>
                      <button
                        type="button"
                        className={`${positionActionPanelConfirm} terminal-widget-no-drag`}
                        onClick={handlePositionActionConfirm}
                      >
                        Подтвердить
                      </button>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </WidgetShell>
        );

      default:
        return null;
    }
  };

  return (
    <div className={pageRoot}>
      <div className={widgetCanvas} ref={widgetCanvasRef}>
        <GridLayout
          className="layout"
          width={gridWidth}
          layout={gridLayout}
          cols={widgetGridColumns}
          rowHeight={widgetGridRowHeight}
          margin={widgetGridMargin}
          containerPadding={[0, 0]}
          draggableHandle=".terminal-widget-drag-handle"
          draggableCancel=".terminal-widget-no-drag,button,input,select,textarea,canvas,a"
          resizeHandles={["n", "s", "e", "w", "ne", "nw", "se", "sw"]}
          compactType={null}
          preventCollision
          allowOverlap
          resizeHandle={(axis, ref) => (
            <span
              ref={ref as Ref<HTMLSpanElement>}
              className={`react-resizable-handle react-resizable-handle-${axis} terminal-widget-resize-handle`}
              aria-label={`Изменить размер виджета ${axis}`}
            />
          )}
          onLayoutChange={updateWidgetLayouts}
        >
          {visibleWidgets.map((widget) => (
            <div
              key={widget.id}
              data-widget-id={widget.id}
              className={focusedWidgetId === widget.id ? "terminal-widget-grid-item-focused" : undefined}
            >
              {renderWidget(widget)}
            </div>
          ))}
        </GridLayout>
      </div>
    </div>
  );
}
