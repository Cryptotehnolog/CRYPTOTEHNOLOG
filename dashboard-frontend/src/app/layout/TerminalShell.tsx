import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import * as Tooltip from "@radix-ui/react-tooltip";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Bell,
  Gauge,
  Home,
  LineChart,
  Moon,
  Menu,
  Plug,
  Settings,
  ShieldAlert,
  SunMedium,
  Wallet,
} from "lucide-react";

import {
  dialogContent,
  dialogContentTone,
  dialogA11yHidden,
  dialogListViewport,
  dialogOverlay,
  dialogOverlayTone,
  dialogTone,
  mainFrame,
  navDrawerItem,
  navDrawerItemActive,
  navDrawerItemIcon,
  navDrawerItemMeta,
  navDrawerItemText,
  navDrawerList,
  rail,
  railButton,
  railSection,
  shellRoot,
  shellSurface,
  shellTone,
  tooltipContent,
  tooltipTone,
  topBar,
  topBarActionCluster,
  topBarBrandBlock,
  topBarBrandTitle,
  topBarCluster,
  topBarLeftCluster,
  topBarMetaLabel,
  topBarEmergency,
  topBarSignalDot,
  topBarStatusBlock,
  topBarStatusValue,
  topBarStatusZone,
  topBarThemeSwitch,
  topBarTimeValue,
  topBarExchangeCapsule,
  topBarExchangeName,
  topBarExchangePing,
} from "./TerminalShell.css";
import { getBybitConnectorDiagnostics } from "../../modules/terminal/api/getBybitConnectorDiagnostics";
import { getBybitSpotConnectorDiagnostics } from "../../modules/terminal/api/getBybitSpotConnectorDiagnostics";
import { type TerminalSection, useTerminalUiStore } from "../../modules/terminal/state/useTerminalUiStore";

const terminalSections: Array<{
  section: TerminalSection;
  label: string;
  meta: string;
  icon: typeof Home;
}> = [
  { section: "home", label: "Главная", meta: "рабочий стол", icon: Home },
  {
    section: "connectors",
    label: "Коннекторы",
    meta: "биржи и живые подключения",
    icon: Plug,
  },
  { section: "market", label: "Рынок", meta: "наблюдение и контекст", icon: LineChart },
  { section: "positions", label: "Позиции", meta: "открытые сделки", icon: Wallet },
  {
    section: "strategies",
    label: "Стратегии",
    meta: "активные подходы",
    icon: BarChart3,
  },
  { section: "signals", label: "Сигналы", meta: "точки внимания", icon: Bell },
  { section: "risk", label: "Риск", meta: "лимиты и защита", icon: ShieldAlert },
  { section: "reports", label: "Отчёты", meta: "сводки и артефакты", icon: Activity },
  {
    section: "diagnostics",
    label: "Диагностика",
    meta: "контроль системы",
    icon: Gauge,
  },
  {
    section: "settings",
    label: "Настройки",
    meta: "контур терминала",
    icon: Settings,
  },
];

const getBybitRttTone = (transportRttMs: number | null) => {
  if (transportRttMs === null) {
    return "good" as const;
  }

  if (transportRttMs <= 120) {
    return "good" as const;
  }

  if (transportRttMs <= 300) {
    return "warn" as const;
  }

  return "bad" as const;
};

const isBybitTimeoutState = (diagnostics: {
  last_disconnect_reason: string | null;
  degraded_reason: string | null;
}) => {
  const timeoutText = `${diagnostics.last_disconnect_reason ?? ""} ${diagnostics.degraded_reason ?? ""}`
    .toLowerCase();
  return timeoutText.includes("timeout");
};

