import { create } from "zustand";

export type TerminalTheme = "dark" | "light";
export type TerminalMode = "manual" | "auto";
export type TerminalExchangeState = {
  name: "OKX" | "Bybit" | "Binance";
  connected: boolean;
  pingTone: "good" | "warn" | "bad";
  ping: string;
};

export type TerminalSection =
  | "home"
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
  mode: TerminalMode;
  exchanges: TerminalExchangeState[];
  openDrawer: () => void;
  closeDrawer: () => void;
  setActiveSection: (section: TerminalSection) => void;
  toggleTheme: () => void;
  setMode: (mode: TerminalMode) => void;
  setExchangeConnected: (exchangeName: TerminalExchangeState["name"], connected: boolean) => void;
};

export const useTerminalUiStore = create<TerminalUiState>((set) => ({
  activeSection: "home",
  drawerOpen: false,
  theme: "dark",
  mode: "manual",
  exchanges: [
    { name: "OKX", connected: true, pingTone: "good", ping: "18 ms" },
    { name: "Bybit", connected: true, pingTone: "warn", ping: "74 ms" },
    { name: "Binance", connected: false, pingTone: "bad", ping: "timeout" },
  ],
  openDrawer: () => set({ drawerOpen: true }),
  closeDrawer: () => set({ drawerOpen: false }),
  setActiveSection: (section) => set({ activeSection: section, drawerOpen: false }),
  toggleTheme: () =>
    set((state) => ({
      theme: state.theme === "dark" ? "light" : "dark",
    })),
  setMode: (mode) => set({ mode }),
  setExchangeConnected: (exchangeName, connected) =>
    set((state) => ({
      exchanges: state.exchanges.map((exchange) =>
        exchange.name === exchangeName
          ? {
              ...exchange,
              connected,
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
