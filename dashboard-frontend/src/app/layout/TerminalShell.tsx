import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  Activity,
  BarChart3,
  Bell,
  Gauge,
  Home,
  LineChart,
  Moon,
  Menu,
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
import { type TerminalSection, useTerminalUiStore } from "../../modules/terminal/state/useTerminalUiStore";

const terminalSections: Array<{
  section: TerminalSection;
  label: string;
  meta: string;
  icon: typeof Home;
}> = [
  { section: "home", label: "Главная", meta: "рабочий стол", icon: Home },
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
  const mode = useTerminalUiStore((state) => state.mode);
  const exchanges = useTerminalUiStore((state) => state.exchanges);
  const openDrawer = useTerminalUiStore((state) => state.openDrawer);
  const closeDrawer = useTerminalUiStore((state) => state.closeDrawer);
  const setActiveSection = useTerminalUiStore((state) => state.setActiveSection);
  const toggleTheme = useTerminalUiStore((state) => state.toggleTheme);

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
    location.pathname === "/terminal/settings" ? "settings" : activeSection;

  const handleSectionSelect = (section: TerminalSection) => {
    setActiveSection(section);
    navigate(section === "settings" ? "/terminal/settings" : "/terminal");
  };

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
                    {mode === "manual" ? "Ручной режим" : "Авто режим"}
                  </div>
                </div>

              </div>

              <div className={topBarActionCluster}>
                <div className={topBarStatusBlock}>
                  <div className={topBarStatusZone}>
                    {exchanges.map((exchange) => (
                      <div
                        key={exchange.name}
                        className={topBarExchangeCapsule}
                        data-exchange-state={exchange.connected ? "connected" : "offline"}
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
