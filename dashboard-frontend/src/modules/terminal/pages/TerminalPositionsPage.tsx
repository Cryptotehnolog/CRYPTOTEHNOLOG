import { type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
  type SortingFn,
  type SortingState,
} from "@tanstack/react-table";

import { useOpenPositions } from "../hooks/useOpenPositions";
import { usePositionActionsOverlay } from "../hooks/usePositionActionsOverlay";
import { useHomeProjectionColumns } from "../hooks/useHomeProjectionColumns";
import { usePositionHistory } from "../hooks/usePositionHistory";
import { usePositionHistoryViewModel } from "../hooks/usePositionHistoryViewModel";
import { useTerminalUiStore } from "../state/useTerminalUiStore";
import {
  defaultOpenPositionsHomeColumns,
  getOpenPositionColumnValue,
  getOpenPositionRowKey,
  loadPersistedOpenPositionsHomeColumns,
  lockedOpenPositionColumnKeys,
  mapOpenPositionToTerminalRow,
  openPositionColumnLabels,
  openPositionColumnOrder,
  openPositionsHomeColumnsStorageKey,
  sanitizeOpenPositionsHomeColumns,
  type OpenPositionColumnKey,
} from "../lib/openPositionsColumns";
import {
  getPositionHistoryColumnValue,
  loadPersistedPositionHistoryHomeColumns,
  lockedPositionHistoryColumnKeys,
  mapPositionHistoryToTerminalRow,
  positionHistoryColumnLabels,
  positionHistoryColumnOrder,
  positionHistoryHomeColumnsStorageKey,
  sanitizePositionHistoryHomeColumns,
  type PositionHistoryColumnKey,
} from "../lib/positionHistoryColumns";
import {
  card,
  positionActionPanel,
  positionActionPanelActions,
  positionActionPanelCancel,
  positionActionPanelConfirm,
  positionActionPanelMeta,
  positionActionPanelText,
  positionActionPanelTitle,
  positionActionsMenu,
  positionActionsMenuItem,
  positionActionOverlayLayer,
  positionActionsAnchor,
  positionActionsCell,
  positionActionsTrigger,
  positionMetricCell,
  positionModeButton,
  positionModeButtonActive,
  positionModeSwitch,
  positionPnlNegativeText,
  positionPnlPositiveText,
  positionPairCell,
  positionPrimaryValue,
  positionSecondaryValue,
  positionSideLong,
  positionSideShort,
  positionStatusCell,
  positionStatusMeta,
  positionStatusValue,
  positionTimestampCell,
  positionsEmptyState,
  positionsHistoryControls,
  positionsHistorySearchInput,
  positionsHistorySelect,
  positionsTable,
  positionsTableBodyViewport,
  positionsWidgetContent,
  positionsWidgetHeader,
  positionsWidgetHeaderMain,
  tableCell,
  tableHeader,
  tableRow,
  tableRowActive,
  tableRowInteractive,
} from "./TerminalPage.css";
import {
  positionsHeaderCell,
  positionsHeaderCellCentered,
  positionsHeaderContentCentered,
  positionsPageHeader,
  positionsPageCenteredSimpleCell,
  positionsPageCenteredValueCell,
  positionsPageEmptyState,
  positionsPageRoot,
  positionsPageSection,
  positionsPageInteractiveRow,
  positionsPageTableRow,
  positionsPageTitle,
  positionsHeaderStaticLabel,
  positionsHeaderToggle,
  positionsHeaderToggleActive,
  positionsHeaderToggleInactive,
  positionsHeaderToggleLocked,
  positionsPageControlsCluster,
  positionsPageControlsRow,
  positionsPageSearchCompact,
  positionsPageWideTable,
  positionsPageWideViewport,
} from "./TerminalPositionsPage.css";

const positionQuickActions = ["закрыть", "перевернуть", "stop-loss", "в безубыток"] as const;
type PositionQuickAction = (typeof positionQuickActions)[number];

const positionQuickActionLabels: Record<PositionQuickAction, string> = {
  "закрыть": "Закрыть позицию",
  "перевернуть": "Перевернуть позицию",
  "stop-loss": "Обновить stop-loss",
  "в безубыток": "Перевести в безубыток",
};

