export type NavigationItem = {
  key: string;
  title: string;
  description: string;
  route: string;
  phase: string;
};

export const navigationItems: NavigationItem[] = [
  {
    key: "overview",
    title: "Обзор",
    description: "Глобальный обзор состояния платформы",
    route: "/overview",
    phase: "v1.14.0",
  },
  {
    key: "control-plane",
    title: "Контур управления",
    description: "Жизненный цикл системы и runtime discipline",
    route: "/control-plane",
    phase: "core",
  },
  {
    key: "health-observability",
    title: "Здоровье и наблюдаемость",
    description: "Деградации, здоровье и наблюдаемость",
    route: "/health",
    phase: "core",
  },
  {
    key: "operator-gate",
    title: "Операторский контур",
    description: "Ожидающие подтверждения и двойной контроль",
    route: "/operator-gate",
    phase: "core",
  },
  {
    key: "config-events",
    title: "Конфигурация и события",
    description: "Снимки конфигурации и события",
    route: "/config-events",
    phase: "v1.4.0",
  },
  {
    key: "risk",
    title: "Риск",
    description: "Риск, лимиты и ограничения",
    route: "/risk",
    phase: "v1.5.1",
  },
  {
    key: "signals",
    title: "Сигналы",
    description: "Signal Generation Foundation и signal truth",
    route: "/signals",
    phase: "v1.8.0",
  },
  {
    key: "strategy",
    title: "Стратегия",
    description: "Strategy Foundation и strategy candidate truth",
    route: "/strategy",
    phase: "v1.9.0",
  },
  {
    key: "execution",
    title: "Исполнение",
    description: "Execution Foundation и execution intent truth",
    route: "/execution",
    phase: "v1.10.0",
  },
  {
    key: "opportunity",
    title: "Opportunity",
    description: "Opportunity / Selection Foundation",
    route: "/opportunity",
    phase: "v1.11.0",
  },
  {
    key: "orchestration",
    title: "Orchestration",
    description: "Strategy Orchestration / Meta Layer",
    route: "/orchestration",
    phase: "v1.12.0",
  },
  {
    key: "position-expansion",
    title: "Position Expansion",
    description: "Position Expansion Foundation",
    route: "/position-expansion",
    phase: "v1.13.0",
  },
  {
    key: "portfolio-governor",
    title: "Portfolio Governor",
    description: "Portfolio Governor / Capital Governance Foundation",
    route: "/portfolio-governor",
    phase: "v1.14.0",
  },
];