const getBybitPingFallback = (
  diagnostics: Array<{
    last_disconnect_reason: string | null;
    degraded_reason: string | null;
    transport_status: string;
    policy_apply_status?: string | null;
    subscription_alive: boolean;
    trade_seen: boolean;
    orderbook_seen: boolean;
    application_heartbeat_latency_ms: number | null;
    last_message_at: string | null;
    message_age_ms: number | null;
  }>,
) => {
  const anyAlive = diagnostics.some(
    (item) =>
      item.transport_status === "connected" &&
      (item.subscription_alive ||
        item.trade_seen ||
        item.orderbook_seen ||
        item.application_heartbeat_latency_ms !== null ||
        item.last_message_at !== null ||
        item.message_age_ms !== null),
  );
  if (anyAlive) {
    return { label: "LIVE", tone: "good" as const };
  }
  const waitingForScope = diagnostics.some(
    (item) =>
      item.transport_status === "idle" &&
      (item.degraded_reason === "discovery_unavailable" ||
        item.policy_apply_status === "waiting_for_scope"),
  );
  if (waitingForScope) {
    return { label: "WAITING", tone: "warn" as const };
  }
  return diagnostics.some(isBybitTimeoutState)
    ? { label: "TIMEOUT", tone: "bad" as const }
    : { label: "ERROR", tone: "bad" as const };
};

const formatBybitTransportStatus = (status: string) => {
  switch (status) {
    case "connected":
      return "подключено";
    case "connecting":
      return "подключаемся";
    case "disconnected":
      return "нет соединения";
    case "idle":
      return "ожидает запуска";
    case "disabled":
      return "отключено";
    default:
      return status;
  }
};

const isBybitRecoveryInProgress = (diagnostics: {
  transport_status: string;
  recovery_status: string;
  derived_trade_count_state: string | null;
  derived_trade_count_backfill_status: string | null;
  universe_admission_state: string | null;
}) =>
  diagnostics.recovery_status !== "recovered" ||
  diagnostics.universe_admission_state === "waiting_for_filter_readiness" ||
  diagnostics.derived_trade_count_state === "warming_up" ||
  diagnostics.derived_trade_count_state === "not_reliable_after_gap" ||
  diagnostics.derived_trade_count_backfill_status === "pending" ||
  diagnostics.derived_trade_count_backfill_status === "running" ||
  (diagnostics.transport_status === "idle" &&
    diagnostics.universe_admission_state === "waiting_for_filter_readiness");

const getBybitContourHeaderState = (diagnostics: {
  enabled: boolean;
  transport_status: string;
  policy_apply_status: string | null;
  universe_admission_state: string | null;
  operator_runtime_state: string | null;
}) => {
  if (!diagnostics.enabled) {
    return "disabled" as const;
  }
  if (diagnostics.policy_apply_status === "deferred") {
    return "deferred" as const;
  }
  if (diagnostics.universe_admission_state === "ready_for_selection") {
    return "ready" as const;
  }
  if (diagnostics.operator_runtime_state === "waiting_for_live_tail") {
    return "live_tail" as const;
  }
  if (diagnostics.transport_status === "connected") {
    return "recovering" as const;
  }
  if (diagnostics.transport_status === "connecting" || diagnostics.transport_status === "idle") {
    return "connecting" as const;
  }
  return "offline" as const;
};

const formatBybitContourHeaderDetail = (
  label: string,
  diagnostics: {
    enabled: boolean;
    transport_status: string;
    universe_admission_state: string | null;
    policy_apply_status: string | null;
    policy_apply_reason: string | null;
    degraded_reason?: string | null;
    operator_runtime_state: string | null;
    operator_confidence_state?: string | null;
    historical_recovery_state?: string | null;
    active_subscribed_scope_count: number;
  },
) => {
  if (!diagnostics.enabled) {
    return `${label}: отключён`;
  }
  if (diagnostics.policy_apply_status === "deferred") {
    return `${label}: настройка сохранена, но начнёт действовать позже${diagnostics.policy_apply_reason ? ` · ${diagnostics.policy_apply_reason}` : ""}`;
  }
  if (diagnostics.operator_confidence_state === "streams_recovering") {
    return `${label}: потоки данных восстанавливаются`;
  }
  if (diagnostics.universe_admission_state === "ready_for_selection") {
    return `${label}: готов · ${diagnostics.active_subscribed_scope_count} инструментов в работе`;
  }
  if (diagnostics.operator_runtime_state === "waiting_for_live_tail") {
    return `${label}: ждёт последние сделки после переподключения`;
  }
  if (diagnostics.historical_recovery_state === "retry_scheduled") {
    return `${label}: повтор загрузки истории запланирован`;
  }
  if (
    diagnostics.degraded_reason === "discovery_unavailable" ||
    diagnostics.policy_apply_status === "waiting_for_scope"
  ) {
    return `${label}: ждёт список инструментов`;
  }
  return `${label}: ${formatBybitTransportStatus(diagnostics.transport_status)}`;
};

