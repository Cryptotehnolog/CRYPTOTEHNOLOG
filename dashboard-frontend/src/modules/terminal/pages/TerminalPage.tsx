import { type CSSProperties, type DragEvent as ReactDragEvent, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent, type ReactNode, type Ref, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import GridLayoutBase, { type Layout } from "react-grid-layout/legacy";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { TerminalChartSurface } from "../components/TerminalChartSurface";
import { useOpenPositions } from "../hooks/useOpenPositions";
import { usePositionActionsOverlay } from "../hooks/usePositionActionsOverlay";
import { usePositionHistory } from "../hooks/usePositionHistory";
import { usePositionHistoryViewModel } from "../hooks/usePositionHistoryViewModel";
import {
  getOpenPositionColumnValue,
  getOpenPositionGridTemplate,
  loadPersistedOpenPositionsHomeColumns,
  mapOpenPositionToTerminalRow,
  openPositionColumnLabels,
  openPositionsHomeColumnsStorageKey,
  type OpenPositionColumnKey,
} from "../lib/openPositionsColumns";
import {
  getCompactPositionHistoryGridTemplate,
  getPositionHistoryColumnValue,
  getPositionHistoryGridTemplate,
  loadPersistedPositionHistoryHomeColumns,
  positionHistoryColumnLabels,
  positionHistoryHomeColumnsStorageKey,
  type PositionHistoryColumnKey,
} from "../lib/positionHistoryColumns";
import { useTerminalWidgetStore } from "../state/useTerminalWidgetStore";
import { useTerminalUiStore } from "../state/useTerminalUiStore";
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
  positionsEmptyState,
  positionsEmptyStateCentered,
  positionsTable,
  positionsCompactCenteredSimpleCell,
  positionsCompactCenteredValueCell,
  positionsCompactHeaderDragHandle,
  positionsCompactHeaderDragging,
  positionsCompactHeaderDropTarget,
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
  positionPnlNegativeText,
  positionPnlPositiveText,
  positionPrimaryValue,
  positionSecondaryValue,
  positionStrategyCell,
  positionSideLong,
  positionSideShort,
  positionStatusCell,
  positionStatusMeta,
  positionStatusValue,
  positionsTableViewport,
  positionsTableBodyViewport,
  positionsWidgetContent,
  positionTimestampCell,
  positionsHistoryControls,
  positionsHistoryControlsGroup,
  positionsHistorySearchInput,
  positionsHistorySelect,
  positionsCompactHeaderCell,
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
    pair: "BTC/USDT",
    exchange: "Bybit",
    price: "67 405",
    spread: "спред 5.1",
    signal: "объём держится",
    context: "bid 67 402 · ask 67 407",
    move: "+1.6%",
    tone: "up",
  },
  {
    pair: "BTC/USDT",
    exchange: "Binance",
    price: "67 398",
    spread: "спред 3.9",
    signal: "баланс спроса",
    context: "bid 67 396 · ask 67 400",
    move: "+1.5%",
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

const positionQuickActions = ["закрыть", "перевернуть", "stop-loss", "в безубыток"] as const;
type PositionQuickAction = (typeof positionQuickActions)[number];
type HomeProjectionSurface = "open" | "history";
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

function getInstrumentContextKey(pair: string, exchange: string) {
  return `${exchange}:${pair}`;
}

function getOpenPositionRowKey(positionId: string) {
  return `open-position:${positionId}`;
}

function formatDecimalValue(value: string | number, maximumFractionDigits = 2) {
  const numeric = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }

  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits,
  }).format(numeric);
}

function formatPriceValue(value: string | number) {
  return formatDecimalValue(value, 4);
}

function formatQuantityValue(value: string | number) {
  return formatDecimalValue(value, 8);
}

function formatUsdValue(value: string | number) {
  return `$${formatDecimalValue(value, 2)}`;
}

function formatRiskRValue(value: string | number) {
  return `${formatDecimalValue(value, 2)}R`;
}

function formatPositionTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function formatPositionSideLabel(side: string) {
  return side.trim().toUpperCase() === "SHORT" || side.trim().toLowerCase() === "short" ? "SHORT" : "LONG";
}

function formatTrailingStateLabel(state: string) {
  const normalized = state.trim().toLowerCase();

  switch (normalized) {
    case "armed":
      return "armed";
    case "active":
      return "active";
    case "emergency":
      return "emergency";
    case "terminated":
      return "terminated";
    default:
      return "inactive";
  }
}

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
  const [activeExchange, setActiveExchange] = useState("OKX");
  const [marketSelectedInstrument, setMarketSelectedInstrument] = useState<string | null>(
    getInstrumentContextKey("BTC/USDT", "OKX"),
  );
  const [positionsSelectedInstrument, setPositionsSelectedInstrument] = useState<string | null>(null);
  const [positionsView, setPositionsView] = useState<"open" | "history">("open");
  const [historyPairQuery, setHistoryPairQuery] = useState("");
  const [historyExchangeFilter, setHistoryExchangeFilter] = useState("all");
  const [historyStrategyFilter, setHistoryStrategyFilter] = useState("all");
  const [historySort, setHistorySort] = useState<"recent" | "result-desc" | "result-asc">("recent");
  const [focusedWidgetId, setFocusedWidgetId] = useState<TerminalWidgetId | null>(null);
  const [isTimeframeMenuOpen, setIsTimeframeMenuOpen] = useState(false);
  const [customTimeframeUnit, setCustomTimeframeUnit] = useState("m");
  const [customTimeframeValue, setCustomTimeframeValue] = useState("2");
  const [gridWidth, setGridWidth] = useState(1200);
  const [homeProjectionColumns, setHomeProjectionColumns] = useState<OpenPositionColumnKey[]>(
    () => loadPersistedOpenPositionsHomeColumns(),
  );
  const [historyHomeProjectionColumns, setHistoryHomeProjectionColumns] = useState<
    PositionHistoryColumnKey[]
  >(() => loadPersistedPositionHistoryHomeColumns());
  const [draggedHomeColumn, setDraggedHomeColumn] = useState<{
    surface: HomeProjectionSurface;
    key: OpenPositionColumnKey | PositionHistoryColumnKey;
  } | null>(null);
  const [homeDropColumn, setHomeDropColumn] = useState<{
    surface: HomeProjectionSurface;
    key: OpenPositionColumnKey | PositionHistoryColumnKey;
  } | null>(null);
  const timeframeMenuRef = useRef<HTMLDivElement | null>(null);
  const widgetCanvasRef = useRef<HTMLDivElement | null>(null);
  const openPositionsQuery = useOpenPositions();
  const positionHistoryQuery = usePositionHistory();
  const terminalExchanges = useTerminalUiStore((state) => state.exchanges);

  const openPositionsRows =
    openPositionsQuery.data?.positions.map(mapOpenPositionToTerminalRow) ?? [];
  const {
    rows: historyRows,
    exchangeOptions: historyExchangeOptions,
    strategyOptions: historyStrategyOptions,
  } =
    usePositionHistoryViewModel({
      data: positionHistoryQuery.data,
      pairQuery: historyPairQuery,
      exchangeFilter: historyExchangeFilter,
      strategyFilter: historyStrategyFilter,
      sortMode: historySort,
      terminalExchanges,
    });
  const compactOpenPositionsGridTemplate = getOpenPositionGridTemplate(homeProjectionColumns, true);
  const compactHistoryGridTemplate = useMemo(
    () => getCompactPositionHistoryGridTemplate(historyHomeProjectionColumns),
    [historyHomeProjectionColumns],
  );
  const hasOpenPositionRowKey = useMemo(
    () => (rowKey: string) =>
      openPositionsRows.some((row) => getOpenPositionRowKey(row.positionId) === rowKey),
    [openPositionsRows],
  );
  const {
    openPositionActionsFor,
    pendingPositionAction,
    positionActionOverlayPosition,
    positionActionsLayerRef,
    positionActionAnchorRefs,
    clearPositionActions,
    handlePositionActionsToggle,
    handlePositionActionSelect,
    handlePositionActionCancel,
    handlePositionActionConfirm,
  } = usePositionActionsOverlay<PositionQuickAction>({
    hasRowKey: hasOpenPositionRowKey,
    menuEstimate: positionActionMenuEstimate,
    confirmEstimate: positionActionConfirmEstimate,
  });

  const marketContext =
    marketWatch.find((item) => item.pair === activeInstrument && item.exchange === activeExchange) ??
    {
      pair: activeInstrument,
      exchange: activeExchange,
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
    if (positionsView === "history") {
      clearPositionActions();
    }
  }, [clearPositionActions, positionsView]);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (!event.key || event.key === openPositionsHomeColumnsStorageKey) {
        setHomeProjectionColumns(loadPersistedOpenPositionsHomeColumns());
      }

      if (!event.key || event.key === positionHistoryHomeColumnsStorageKey) {
        setHistoryHomeProjectionColumns(loadPersistedPositionHistoryHomeColumns());
      }
    };

    window.addEventListener("storage", handleStorage);

    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

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
  const visibleToolbarTimeframes = orderedSelectedTimeframes;
  const openPositionActionRow = openPositionActionsFor
    ? openPositionsRows.find((row) => getOpenPositionRowKey(row.positionId) === openPositionActionsFor) ?? null
    : null;
  const pendingPositionRow = pendingPositionAction
    ? openPositionsRows.find((row) => getOpenPositionRowKey(row.positionId) === pendingPositionAction.rowKey) ?? null
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

  const handleInstrumentActivate = (pair: string, exchange: string, source: "market" | "positions") => {
    setActiveInstrument(pair);
    setActiveExchange(exchange);
    if (source === "market") {
      setMarketSelectedInstrument(getInstrumentContextKey(pair, exchange));
      setPositionsSelectedInstrument(null);
      return;
    }

    setPositionsSelectedInstrument(getInstrumentContextKey(pair, exchange));
    setMarketSelectedInstrument(null);
  };

  const handleOpenPositionActivate = (positionId: string, pair: string) => {
    setActiveInstrument(pair);
    setPositionsSelectedInstrument(getOpenPositionRowKey(positionId));
    setMarketSelectedInstrument(null);
  };

  const handleInstrumentKeyDown = (
    event: ReactKeyboardEvent<HTMLElement>,
    pair: string,
    exchange: string,
    source: "market" | "positions",
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleInstrumentActivate(pair, exchange, source);
    }
  };

  const reorderColumns = <TColumnKey extends string>(
    columns: TColumnKey[],
    sourceKey: TColumnKey,
    targetKey: TColumnKey,
  ) => {
    if (sourceKey === targetKey) {
      return columns;
    }

    const sourceIndex = columns.indexOf(sourceKey);
    const targetIndex = columns.indexOf(targetKey);

    if (sourceIndex === -1 || targetIndex === -1) {
      return columns;
    }

    const next = [...columns];
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, moved);
    return next;
  };

  const handleHomeColumnDragStart = (
    event: ReactDragEvent<HTMLElement>,
    surface: HomeProjectionSurface,
    key: OpenPositionColumnKey | PositionHistoryColumnKey,
  ) => {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", `${surface}:${key}`);
    setDraggedHomeColumn({ surface, key });
    setHomeDropColumn(null);
  };

  const handleHomeColumnDragEnter = (
    surface: HomeProjectionSurface,
    key: OpenPositionColumnKey | PositionHistoryColumnKey,
  ) => {
    if (!draggedHomeColumn || draggedHomeColumn.surface !== surface || draggedHomeColumn.key === key) {
      return;
    }

    setHomeDropColumn({ surface, key });
  };

  const handleHomeColumnDragEnd = () => {
    setDraggedHomeColumn(null);
    setHomeDropColumn(null);
  };

  const handleOpenHomeColumnDrop = (targetKey: OpenPositionColumnKey) => {
    if (!draggedHomeColumn || draggedHomeColumn.surface !== "open") {
      return;
    }

    setHomeProjectionColumns((current) =>
      reorderColumns(current, draggedHomeColumn.key as OpenPositionColumnKey, targetKey),
    );
    setDraggedHomeColumn(null);
    setHomeDropColumn(null);
  };

  const handleHistoryHomeColumnDrop = (targetKey: PositionHistoryColumnKey) => {
    if (!draggedHomeColumn || draggedHomeColumn.surface !== "history") {
      return;
    }

    setHistoryHomeProjectionColumns((current) =>
      reorderColumns(current, draggedHomeColumn.key as PositionHistoryColumnKey, targetKey),
    );
    setDraggedHomeColumn(null);
    setHomeDropColumn(null);
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
                exchange={marketContext.exchange}
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
                    key={getInstrumentContextKey(item.pair, item.exchange)}
                    className={`${marketPair} terminal-widget-no-drag ${marketSelectedInstrument === getInstrumentContextKey(item.pair, item.exchange) ? marketPairActive : ""}`}
                    role="button"
                    tabIndex={0}
                    aria-label={`Открыть ${item.pair} ${item.exchange} на главном графике`}
                    onClick={() => handleInstrumentActivate(item.pair, item.exchange, "market")}
                    onKeyDown={(event) => handleInstrumentKeyDown(event, item.pair, item.exchange, "market")}
                  >
                    <div className={marketPairBody}>
                      <div className={marketPairHeader}>
                        <div className={marketPairMain}>
                          <span className={marketSelectedInstrument === getInstrumentContextKey(item.pair, item.exchange) ? positionInstrumentActive : marketPairPrice}>
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
            contentClassName={positionsWidgetContent}
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
              className={`${positionsTableViewport} terminal-widget-no-drag`}
            >
              <div className={positionsTable}>
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
                        aria-label="Фильтр истории позиций по бирже"
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
                        aria-label="Фильтр истории позиций по стратегии"
                        name="history-strategy"
                        value={historyStrategyFilter}
                        onChange={(event) => setHistoryStrategyFilter(event.target.value)}
                      >
                        <option value="all">Все стратегии</option>
                        {historyStrategyOptions.map((strategy) => (
                          <option key={strategy} value={strategy.toLowerCase()}>
                            {strategy}
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
                <div
                  className={tableHeader}
                  style={{
                    gridTemplateColumns:
                      positionsView === "open"
                        ? compactOpenPositionsGridTemplate
                        : compactHistoryGridTemplate,
                  }}
                >
                  {positionsView === "open" ? (
                    <>
                      {homeProjectionColumns.map((columnKey) => (
                        <span key={columnKey} className={positionsCompactHeaderCell}>
                          <span
                            className={`${positionsCompactHeaderDragHandle} ${
                              draggedHomeColumn?.surface === "open" &&
                              draggedHomeColumn.key === columnKey
                                ? positionsCompactHeaderDragging
                                : ""
                            } ${
                              homeDropColumn?.surface === "open" &&
                              homeDropColumn.key === columnKey
                                ? positionsCompactHeaderDropTarget
                                : ""
                            }`}
                            draggable
                            aria-label={`Перетащить колонку ${openPositionColumnLabels[columnKey]}`}
                            aria-grabbed={
                              draggedHomeColumn?.surface === "open" &&
                              draggedHomeColumn.key === columnKey
                            }
                            onDragStart={(event) => handleHomeColumnDragStart(event, "open", columnKey)}
                            onDragEnter={() => handleHomeColumnDragEnter("open", columnKey)}
                            onDragOver={(event) => event.preventDefault()}
                            onDrop={(event) => {
                              event.preventDefault();
                              handleOpenHomeColumnDrop(columnKey);
                            }}
                            onDragEnd={handleHomeColumnDragEnd}
                          >
                            {openPositionColumnLabels[columnKey]}
                          </span>
                        </span>
                      ))}
                      <span className={positionsCompactHeaderCell}>Действия</span>
                    </>
                  ) : (
                    <>
                      {historyHomeProjectionColumns.map((columnKey) => (
                        <span key={columnKey} className={positionsCompactHeaderCell}>
                          <span
                            className={`${positionsCompactHeaderDragHandle} ${
                              draggedHomeColumn?.surface === "history" &&
                              draggedHomeColumn.key === columnKey
                                ? positionsCompactHeaderDragging
                                : ""
                            } ${
                              homeDropColumn?.surface === "history" &&
                              homeDropColumn.key === columnKey
                                ? positionsCompactHeaderDropTarget
                                : ""
                            }`}
                            draggable
                            aria-label={`Перетащить колонку ${positionHistoryColumnLabels[columnKey]}`}
                            aria-grabbed={
                              draggedHomeColumn?.surface === "history" &&
                              draggedHomeColumn.key === columnKey
                            }
                            onDragStart={(event) => handleHomeColumnDragStart(event, "history", columnKey)}
                            onDragEnter={() => handleHomeColumnDragEnter("history", columnKey)}
                            onDragOver={(event) => event.preventDefault()}
                            onDrop={(event) => {
                              event.preventDefault();
                              handleHistoryHomeColumnDrop(columnKey);
                            }}
                            onDragEnd={handleHomeColumnDragEnd}
                          >
                            {positionHistoryColumnLabels[columnKey]}
                          </span>
                        </span>
                      ))}
                    </>
                  )}
                </div>

                <div className={`${positionsTableBodyViewport} terminal-widget-no-drag`}>
                    {positionsView === "open"
                      ? openPositionsQuery.isLoading ? (
                        <div className={`${positionsEmptyState} ${positionsEmptyStateCentered}`}>
                          <span className={positionPrimaryValue}>Открытые позиции загружаются</span>
                        </div>
                      ) : openPositionsQuery.isError ? (
                        <div className={`${positionsEmptyState} ${positionsEmptyStateCentered}`}>
                          <span className={positionPrimaryValue}>Ошибка: открытые позиции недоступны</span>
                        </div>
                      ) : openPositionsRows.length === 0 ? (
                        <div className={`${positionsEmptyState} ${positionsEmptyStateCentered}`}>
                          <span className={positionPrimaryValue}>Открытых позиций нет</span>
                        </div>
                      ) : openPositionsRows.map((row) => {
                        const rowKey = getOpenPositionRowKey(row.positionId);
                        const isActionsOpen = openPositionActionsFor === rowKey;

                        return (
                          <div
                            key={row.positionId}
                            className={`${tableRow} ${tableRowInteractive} terminal-widget-no-drag ${positionsSelectedInstrument === rowKey ? tableRowActive : ""}`}
                            style={{ gridTemplateColumns: compactOpenPositionsGridTemplate }}
                            role="button"
                            tabIndex={0}
                            aria-label={`Открыть ${row.symbol} на главном графике`}
                            onClick={() => handleOpenPositionActivate(row.positionId, row.symbol)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                handleOpenPositionActivate(row.positionId, row.symbol);
                              }
                            }}
                          >
                            {homeProjectionColumns.map((columnKey) => {
                              const cell = getOpenPositionColumnValue(row, columnKey);

                              if (columnKey === "instrument") {
                                return (
                                  <div key={columnKey} className={positionPairCell}>
                                    <span className={`${positionPrimaryValue} ${positionsSelectedInstrument === rowKey ? positionInstrumentActive : ""}`}>
                                      {cell.primary}
                                    </span>
                                    {cell.secondary ? (
                                      <span className={positionSecondaryValue}>{cell.secondary}</span>
                                    ) : null}
                                  </div>
                                );
                              }

                              if (columnKey === "direction") {
                                return (
                                  <div key={columnKey} className={`${tableCell} ${positionsCompactCenteredSimpleCell}`}>
                                    <span className={row.sideLabel === "LONG" ? positionSideLong : positionSideShort}>
                                      {cell.primary}
                                    </span>
                                  </div>
                                );
                              }

                              const metricCellClassName =
                                columnKey === "entry" ||
                                columnKey === "current_price" ||
                                columnKey === "size" ||
                                columnKey === "initial_stop" ||
                                columnKey === "current_stop"
                                  ? positionMetricCell
                                  : positionStatusCell;
                              const pnlTextClassName =
                                columnKey === "pnl_usd"
                                  ? row.unrealizedPnlUsdRaw === null
                                    ? undefined
                                    : row.unrealizedPnlUsdRaw > 0
                                      ? positionPnlPositiveText
                                      : row.unrealizedPnlUsdRaw < 0
                                        ? positionPnlNegativeText
                                        : undefined
                                  : columnKey === "pnl_percent"
                                    ? row.unrealizedPnlPercentRaw === null
                                      ? undefined
                                      : row.unrealizedPnlPercentRaw > 0
                                        ? positionPnlPositiveText
                                        : row.unrealizedPnlPercentRaw < 0
                                          ? positionPnlNegativeText
                                          : undefined
                                    : undefined;

                              return (
                                <div key={columnKey} className={`${metricCellClassName} ${positionsCompactCenteredValueCell}`}>
                                  <span className={`${positionStatusValue} ${pnlTextClassName ?? ""}`}>{cell.primary}</span>
                                  {cell.secondary ? (
                                    <span className={positionStatusMeta}>{cell.secondary}</span>
                                  ) : null}
                                </div>
                              );
                            })}
                            <div className={positionActionsCell}>
                              <div
                                ref={(node) => {
                                  positionActionAnchorRefs.current[rowKey] = node;
                                }}
                                className={`${positionActionsAnchor} terminal-widget-no-drag`}
                                data-position-actions-anchor="true"
                              >
                                <button
                                  type="button"
                                  className={`${positionActionsTrigger} terminal-widget-no-drag`}
                                  aria-label={`Действия пока недоступны для ${row.symbol}`}
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
                      : positionHistoryQuery.isLoading ? (
                        <div className={`${positionsEmptyState} ${positionsEmptyStateCentered}`}>
                          <span className={positionPrimaryValue}>История позиций загружается</span>
                        </div>
                      ) : positionHistoryQuery.isError ? (
                        <div className={`${positionsEmptyState} ${positionsEmptyStateCentered}`}>
                          <span className={positionPrimaryValue}>Ошибка: история позиций недоступна</span>
                        </div>
                      ) : historyRows.length === 0 ? (
                        <div className={`${positionsEmptyState} ${positionsEmptyStateCentered}`}>
                          <span className={positionPrimaryValue}>Истории позиций нет</span>
                        </div>
                      ) : historyRows.map((row) => (
                        <div
                          key={row.positionId}
                          className={`${tableRow} terminal-widget-no-drag`}
                          style={{ gridTemplateColumns: compactHistoryGridTemplate }}
                        >
                          {historyHomeProjectionColumns.map((columnKey) => {
                            const cell = getPositionHistoryColumnValue(row, columnKey);

                            if (columnKey === "instrument") {
                              return (
                                <div key={columnKey} className={positionPairCell}>
                                  <span className={positionPrimaryValue}>{cell.primary}</span>
                                  {cell.secondary ? (
                                    <span className={positionSecondaryValue}>{cell.secondary}</span>
                                  ) : null}
                                </div>
                              );
                            }

                            if (columnKey === "direction") {
                              return (
                                <div key={columnKey} className={`${tableCell} ${positionsCompactCenteredSimpleCell}`}>
                                  <span className={row.sideLabel === "LONG" ? positionSideLong : positionSideShort}>
                                    {cell.primary}
                                  </span>
                                </div>
                              );
                            }

                            if (columnKey === "result_r") {
                              return (
                                <div
                                  key={columnKey}
                                  className={`${positionStatusCell} ${positionsCompactCenteredValueCell}`}
                                >
                                  <span className={positionStatusValue}>{cell.primary}</span>
                                </div>
                              );
                            }

                            if (columnKey === "result_usd" || columnKey === "result_percent") {
                              const pnlRawValue =
                                columnKey === "result_usd"
                                  ? row.realizedPnlUsdRaw
                                  : row.realizedPnlPercentRaw;
                              const pnlTextClassName =
                                pnlRawValue === null
                                  ? undefined
                                  : pnlRawValue > 0
                                    ? positionPnlPositiveText
                                    : pnlRawValue < 0
                                      ? positionPnlNegativeText
                                      : undefined;

                              return (
                                <div
                                  key={columnKey}
                                  className={`${positionStatusCell} ${positionsCompactCenteredValueCell}`}
                                >
                                  <span
                                    className={`${positionStatusValue} ${pnlTextClassName ?? ""}`}
                                  >
                                    {cell.primary}
                                  </span>
                                </div>
                              );
                            }

                            const metricCellClassName =
                              columnKey === "entry" ||
                              columnKey === "exit" ||
                              columnKey === "size" ||
                              columnKey === "initial_stop" ||
                              columnKey === "exit_stop"
                                ? positionMetricCell
                                : positionStatusCell;

                            return (
                              <div key={columnKey} className={`${metricCellClassName} ${positionsCompactCenteredValueCell}`}>
                                <span className={positionStatusValue}>{cell.primary}</span>
                                {cell.secondary ? (
                                  <span className={positionStatusMeta}>{cell.secondary}</span>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      ))}
                </div>
              </div>
            </div>
            {typeof document !== "undefined" &&
            positionActionOverlayPosition &&
            openPositionActionRow
              ? createPortal(
                  <div
                    ref={positionActionsLayerRef}
                    className={`${positionActionOverlayLayer} terminal-widget-no-drag`}
                    style={{
                      top: `${positionActionOverlayPosition.top}px`,
                      left: `${positionActionOverlayPosition.left}px`,
                      width: `${positionActionMenuEstimate.width}px`,
                    }}
                    role="menu"
                    aria-label={`Действия для ${openPositionActionRow.symbol}`}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <div className={`${positionActionsMenu} terminal-widget-no-drag`}>
                      {positionQuickActions.map((action) => (
                        <button
                          key={action}
                          type="button"
                          role="menuitem"
                          className={`${positionActionsMenuItem} terminal-widget-no-drag`}
                          onClick={(event) =>
                            handlePositionActionSelect(
                              event,
                              getOpenPositionRowKey(openPositionActionRow.positionId),
                              action,
                            )
                          }
                        >
                          {action}
                        </button>
                      ))}
                    </div>
                  </div>,
                  document.body,
                )
              : null}
            {typeof document !== "undefined" &&
            positionActionOverlayPosition &&
            pendingPositionRow &&
            pendingPositionAction
              ? createPortal(
                  <div
                    ref={positionActionsLayerRef}
                    className={`${positionActionOverlayLayer} terminal-widget-no-drag`}
                    style={{
                      top: `${positionActionOverlayPosition.top}px`,
                      left: `${positionActionOverlayPosition.left}px`,
                      width: `${positionActionConfirmEstimate.width}px`,
                    }}
                    role="dialog"
                    aria-label={`${positionQuickActionLabels[pendingPositionAction.action]} для ${pendingPositionRow.symbol}`}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <div className={`${positionActionPanel} terminal-widget-no-drag`}>
                      <div className={positionActionPanelMeta}>
                        <div className={positionActionPanelTitle}>
                          {positionQuickActionLabels[pendingPositionAction.action]}
                        </div>
                        <div className={positionActionPanelText}>
                          {pendingPositionRow.symbol} · {pendingPositionRow.sideLabel}
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
                  </div>,
                  document.body,
                )
              : null}
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
