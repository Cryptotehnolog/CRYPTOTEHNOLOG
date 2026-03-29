export type TerminalWidgetId =
  | "chart"
  | "market-watch"
  | "focus-alerts"
  | "trend"
  | "volume"
  | "signal"
  | "positions";

export type TerminalWidgetType =
  | "chart"
  | "watchlist"
  | "alerts"
  | "stat"
  | "positions";

export type TerminalWidgetLayout = {
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
};

export type TerminalWidget = {
  id: TerminalWidgetId;
  type: TerminalWidgetType;
  title: string;
  visible: boolean;
  layout: TerminalWidgetLayout;
};

export const terminalWidgetStorageKey = "cryptotechnolog.terminal.widgets";

const legacy12ToCurrentGridScaleFactor = 8;
const current24ToDenseGridScaleFactor = 4;
const current48ToUltraDenseGridScaleFactor = 2;

export const terminalDefaultWidgets: TerminalWidget[] = [
  {
    id: "chart",
    type: "chart",
    title: "График",
    visible: true,
    layout: { x: 0, y: 0, w: 64, h: 96 },
  },
  {
    id: "market-watch",
    type: "watchlist",
    title: "Рынок",
    visible: true,
    layout: { x: 64, y: 0, w: 32, h: 34 },
  },
  {
    id: "focus-alerts",
    type: "alerts",
    title: "Фокус",
    visible: true,
    layout: { x: 64, y: 34, w: 32, h: 38 },
  },
  {
    id: "trend",
    type: "stat",
    title: "Тренд",
    visible: true,
    layout: { x: 0, y: 96, w: 24, h: 20 },
  },
  {
    id: "volume",
    type: "stat",
    title: "Объём",
    visible: true,
    layout: { x: 24, y: 96, w: 24, h: 20 },
  },
  {
    id: "signal",
    type: "stat",
    title: "Сигнал",
    visible: true,
    layout: { x: 64, y: 72, w: 32, h: 24 },
  },
  {
    id: "positions",
    type: "positions",
    title: "Позиции",
    visible: true,
    layout: { x: 0, y: 116, w: 96, h: 52 },
  },
];

function isLegacy12Grid(rawWidgets: Array<Partial<TerminalWidget> & { id: string }>) {
  return rawWidgets.length > 0 && rawWidgets.every((item) => {
    const layout = item.layout;
    if (!layout) {
      return true;
    }

    const x = typeof layout.x === "number" ? layout.x : 0;
    const y = typeof layout.y === "number" ? layout.y : 0;
    const w = typeof layout.w === "number" ? layout.w : 0;
    const h = typeof layout.h === "number" ? layout.h : 0;

    return x <= 12 && y <= 15 && w <= 12 && h <= 12;
  });
}

function isCurrent24Grid(rawWidgets: Array<Partial<TerminalWidget> & { id: string }>) {
  return rawWidgets.length > 0 && rawWidgets.every((item) => {
    const layout = item.layout;
    if (!layout) {
      return true;
    }

    const x = typeof layout.x === "number" ? layout.x : 0;
    const y = typeof layout.y === "number" ? layout.y : 0;
    const w = typeof layout.w === "number" ? layout.w : 0;
    const h = typeof layout.h === "number" ? layout.h : 0;

    return x <= 24 && y <= 42 && w <= 24 && h <= 24;
  });
}

function isCurrent48Grid(rawWidgets: Array<Partial<TerminalWidget> & { id: string }>) {
  return rawWidgets.length > 0 && rawWidgets.every((item) => {
    const layout = item.layout;
    if (!layout) {
      return true;
    }

    const x = typeof layout.x === "number" ? layout.x : 0;
    const y = typeof layout.y === "number" ? layout.y : 0;
    const w = typeof layout.w === "number" ? layout.w : 0;
    const h = typeof layout.h === "number" ? layout.h : 0;

    return x <= 48 && y <= 84 && w <= 48 && h <= 48;
  });
}

export function normalizeTerminalWidgets(input: unknown): TerminalWidget[] {
  const rawWidgets = Array.isArray(input) ? input : [];
  const typedWidgets = rawWidgets.filter(
    (item): item is Partial<TerminalWidget> & { id: string } =>
      !!item && typeof item === "object" && "id" in item,
  );
  const shouldMigrateLegacy12Grid = isLegacy12Grid(typedWidgets);
  const shouldMigrateCurrent24Grid = !shouldMigrateLegacy12Grid && isCurrent24Grid(typedWidgets);
  const shouldMigrateCurrent48Grid =
    !shouldMigrateLegacy12Grid &&
    !shouldMigrateCurrent24Grid &&
    isCurrent48Grid(typedWidgets);
  const widgetMap = new Map(
    typedWidgets.map((item) => [item.id, item]),
  );

  return terminalDefaultWidgets.map((widget) => {
    const persisted = widgetMap.get(widget.id);
    const persistedLayout = persisted?.layout;
    const x = typeof persistedLayout?.x === "number" ? persistedLayout.x : widget.layout.x;
    const y = typeof persistedLayout?.y === "number" ? persistedLayout.y : widget.layout.y;
    const w = typeof persistedLayout?.w === "number" ? persistedLayout.w : widget.layout.w;
    const h = typeof persistedLayout?.h === "number" ? persistedLayout.h : widget.layout.h;
    const scaledLayout = shouldMigrateLegacy12Grid
      ? {
          x: x * legacy12ToCurrentGridScaleFactor,
          y: y * legacy12ToCurrentGridScaleFactor,
          w: w * legacy12ToCurrentGridScaleFactor,
          h: h * legacy12ToCurrentGridScaleFactor,
        }
      : shouldMigrateCurrent24Grid
        ? {
            x: x * current24ToDenseGridScaleFactor,
            y: y * current24ToDenseGridScaleFactor,
            w: w * current24ToDenseGridScaleFactor,
            h: h * current24ToDenseGridScaleFactor,
          }
        : shouldMigrateCurrent48Grid
          ? {
              x: x * current48ToUltraDenseGridScaleFactor,
              y: y * current48ToUltraDenseGridScaleFactor,
              w: w * current48ToUltraDenseGridScaleFactor,
              h: h * current48ToUltraDenseGridScaleFactor,
            }
        : { x, y, w, h };

    return {
      ...widget,
      visible: typeof persisted?.visible === "boolean" ? persisted.visible : widget.visible,
      layout: {
        ...widget.layout,
        x: scaledLayout.x,
        y: scaledLayout.y,
        w: scaledLayout.w,
        h: scaledLayout.h,
        maxW: typeof persisted?.layout?.maxW === "number" ? persisted.layout.maxW : widget.layout.maxW,
        maxH: typeof persisted?.layout?.maxH === "number" ? persisted.layout.maxH : widget.layout.maxH,
      },
    };
  });
}
