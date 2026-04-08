import { create } from "zustand";

export type TerminalTheme = "dark" | "light";
export type TerminalExchangeState = {
  name: "OKX" | "Bybit" | "Binance";
  connected: boolean;
  statusState?:
    | "connected"
    | "mixed"
    | "deferred"
    | "recovering"
    | "connecting"
    | "disabled"
    | "offline";
  pingTone: "good" | "warn" | "bad" | "neutral";
  ping: string;
  title?: string;
};

export type TerminalSection =
  | "home"
  | "connectors"
  | "market"
  | "positions"
  | "strategies"
  | "signals"
  | "risk"
  | "reports"
  | "diagnostics"
  | "settings";

type TerminalUiState = {
  activeSection: TerminalSection;
  drawerOpen: boolean;
  theme: TerminalTheme;
  exchanges: TerminalExchangeState[];
  openDrawer: () => void;
  closeDrawer: () => void;
  setActiveSection: (section: TerminalSection) => void;
  toggleTheme: () => void;
  setExchangeConnected: (exchangeName: TerminalExchangeState["name"], connected: boolean) => void;
};

export const useTerminalUiStore = create<TerminalUiState>((set) => ({
  activeSection: "home",
  drawerOpen: false,
  theme: "dark",
  exchanges: [
    { name: "OKX", connected: true, statusState: "connected", pingTone: "good", ping: "18 ms" },
    { name: "Bybit", connected: true, statusState: "connected", pingTone: "warn", ping: "74 ms" },
    { name: "Binance", connected: false, statusState: "offline", pingTone: "bad", ping: "timeout" },
  ],
  openDrawer: () => set({ drawerOpen: true }),
  closeDrawer: () => set({ drawerOpen: false }),
  setActiveSection: (section) => set({ activeSection: section, drawerOpen: false }),
  toggleTheme: () =>
    set((state) => ({
      theme: state.theme === "dark" ? "light" : "dark",
    })),
  setExchangeConnected: (exchangeName, connected) =>
    set((state) => ({
      exchanges: state.exchanges.map((exchange) =>
        exchange.name === exchangeName
          ? {
              ...exchange,
              connected,
              statusState: connected ? "connected" : "offline",
              ping: connected ? (exchange.name === "OKX" ? "18 ms" : "74 ms") : "timeout",
              pingTone: connected
                ? exchange.name === "OKX"
                  ? "good"
                  : "warn"
                : "bad",
            }
          : exchange,
      ),
    })),
}));
