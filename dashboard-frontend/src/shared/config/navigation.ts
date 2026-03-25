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
    description: "Жизненный цикл системы и дисциплина исполнения",
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
    description: "Формирование сигналов и текущее сигнальное состояние",
    route: "/signals",
    phase: "v1.8.0",
  },
  {
    key: "strategy",
    title: "Стратегия",
    description: "Основа стратегии и состояние кандидатов",
    route: "/strategy",
    phase: "v1.9.0",
  },
  {
    key: "execution",
    title: "Исполнение",
    description: "Контур исполнения и состояние намерений",
    route: "/execution",
    phase: "v1.10.0",
  },
  {
    key: "oms",
    title: "OMS",
    description: "Контур OMS и состояние заявок",
    route: "/oms",
    phase: "v1.16.0",
  },
  {
    key: "manager",
    title: "Менеджер",
    description: "Контур менеджера и состояние рабочих процессов",
    route: "/manager",
    phase: "v1.17.0",
  },
  {
    key: "validation",
    title: "Валидация",
    description: "Контур валидации и состояние проверок",
    route: "/validation",
    phase: "v1.18.0",
  },
  {
    key: "paper",
    title: "Пейпер",
    description: "Пейпер-контур и состояние репетиций",
    route: "/paper",
    phase: "v1.19.0",
  },
  {
    key: "backtest",
    title: "Бэктест",
    description: "Контур бэктеста и состояние прогонов",
    route: "/backtest",
    phase: "v1.20.0",
  },
  {
    key: "reporting",
    title: "Отчётность",
    description: "Каталог отчётных артефактов и bundle-снимков",
    route: "/reporting",
    phase: "v1.21.0",
  },
  {
    key: "opportunity",
    title: "Возможности",
    description: "Отбор возможностей и селекционный контур",
    route: "/opportunity",
    phase: "v1.11.0",
  },
  {
    key: "orchestration",
    title: "Оркестрация",
    description: "Оркестрация стратегий и мета-уровень",
    route: "/orchestration",
    phase: "v1.12.0",
  },
  {
    key: "position-expansion",
    title: "Расширение позиции",
    description: "Контур расширения позиции",
    route: "/position-expansion",
    phase: "v1.13.0",
  },
  {
    key: "portfolio-governor",
    title: "Портфельный контур",
    description: "Контур управления капиталом и портфелем",
    route: "/portfolio-governor",
    phase: "v1.14.0",
  },
];
