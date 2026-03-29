import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import {
  normalizeTerminalWidgets,
  terminalDefaultWidgets,
  terminalWidgetStorageKey,
  type TerminalWidget,
  type TerminalWidgetId,
  type TerminalWidgetLayout,
} from "./terminalWidgets";

type TerminalWidgetStore = {
  widgets: TerminalWidget[];
  setWidgetVisible: (id: TerminalWidgetId, visible: boolean) => void;
      updateWidgetLayouts: (
    layouts: ReadonlyArray<{
      i: string;
      x: number;
      y: number;
      w: number;
      h: number;
    }>,
  ) => void;
};

export const useTerminalWidgetStore = create<TerminalWidgetStore>()(
  persist(
    (set) => ({
      widgets: terminalDefaultWidgets,
      setWidgetVisible: (id, visible) =>
        set((state) => ({
          widgets: state.widgets.map((widget) =>
            widget.id === id ? { ...widget, visible } : widget,
          ),
        })),
      updateWidgetLayouts: (layouts) =>
        set((state) => {
          const nextLayouts = new Map(layouts.map((layout) => [layout.i, layout]));

          return {
            widgets: state.widgets.map((widget) => {
              const layout = nextLayouts.get(widget.id);
              if (!layout) {
                return widget;
              }

              const nextLayout: TerminalWidgetLayout = {
                ...widget.layout,
                x: layout.x,
                y: layout.y,
                w: layout.w,
                h: layout.h,
              };

              return {
                ...widget,
                layout: nextLayout,
              };
            }),
          };
        }),
    }),
    {
      name: terminalWidgetStorageKey,
      storage: createJSONStorage(() => window.localStorage),
      partialize: (state) => ({
        widgets: state.widgets,
      }),
      merge: (persisted, current) => {
        const persistedWidgets =
          persisted && typeof persisted === "object" && "widgets" in persisted
            ? (persisted as { widgets?: unknown }).widgets
            : undefined;

        return {
          ...current,
          widgets: normalizeTerminalWidgets(persistedWidgets),
        };
      },
    },
  ),
);