const positionQuickActionDescriptions: Record<PositionQuickAction, string> = {
  "закрыть": "Действие пока недоступно.",
  "перевернуть": "Действие пока недоступно.",
  "stop-loss": "Действие пока недоступно.",
  "в безубыток": "Действие пока недоступно.",
};

const positionActionMenuEstimate = { width: 156, height: 156 };
const positionActionConfirmEstimate = { width: 260, height: 164 };

const openColumnHelper = createColumnHelper<ReturnType<typeof mapOpenPositionToTerminalRow>>();
const historyColumnHelper = createColumnHelper<ReturnType<typeof mapPositionHistoryToTerminalRow>>();

const isoDateSortingFn: SortingFn<ReturnType<typeof mapPositionHistoryToTerminalRow>> = (
  left,
  right,
  columnId,
) => {
  const leftValue = Date.parse(String(left.getValue(columnId) ?? ""));
  const rightValue = Date.parse(String(right.getValue(columnId) ?? ""));

  if (Number.isNaN(leftValue) && Number.isNaN(rightValue)) {
    return 0;
  }
  if (Number.isNaN(leftValue)) {
    return 1;
  }
  if (Number.isNaN(rightValue)) {
    return -1;
  }
  return leftValue - rightValue;
};

const nullableNumberSortingFn: SortingFn<ReturnType<typeof mapPositionHistoryToTerminalRow>> = (
  left,
  right,
  columnId,
) => {
  const leftValue = left.getValue<number | null>(columnId);
  const rightValue = right.getValue<number | null>(columnId);

  if (leftValue === null && rightValue === null) {
    return 0;
  }
  if (leftValue === null) {
    return 1;
  }
  if (rightValue === null) {
    return -1;
  }
  return leftValue - rightValue;
};

function buildGridTemplate<TData>(columns: Array<ColumnDef<TData, any>>) {
  return columns
    .map((column) => {
      const meta = column.meta as { grid?: string } | undefined;
      return meta?.grid ?? "minmax(112px, 0.8fr)";
    })
    .join(" ");
}

function getFullOpenGridTemplate() {
  return [
    "minmax(180px, 1fr)",
    "minmax(108px, 0.72fr)",
    "minmax(108px, 0.72fr)",
    "minmax(118px, 0.8fr)",
    "minmax(118px, 0.8fr)",
    "minmax(118px, 0.8fr)",
    "minmax(128px, 0.86fr)",
    "minmax(128px, 0.86fr)",
    "minmax(108px, 0.72fr)",
    "minmax(118px, 0.8fr)",
    "minmax(96px, 0.7fr)",
    "minmax(118px, 0.8fr)",
    "minmax(96px, 0.7fr)",
    "minmax(136px, 0.9fr)",
    "minmax(136px, 0.9fr)",
    "minmax(108px, 0.72fr)",
    "minmax(88px, 0.64fr)",
  ].join(" ");
}

function getFullHistoryGridTemplate() {
  return [
    "minmax(180px, 1fr)",
    "minmax(108px, 0.72fr)",
    "minmax(108px, 0.72fr)",
    "minmax(118px, 0.8fr)",
    "minmax(118px, 0.8fr)",
    "minmax(128px, 0.86fr)",
    "minmax(128px, 0.86fr)",
    "minmax(108px, 0.72fr)",
    "minmax(108px, 0.72fr)",
    "minmax(136px, 0.9fr)",
    "minmax(136px, 0.9fr)",
    "minmax(108px, 0.72fr)",
  ].join(" ");
}

function formatRelativeAge(value: string) {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return "—";
  }

  const deltaMinutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  const days = Math.floor(deltaMinutes / 1440);
  const hours = Math.floor((deltaMinutes % 1440) / 60);
  const minutes = deltaMinutes % 60;

  if (days > 0) {
    return `${days}д ${hours}ч`;
  }

  if (hours > 0) {
    return `${hours}ч ${minutes}м`;
  }

  return `${minutes}м`;
}

function formatDurationBetween(start: string, end: string) {
  const startTime = Date.parse(start);
  const endTime = Date.parse(end);
  if (Number.isNaN(startTime) || Number.isNaN(endTime) || endTime < startTime) {
    return "—";
  }

  const deltaMinutes = Math.floor((endTime - startTime) / 60000);
  const days = Math.floor(deltaMinutes / 1440);
  const hours = Math.floor((deltaMinutes % 1440) / 60);
  const minutes = deltaMinutes % 60;

  if (days > 0) {
    return `${days}д ${hours}ч`;
  }

  if (hours > 0) {
    return `${hours}ч ${minutes}м`;
  }

  return `${minutes}м`;
}