function RailIconButton(props: {
  label: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
        <Tooltip.Root delayDuration={120}>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          className={railButton}
          aria-label={props.label}
          onClick={props.onClick}
        >
          {props.children}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          sideOffset={10}
          className={`${tooltipContent} ${tooltipTone.dark}`}
        >
          {props.label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export function TerminalShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTerminalUiStore((state) => state.theme);
  const drawerOpen = useTerminalUiStore((state) => state.drawerOpen);
  const activeSection = useTerminalUiStore((state) => state.activeSection);
  const exchanges = useTerminalUiStore((state) => state.exchanges);
  const openDrawer = useTerminalUiStore((state) => state.openDrawer);
  const closeDrawer = useTerminalUiStore((state) => state.closeDrawer);
  const setActiveSection = useTerminalUiStore((state) => state.setActiveSection);
  const toggleTheme = useTerminalUiStore((state) => state.toggleTheme);
  const bybitDiagnosticsQuery = useQuery({
    queryKey: ["dashboard", "settings", "bybit-connector-diagnostics"],
    queryFn: getBybitConnectorDiagnostics,
    refetchInterval: 5000,
  });
  const bybitSpotDiagnosticsQuery = useQuery({
    queryKey: ["dashboard", "settings", "bybit-spot-connector-diagnostics"],
    queryFn: getBybitSpotConnectorDiagnostics,
    refetchInterval: 5000,
  });

  const formatTerminalClock = (date: Date) =>
    `${new Intl.DateTimeFormat("ru-RU", {
      timeZone: "Europe/Minsk",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date)} UTC+3`;

  const [clock, setClock] = useState(() => formatTerminalClock(new Date()));

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setClock(formatTerminalClock(new Date()));
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, []);

  const currentSection: TerminalSection =
    location.pathname === "/terminal/connectors"
      ? "connectors"
      : location.pathname === "/terminal/settings"
      ? "settings"
      : location.pathname === "/terminal/positions"
        ? "positions"
        : activeSection;

  const handleSectionSelect = (section: TerminalSection) => {
    setActiveSection(section);
    navigate(
      section === "settings"
        ? "/terminal/settings"
        : section === "connectors"
          ? "/terminal/connectors"
        : section === "positions"
          ? "/terminal/positions"
          : "/terminal",
    );
  };

  const displayedExchanges = useMemo(
    () =>
      exchanges.map((exchange) => {
        if (exchange.name !== "Bybit") {
          return exchange;
        }

        if (bybitDiagnosticsQuery.isLoading || bybitSpotDiagnosticsQuery.isLoading) {
          return {
            ...exchange,
            connected: false,
            ping: "loading",
            pingTone: "warn" as const,
          };
        }

        if (
          bybitDiagnosticsQuery.isError ||
          bybitSpotDiagnosticsQuery.isError ||
          !bybitDiagnosticsQuery.data ||
          !bybitSpotDiagnosticsQuery.data
        ) {
          return {
            ...exchange,
            connected: false,
            ping: "error",
            pingTone: "bad" as const,
          };
        }

        const diagnostics = [bybitDiagnosticsQuery.data, bybitSpotDiagnosticsQuery.data];
        const enabledDiagnostics = diagnostics.filter((item) => item.enabled);
        const connectedDiagnostics = enabledDiagnostics.filter(
          (item) => item.transport_status === "connected",
        );
        const contourStates = diagnostics.map(getBybitContourHeaderState);
        const anyEnabled = enabledDiagnostics.length > 0;
        const connected = connectedDiagnostics.length > 0;
        const recovering = enabledDiagnostics.some(isBybitRecoveryInProgress);
        const fullyConnected =
          anyEnabled &&
          enabledDiagnostics.every(
            (item) =>
              item.transport_status === "connected" && !isBybitRecoveryInProgress(item),
          );
        const mixed = connected && recovering && !fullyConnected;
        const connecting = enabledDiagnostics.some(
          (item) =>
            item.transport_status === "connecting" ||
            item.lifecycle_state === "connecting" ||
            item.transport_status === "idle",
        );
        const aggregatedRtt = connectedDiagnostics.reduce<number | null>((best, item) => {
          if (item.transport_rtt_ms === null) {
            return best;
          }
          if (best === null) {
            return item.transport_rtt_ms;
          }
          return Math.min(best, item.transport_rtt_ms);
        }, null);
        const primaryEnabledDiagnostics =
          diagnostics.find((item) => item.enabled && item.transport_status !== "disabled") ??
          diagnostics.find((item) => item.enabled) ??
          diagnostics[0];

        let ping = "disabled";
        let pingTone: "good" | "warn" | "bad" | "neutral" = "neutral";
        let statusState:
          | "connected"
          | "mixed"
          | "deferred"
          | "recovering"
          | "connecting"
          | "disabled"
          | "offline" =
          "disabled";
        let connectedState = false;
        const title = [
          formatBybitContourHeaderDetail("Perp", bybitDiagnosticsQuery.data),
          formatBybitContourHeaderDetail("Spot", bybitSpotDiagnosticsQuery.data),
        ].join("\n");

        if (contourStates.some((state) => state === "deferred")) {
          if (aggregatedRtt !== null) {
            ping = `RTT ${aggregatedRtt} ms`;
            pingTone = getBybitRttTone(aggregatedRtt);
          } else {
            const fallback = getBybitPingFallback(enabledDiagnostics);
            ping = fallback.label;
            pingTone = fallback.tone;
          }
          statusState = connected ? "mixed" : "deferred";
          connectedState = connected;
        } else if (mixed) {
          if (aggregatedRtt !== null) {
            ping = `RTT ${aggregatedRtt} ms`;
            pingTone = getBybitRttTone(aggregatedRtt);
          } else {
            const fallback = getBybitPingFallback(enabledDiagnostics);
            ping = fallback.label;
            pingTone = fallback.tone;
          }
          statusState = "mixed";
          connectedState = true;
        } else if (fullyConnected || connected) {
          if (aggregatedRtt !== null) {
            ping = `RTT ${aggregatedRtt} ms`;
            pingTone = getBybitRttTone(aggregatedRtt);
          } else {
            const fallback = getBybitPingFallback(enabledDiagnostics);
            ping = fallback.label;
            pingTone = fallback.tone;
          }
          statusState = "connected";
          connectedState = true;
        } else if (anyEnabled && recovering) {
          ping = enabledDiagnostics.some(isBybitTimeoutState) ? "timeout" : "error";
          pingTone = "bad";
          statusState = "recovering";
        } else if (anyEnabled && connecting) {
          ping = primaryEnabledDiagnostics.transport_status;
          pingTone = "warn";
          statusState = "connecting";
        } else if (anyEnabled) {
          ping = primaryEnabledDiagnostics.transport_status;
          pingTone = "bad";
          statusState = "offline";
        }

        return {
          ...exchange,
          connected: connectedState,
          statusState,
          ping,
          pingTone,
          title,
        };
      }),
    [
      bybitDiagnosticsQuery.data,
      bybitDiagnosticsQuery.isError,
      bybitDiagnosticsQuery.isLoading,
      bybitSpotDiagnosticsQuery.data,
      bybitSpotDiagnosticsQuery.isError,
      bybitSpotDiagnosticsQuery.isLoading,
      exchanges,
    ],
  );

  return (
    <Tooltip.Provider>
      <Dialog.Root open={drawerOpen} onOpenChange={(open) => (open ? openDrawer() : closeDrawer())}>
        <div className={`${shellRoot} ${shellTone[theme]}`}>
          <aside className={rail} aria-label="Быстрые элементы терминала">
            <div className={railSection}>
              <Dialog.Trigger asChild>
                <button
                  type="button"
                  className={railButton}
                  aria-label="Открыть навигацию терминала"
                >
                  <Menu size={20} />
                </button>
              </Dialog.Trigger>
            </div>
          </aside>

          <div className={shellSurface}>
            <header className={topBar}>
              <div className={topBarLeftCluster}>
                <div className={topBarBrandBlock}>
                  <div className={topBarBrandTitle}>CRYPTOTEHNOLOG</div>
                </div>

                <div className={topBarStatusBlock}>
                  <div className={topBarStatusValue}>
                    <span className={topBarSignalDot} />
                    Активна
                  </div>
                </div>
              </div>

              <div className={topBarCluster}>
                <div className={topBarStatusBlock}>
                  <div className={topBarStatusValue}>
                    Автоматический отбор
                  </div>
                </div>

              </div>

              <div className={topBarActionCluster}>
                <div className={topBarStatusBlock}>
                  <div className={topBarStatusZone}>
                    {displayedExchanges.map((exchange) => (
                      <div
                        key={exchange.name}
                        className={topBarExchangeCapsule}
                        data-exchange-state={exchange.statusState ?? (exchange.connected ? "connected" : "offline")}
                        title={exchange.title}
                      >
                        <span className={topBarExchangeName}>{exchange.name}</span>
                        <span className={topBarExchangePing} data-ping-tone={exchange.pingTone}>
                          {exchange.ping}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className={topBarTimeValue}>{clock}</div>

                <button
                  type="button"
                  className={topBarThemeSwitch}
                  onClick={toggleTheme}
                  aria-label="Переключение темы терминала"
                >
                  {theme === "dark" ? <Moon size={18} /> : <SunMedium size={18} />}
                </button>

                <button className={topBarEmergency} type="button">
                  STOP
                </button>
              </div>
            </header>

            <div className={mainFrame}>
              <Outlet />
            </div>
          </div>
        </div>

        <Dialog.Portal>
          <Dialog.Overlay className={`${dialogOverlay} ${dialogOverlayTone[theme]}`} />
          <Dialog.Content className={`${dialogContent} ${dialogContentTone[theme]} ${dialogTone[theme]}`}>
            <Dialog.Title className={dialogA11yHidden}>Навигация терминала</Dialog.Title>
            <Dialog.Description className={dialogA11yHidden}>
              Основные разделы терминала для перехода между рабочими зонами.
            </Dialog.Description>
            <div className={dialogListViewport}>
              <nav className={navDrawerList}>
                {terminalSections.map((item) => {
                  const Icon = item.icon;
                  const isActive = item.section === currentSection;

                  return (
                    <Dialog.Close asChild key={item.section}>
                      <button
                        type="button"
                        className={`${navDrawerItem} ${isActive ? navDrawerItemActive : ""}`}
                        aria-current={isActive ? "page" : undefined}
                        onClick={() => handleSectionSelect(item.section)}
                      >
                        <span className={navDrawerItemIcon}>
                          <Icon size={18} />
                        </span>
                        <span className={navDrawerItemText}>
                          {item.label}
                          <span className={navDrawerItemMeta}>{item.meta}</span>
                        </span>
                      </button>
                    </Dialog.Close>
                  );
                })}
              </nav>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </Tooltip.Provider>
  );
}
