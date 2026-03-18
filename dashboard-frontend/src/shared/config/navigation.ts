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
    phase: "v1",
  },
  {
    key: "control-plane",
    title: "Контур управления",
    description: "Жизненный цикл системы",
    route: "/control-plane",
    phase: "v1",
  },
  {
    key: "health-observability",
    title: "Здоровье и наблюдаемость",
    description: "Деградации, здоровье и наблюдаемость",
    route: "/health",
    phase: "v1",
  },
  {
    key: "operator-gate",
    title: "Операторский контур",
    description: "Ожидающие подтверждения и двойной контроль",
    route: "/operator-gate",
    phase: "v1",
  },
  {
    key: "config-events",
    title: "Конфигурация и события",
    description: "Снимки конфигурации и события",
    route: "/config-events",
    phase: "v1",
  },
  {
    key: "risk",
    title: "Риск",
    description: "Риск, лимиты и ограничения",
    route: "/risk",
    phase: "v2",
  },
  {
    key: "portfolio",
    title: "Портфель и капитал",
    description: "Портфель и капитал",
    route: "/portfolio",
    phase: "v2",
  },
  {
    key: "strategies",
    title: "Стратегии и сигналы",
    description: "Сигналы и состояние стратегий",
    route: "/strategies",
    phase: "v2",
  },
  {
    key: "execution",
    title: "Исполнение и ордера",
    description: "Исполнение и ордера",
    route: "/execution",
    phase: "v3",
  },
  {
    key: "exchanges",
    title: "Биржи",
    description: "Внешние торговые интеграции",
    route: "/exchanges",
    phase: "v3",
  },
  {
    key: "advanced-config",
    title: "Расширенная конфигурация",
    description: "Управляемые сценарии конфигурации",
    route: "/advanced-config",
    phase: "v4",
  },
  {
    key: "audit-compliance",
    title: "Аудит и соответствие",
    description: "След аудита и контуры соответствия",
    route: "/audit",
    phase: "v4",
  },
  {
    key: "analytics",
    title: "Модели и аналитика",
    description: "Поздние исследовательские модули",
    route: "/analytics",
    phase: "v5",
  },
];