function joinClassNames(...classNames: Array<string | false | null | undefined>) {
  return classNames.filter(Boolean).join(" ");
}

function isOpenColumnCentered(columnId: string) {
  return columnId !== "actions";
}

function isHistoryColumnCentered(_columnId: string) {
  return true;
}

export function TerminalPositionsPage() {
  const [positionsView, setPositionsView] = useState<"open" | "history">("open");
  const [selectedRowKey, setSelectedRowKey] = useState<string | null>(null);
  const [historyPairQuery, setHistoryPairQuery] = useState("");
  const [historyExchangeFilter, setHistoryExchangeFilter] = useState("all");
  const [historyStrategyFilter, setHistoryStrategyFilter] = useState("all");
  const [historySort, setHistorySort] = useState<"recent" | "result-desc" | "result-asc">(
    "recent",
  );
  const openPositionsQuery = useOpenPositions();
  const positionHistoryQuery = usePositionHistory();
  const terminalExchanges = useTerminalUiStore((state) => state.exchanges);
  const {
    columns: homeProjectionColumns,
    toggleColumn: toggleHomeProjectionColumn,
    isSelected: isOpenProjectionColumnSelected,
  } = useHomeProjectionColumns<OpenPositionColumnKey>({
    loadPersisted: loadPersistedOpenPositionsHomeColumns,
    sanitize: sanitizeOpenPositionsHomeColumns,
    storageKey: openPositionsHomeColumnsStorageKey,
    lockedKeys: lockedOpenPositionColumnKeys,
  });
  const {
    columns: historyHomeProjectionColumns,
    toggleColumn: toggleHistoryProjectionColumn,
    isSelected: isHistoryProjectionColumnSelected,
  } = useHomeProjectionColumns<PositionHistoryColumnKey>({
    loadPersisted: loadPersistedPositionHistoryHomeColumns,
    sanitize: sanitizePositionHistoryHomeColumns,
    storageKey: positionHistoryHomeColumnsStorageKey,
    lockedKeys: lockedPositionHistoryColumnKeys,
  });

  const openPositionsRows = useMemo(
    () => openPositionsQuery.data?.positions.map(mapOpenPositionToTerminalRow) ?? [],
    [openPositionsQuery.data?.positions],
  );
  const {
    rows: positionHistoryRows,
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

  const openColumns = useMemo(
    () => [
      openColumnHelper.accessor("symbol", {
        id: "instrument",
        header: openPositionColumnLabels.instrument,
        meta: { grid: "minmax(200px, 1fr)" },
        cell: ({ row }) => (
          <div className={positionPairCell}>
            <span className={positionPrimaryValue}>{row.original.symbol}</span>
            <span className={positionSecondaryValue}>
              {row.original.strategy ?? `id ${row.original.positionId}`}
            </span>
          </div>
        ),
      }),
      openColumnHelper.accessor("exchange", {
        id: "exchange",
        header: openPositionColumnLabels.exchange,
        meta: { grid: "minmax(96px, 0.72fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.exchange}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("sideLabel", {
        id: "direction",
        header: openPositionColumnLabels.direction,
        meta: { grid: "minmax(96px, 0.72fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(tableCell, positionsPageCenteredSimpleCell)}>
            <span className={row.original.sideLabel === "LONG" ? positionSideLong : positionSideShort}>
              {row.original.sideLabel}
            </span>
          </div>
        ),
      }),
      openColumnHelper.accessor("entryPrice", {
        id: "entry",
        header: openPositionColumnLabels.entry,
        meta: { grid: "minmax(120px, 0.82fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.entryPrice}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("currentPrice", {
        id: "current_price",
        header: openPositionColumnLabels.current_price,
        meta: { grid: "minmax(120px, 0.82fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.currentPrice}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("quantity", {
        id: "size",
        header: openPositionColumnLabels.size,
        meta: { grid: "minmax(112px, 0.8fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.quantity}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("initialStop", {
        id: "initial_stop",
        header: openPositionColumnLabels.initial_stop,
        meta: { grid: "minmax(124px, 0.86fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.initialStop}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("currentStop", {
        id: "current_stop",
        header: openPositionColumnLabels.current_stop,
        meta: { grid: "minmax(124px, 0.86fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.currentStop}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("trailingState", {
        id: "trailing",
        header: openPositionColumnLabels.trailing,
        meta: { grid: "minmax(96px, 0.72fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.trailingState}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("currentRiskUsd", {
        id: "risk_usd",
        header: openPositionColumnLabels.risk_usd,
        meta: { grid: "minmax(112px, 0.8fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.currentRiskUsd}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("currentRiskR", {
        id: "risk_r",
        header: openPositionColumnLabels.risk_r,
        meta: { grid: "minmax(88px, 0.68fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.currentRiskR}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("unrealizedPnlUsd", {
        id: "pnl_usd",
        header: openPositionColumnLabels.pnl_usd,
        meta: { grid: "minmax(120px, 0.82fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span
              className={joinClassNames(
                positionStatusValue,
                row.original.unrealizedPnlUsdRaw === null
                  ? undefined
                  : row.original.unrealizedPnlUsdRaw > 0
                  ? positionPnlPositiveText
                  : row.original.unrealizedPnlUsdRaw < 0
                    ? positionPnlNegativeText
                    : undefined,
              )}
            >
              {row.original.unrealizedPnlUsd}
            </span>
          </div>
        ),
      }),
      openColumnHelper.accessor("unrealizedPnlPercent", {
        id: "pnl_percent",
        header: openPositionColumnLabels.pnl_percent,
        meta: { grid: "minmax(96px, 0.7fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span
              className={joinClassNames(
                positionStatusValue,
                row.original.unrealizedPnlPercentRaw === null
                  ? undefined
                  : row.original.unrealizedPnlPercentRaw > 0
                  ? positionPnlPositiveText
                  : row.original.unrealizedPnlPercentRaw < 0
                    ? positionPnlNegativeText
                    : undefined,
              )}
            >
              {row.original.unrealizedPnlPercent}
            </span>
          </div>
        ),
      }),
      openColumnHelper.accessor("openedAt", {
        id: "opened_at",
        header: openPositionColumnLabels.opened_at,
        meta: { grid: "minmax(144px, 0.92fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionTimestampCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.openedAt}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("updatedAt", {
        id: "updated_at",
        header: openPositionColumnLabels.updated_at,
        meta: { grid: "minmax(144px, 0.92fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionTimestampCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.updatedAt}</span>
          </div>
        ),
      }),
      openColumnHelper.accessor("openedAtRaw", {
        id: "age",
        header: openPositionColumnLabels.age,
        meta: { grid: "minmax(96px, 0.72fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{formatRelativeAge(row.original.openedAtRaw)}</span>
          </div>
        ),
      }),
      openColumnHelper.display({
        id: "actions",
        header: "Действия",
        meta: { grid: "minmax(92px, 0.64fr)" },
        cell: ({ row }) => (
          <div className={positionActionsCell}>
            <div className={positionTimestampCell}>
              <span className={positionStatusValue}>Действия</span>
              <span className={positionStatusMeta}>Быстрые команды</span>
            </div>
            <div
              ref={(node) => {
                positionActionAnchorRefs.current[getOpenPositionRowKey(row.original.positionId)] = node;
              }}
              className={positionActionsAnchor}
              data-position-actions-anchor="true"
            >
              <button
                type="button"
                className={positionActionsTrigger}
                aria-label={`Действия для ${row.original.symbol}`}
                aria-haspopup="menu"
                aria-expanded={
                  openPositionActionsFor === getOpenPositionRowKey(row.original.positionId)
                }
                onClick={(event) =>
                  handlePositionActionsToggle(
                    event,
                    getOpenPositionRowKey(row.original.positionId),
                  )
                }
              >
                ⋯
              </button>
            </div>
          </div>
        ),
      }),
    ],
    [openPositionActionsFor],
  );

  const historyColumns = useMemo(
    () => [
      historyColumnHelper.accessor("symbol", {
        id: "instrument",
        header: positionHistoryColumnLabels.instrument,
        meta: { grid: "minmax(200px, 1fr)" },
        cell: ({ row }) => (
          <div className={positionPairCell}>
            <span className={positionPrimaryValue}>{row.original.symbol}</span>
            <span className={positionSecondaryValue}>{row.original.symbolMeta}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("exchange", {
        id: "exchange",
        header: positionHistoryColumnLabels.exchange,
        meta: { grid: "minmax(96px, 0.72fr)" },
        filterFn: (row, columnId, value) => {
          if (!value || value === "all") {
            return true;
          }
          return String(row.getValue(columnId)).trim().toLowerCase() === String(value).trim().toLowerCase();
        },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.exchange}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("sideLabel", {
        id: "direction",
        header: positionHistoryColumnLabels.direction,
        meta: { grid: "minmax(96px, 0.72fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(tableCell, positionsPageCenteredSimpleCell)}>
            <span className={row.original.sideLabel === "LONG" ? positionSideLong : positionSideShort}>
              {row.original.sideLabel}
            </span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("entryPrice", {
        id: "entry",
        header: positionHistoryColumnLabels.entry,
        meta: { grid: "minmax(120px, 0.82fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.entryPrice}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("exitPrice", {
        id: "exit",
        header: positionHistoryColumnLabels.exit,
        meta: { grid: "minmax(120px, 0.82fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.exitPrice}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("quantity", {
        id: "size",
        header: positionHistoryColumnLabels.size,
        meta: { grid: "minmax(112px, 0.8fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.quantity}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("initialStop", {
        id: "initial_stop",
        header: positionHistoryColumnLabels.initial_stop,
        meta: { grid: "minmax(124px, 0.86fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.initialStop}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("currentStop", {
        id: "exit_stop",
        header: positionHistoryColumnLabels.exit_stop,
        meta: { grid: "minmax(124px, 0.86fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionMetricCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.currentStop}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("trailingState", {
        id: "trailing",
        header: positionHistoryColumnLabels.trailing,
        meta: { grid: "minmax(96px, 0.72fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.trailingState}</span>
            <span className={positionStatusMeta}>{row.original.trailingStateMeta}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("realizedPnlRRaw", {
        id: "result_r",
        header: positionHistoryColumnLabels.result_r,
        meta: { grid: "minmax(96px, 0.72fr)" },
        sortingFn: nullableNumberSortingFn,
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.realizedPnlR}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("realizedPnlUsdRaw", {
        id: "result_usd",
        header: positionHistoryColumnLabels.result_usd,
        meta: { grid: "minmax(112px, 0.8fr)" },
        sortingFn: nullableNumberSortingFn,
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span
              className={joinClassNames(
                positionStatusValue,
                row.original.realizedPnlUsdRaw === null
                  ? undefined
                  : row.original.realizedPnlUsdRaw > 0
                    ? positionPnlPositiveText
                    : row.original.realizedPnlUsdRaw < 0
                      ? positionPnlNegativeText
                      : undefined,
              )}
            >
              {row.original.realizedPnlUsd}
            </span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("realizedPnlPercentRaw", {
        id: "result_percent",
        header: positionHistoryColumnLabels.result_percent,
        meta: { grid: "minmax(96px, 0.72fr)" },
        sortingFn: nullableNumberSortingFn,
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span
              className={joinClassNames(
                positionStatusValue,
                row.original.realizedPnlPercentRaw === null
                  ? undefined
                  : row.original.realizedPnlPercentRaw > 0
                    ? positionPnlPositiveText
                    : row.original.realizedPnlPercentRaw < 0
                      ? positionPnlNegativeText
                      : undefined,
              )}
            >
              {row.original.realizedPnlPercent}
            </span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("openedAtRaw", {
        id: "opened_at",
        header: positionHistoryColumnLabels.opened_at,
        meta: { grid: "minmax(144px, 0.92fr)" },
        sortingFn: isoDateSortingFn,
        cell: ({ row }) => (
          <div className={joinClassNames(positionTimestampCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.openedAt}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("closedAtRaw", {
        id: "closed_at",
        header: positionHistoryColumnLabels.closed_at,
        meta: { grid: "minmax(144px, 0.92fr)" },
        sortingFn: isoDateSortingFn,
        cell: ({ row }) => (
          <div className={joinClassNames(positionTimestampCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.closedAt}</span>
          </div>
        ),
      }),
      historyColumnHelper.accessor("exitReason", {
        id: "exit_reason",
        header: positionHistoryColumnLabels.exit_reason,
        meta: { grid: "minmax(148px, 1fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>{row.original.exitReason}</span>
          </div>
        ),
      }),
      historyColumnHelper.display({
        id: "duration",
        header: positionHistoryColumnLabels.duration,
        meta: { grid: "minmax(96px, 0.72fr)" },
        cell: ({ row }) => (
          <div className={joinClassNames(positionStatusCell, positionsPageCenteredValueCell)}>
            <span className={positionStatusValue}>
              {formatDurationBetween(row.original.openedAtRaw, row.original.closedAtRaw)}
            </span>
          </div>
        ),
      }),
      historyColumnHelper.accessor(
        (row) => `${row.symbol} ${row.exchange} ${row.positionId}`.toLowerCase(),
        {
          id: "search_index",
          header: "",
          enableHiding: true,
          filterFn: (row, columnId, value) =>
            String(row.getValue(columnId)).includes(String(value).trim().toLowerCase()),
          cell: () => null,
          meta: { grid: "0px" },
        },
      ),
    ],
    [],
  );

  const historyColumnFilters = useMemo<ColumnFiltersState>(() => {
    const next: ColumnFiltersState = [];
    if (historyPairQuery.trim()) {
      next.push({ id: "search_index", value: historyPairQuery });
    }
    if (historyExchangeFilter !== "all") {
      next.push({ id: "exchange", value: historyExchangeFilter });
    }
    return next;
  }, [historyExchangeFilter, historyPairQuery]);

  const historySorting = useMemo<SortingState>(() => {
    switch (historySort) {
      case "result-desc":
        return [{ id: "result_r", desc: true }];
      case "result-asc":
        return [{ id: "result_r", desc: false }];
      default:
        return [{ id: "closed_at", desc: true }];
    }
  }, [historySort]);

  const openTable = useReactTable({
    data: openPositionsRows,
    columns: openColumns,
    getRowId: (row) => row.positionId,
    getCoreRowModel: getCoreRowModel(),
  });

  const historyTable = useReactTable({
    data: positionHistoryRows,
    columns: historyColumns,
    getRowId: (row) => row.positionId,
    state: {
      columnFilters: historyColumnFilters,
      sorting: historySorting,
      columnVisibility: { search_index: false },
    },
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const fullModuleGridTemplate = useMemo(() => buildGridTemplate(openColumns), [openColumns]);
  const historyGridTemplate = useMemo(
    () => buildGridTemplate(historyColumns.filter((column) => column.id !== "search_index")),
    [historyColumns],
  );

  const handleRowActivate = (rowKey: string) => {
    setSelectedRowKey(rowKey);
  };

  const handlePositionsViewChange = (nextView: "open" | "history") => {
    clearPositionActions();
    setSelectedRowKey(null);
    setPositionsView(nextView);
  };

  const handleRowKeyDown = (event: ReactKeyboardEvent<HTMLElement>, rowKey: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleRowActivate(rowKey);
    }
  };

  const openPositionActionRow = openPositionActionsFor
    ? openPositionsRows.find((row) => getOpenPositionRowKey(row.positionId) === openPositionActionsFor) ?? null
    : null;
  const pendingPositionRow = pendingPositionAction
    ? openPositionsRows.find((row) => getOpenPositionRowKey(row.positionId) === pendingPositionAction.rowKey) ?? null
    : null;

  return (
    <div className={positionsPageRoot}>
      <div className={positionsPageHeader}>
        <div className={positionsPageTitle}>Позиции</div>
      </div>

      <section className={`${card} ${positionsPageSection}`}>
        <div className={positionsWidgetContent}>
          <div className={positionsWidgetHeader}>
            <div className={positionsWidgetHeaderMain}>
              <div className={positionModeSwitch}>
                <button
                  type="button"
                  className={`${positionModeButton} ${positionsView === "open" ? positionModeButtonActive : ""}`}
                  onClick={() => handlePositionsViewChange("open")}
                >
                  Открытые позиции
                </button>
                <button
                  type="button"
                  className={`${positionModeButton} ${positionsView === "history" ? positionModeButtonActive : ""}`}
                  onClick={() => handlePositionsViewChange("history")}
                >
                  История позиций
                </button>
              </div>
            </div>
          </div>

          {positionsView === "open" ? (
            <div className={positionsPageWideViewport}>
              <div className={`${positionsTable} ${positionsPageWideTable}`}>
                <div
                  className={tableHeader}
                  style={{ gridTemplateColumns: fullModuleGridTemplate, minWidth: "max-content" } as CSSProperties}
                >
                  {openTable.getHeaderGroups()[0]?.headers.map((header) => (
                    <div
                      key={header.id}
                      className={joinClassNames(
                        positionsHeaderCell,
                        isOpenColumnCentered(header.column.id) && positionsHeaderCellCentered,
                      )}
                    >
                      {header.column.id === "actions" ? (
                        <span className={positionsHeaderStaticLabel}>
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </span>
                      ) : (
                        <button
                          type="button"
                          className={joinClassNames(
                            positionsHeaderToggle,
                            isOpenColumnCentered(header.column.id) && positionsHeaderContentCentered,
                            isOpenProjectionColumnSelected(header.column.id as OpenPositionColumnKey)
                              ? positionsHeaderToggleActive
                              : positionsHeaderToggleInactive,
                            lockedOpenPositionColumnKeys.has(header.column.id as OpenPositionColumnKey) &&
                              positionsHeaderToggleLocked,
                          )}
                          aria-pressed={isOpenProjectionColumnSelected(header.column.id as OpenPositionColumnKey)}
                          disabled={lockedOpenPositionColumnKeys.has(header.column.id as OpenPositionColumnKey)}
                          onClick={() =>
                            toggleHomeProjectionColumn(header.column.id as OpenPositionColumnKey)
                          }
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </button>
                      )}
                    </div>
                  ))}
                </div>

                <div className={positionsTableBodyViewport}>
                  {openPositionsQuery.isLoading ? (
                    <div className={joinClassNames(positionsEmptyState, positionsPageEmptyState)}>
                      <span className={positionPrimaryValue}>Открытые позиции загружаются</span>
                    </div>
                  ) : openPositionsQuery.isError ? (
                    <div className={joinClassNames(positionsEmptyState, positionsPageEmptyState)}>
                      <span className={positionPrimaryValue}>Ошибка: открытые позиции недоступны</span>
                    </div>
                  ) : openPositionsRows.length === 0 ? (
                    <div className={joinClassNames(positionsEmptyState, positionsPageEmptyState)}>
                      <span className={positionPrimaryValue}>Открытых позиций нет</span>
                    </div>
                  ) : (
                    openTable.getRowModel().rows.map((row) => {
                      const rowKey = getOpenPositionRowKey(row.original.positionId);

                      return (
                        <div
                          key={row.original.positionId}
                          className={`${tableRow} ${positionsPageTableRow} ${tableRowInteractive} ${positionsPageInteractiveRow} ${selectedRowKey === rowKey ? tableRowActive : ""}`}
                          style={{
                            gridTemplateColumns: fullModuleGridTemplate,
                            minWidth: "max-content",
                          } as CSSProperties}
                          role="button"
                          tabIndex={0}
                          aria-label={`Выбрать позицию ${row.original.symbol}`}
                          onClick={() => handleRowActivate(rowKey)}
                          onKeyDown={(event) => handleRowKeyDown(event, rowKey)}
                        >
                          {row.getVisibleCells().map((cell) => (
                            <div key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</div>
                          ))}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className={positionsPageWideViewport}>
              <div className={`${positionsTable} ${positionsPageWideTable}`}>
                <div className={`${positionsHistoryControls} ${positionsPageControlsRow}`}>
                  <div className={positionsPageControlsCluster}>
                    <input
                      type="text"
                      className={`${positionsHistorySearchInput} ${positionsPageSearchCompact}`}
                      placeholder="Поиск по паре"
                      aria-label="Поиск в истории позиций по паре"
                      name="positions-page-history-search"
                      value={historyPairQuery}
                      onChange={(event) => setHistoryPairQuery(event.target.value)}
                    />
                    <select
                      className={positionsHistorySelect}
                      aria-label="Фильтр истории позиций по бирже"
                      name="positions-page-history-exchange"
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
                      name="positions-page-history-strategy"
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
                      name="positions-page-history-sort"
                      value={historySort}
                      onChange={(event) =>
                        setHistorySort(event.target.value as typeof historySort)
                      }
                    >
                      <option value="recent">Сначала новые</option>
                      <option value="result-desc">Лучший результат</option>
                      <option value="result-asc">Худший результат</option>
                    </select>
                  </div>
                </div>

                <div
                  className={tableHeader}
                  style={{ gridTemplateColumns: historyGridTemplate, minWidth: "max-content" } as CSSProperties}
                >
                  {historyTable.getHeaderGroups()[0]?.headers.map((header) => (
                    <div
                      key={header.id}
                      className={joinClassNames(
                        positionsHeaderCell,
                        isHistoryColumnCentered(header.column.id) && positionsHeaderCellCentered,
                      )}
                    >
                      <button
                        type="button"
                        className={joinClassNames(
                          positionsHeaderToggle,
                          isHistoryColumnCentered(header.column.id) && positionsHeaderContentCentered,
                          isHistoryProjectionColumnSelected(header.column.id as PositionHistoryColumnKey)
                            ? positionsHeaderToggleActive
                            : positionsHeaderToggleInactive,
                          lockedPositionHistoryColumnKeys.has(header.column.id as PositionHistoryColumnKey) &&
                            positionsHeaderToggleLocked,
                        )}
                        aria-pressed={isHistoryProjectionColumnSelected(header.column.id as PositionHistoryColumnKey)}
                        disabled={lockedPositionHistoryColumnKeys.has(header.column.id as PositionHistoryColumnKey)}
                        onClick={() =>
                          toggleHistoryProjectionColumn(
                            header.column.id as PositionHistoryColumnKey,
                          )
                        }
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </button>
                    </div>
                  ))}
                </div>

                <div className={positionsTableBodyViewport}>
                  {positionHistoryQuery.isLoading ? (
                    <div className={joinClassNames(positionsEmptyState, positionsPageEmptyState)}>
                      <span className={positionPrimaryValue}>История позиций загружается</span>
                    </div>
                  ) : positionHistoryQuery.isError ? (
                    <div className={joinClassNames(positionsEmptyState, positionsPageEmptyState)}>
                      <span className={positionPrimaryValue}>Ошибка: история позиций недоступна</span>
                    </div>
                  ) : positionHistoryRows.length === 0 ? (
                    <div className={joinClassNames(positionsEmptyState, positionsPageEmptyState)}>
                      <span className={positionPrimaryValue}>Истории позиций нет</span>
                    </div>
                  ) : (
                    historyTable.getRowModel().rows.map((row) => (
                      <div
                        key={row.original.positionId}
                        className={`${tableRow} ${positionsPageTableRow}`}
                        style={{
                          gridTemplateColumns: historyGridTemplate,
                          minWidth: "max-content",
                        } as CSSProperties}
                      >
                          {row.getVisibleCells().map((cell) => (
                            <div key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</div>
                          ))}
                        </div>
                      ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
      {typeof document !== "undefined" &&
      positionActionOverlayPosition &&
      openPositionActionRow
        ? createPortal(
            <div
              ref={positionActionsLayerRef}
              className={positionActionOverlayLayer}
              style={{
                top: `${positionActionOverlayPosition.top}px`,
                left: `${positionActionOverlayPosition.left}px`,
                width: `${positionActionMenuEstimate.width}px`,
              }}
              role="menu"
              aria-label={`Действия для ${openPositionActionRow.symbol}`}
              onClick={(event) => event.stopPropagation()}
            >
              <div className={positionActionsMenu}>
                {positionQuickActions.map((action) => (
                  <button
                    key={action}
                    type="button"
                    role="menuitem"
                    className={positionActionsMenuItem}
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
              className={positionActionOverlayLayer}
              style={{
                top: `${positionActionOverlayPosition.top}px`,
                left: `${positionActionOverlayPosition.left}px`,
                width: `${positionActionConfirmEstimate.width}px`,
              }}
              role="dialog"
              aria-label={`${positionQuickActionLabels[pendingPositionAction.action]} для ${pendingPositionRow.symbol}`}
              onClick={(event) => event.stopPropagation()}
            >
              <div className={positionActionPanel}>
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
                    className={positionActionPanelCancel}
                    onClick={handlePositionActionCancel}
                  >
                    Отменить
                  </button>
                  <button
                    type="button"
                    className={positionActionPanelConfirm}
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
    </div>
  );
}
