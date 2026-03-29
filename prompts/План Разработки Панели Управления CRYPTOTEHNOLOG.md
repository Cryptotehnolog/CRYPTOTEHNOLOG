# План Разработки Панели Управления CRYPTOTEHNOLOG

## Summary

Разработка панели идёт не как отдельный “сайт”, а как поэтапное наращивание `Platform Control Center` поверх существующей и будущей архитектуры `CRYPTOTEHNOLOG`.

Ключевой принцип:
- сначала фиксируется целевая архитектура всей панели;
- затем делается `v1` каркас;
- дальше модули подключаются по волнам готовности backend;
- каждый модуль проходит стадии `inactive -> read-only -> active`.

Базовая стратегия:
- не ждать конца проекта;
- не пытаться сразу реализовать финальную панель целиком;
- строить единый интерфейс, но включать только реально поддержанные функции.

## Этап 1. Архитектурная Фиксация Панели

### Цель
Зафиксировать фундаментальные решения до начала кода.

### Что определить
- frontend-стек;
- место панели в репозитории;
- способ связи frontend и backend;
- модель модулей `inactive/read-only/active/restricted`;
- глобальную структуру интерфейса;
- политику критических действий;
- правила маршрутизации и layout.

### Результат этапа
- утверждённый целевой концепт панели;
- карта модулей;
- список модулей `v1`;
- соглашение по UX для критических действий;
- техническое решение по frontend/backend структуре.

### Рекомендуемый default
- frontend: `React + TypeScript`
- backend UI API: `FastAPI`
- real-time: `WebSocket`
- режим встраивания: отдельный frontend-модуль + backend API внутри основного проекта

## Этап 2. Информационная Архитектура И UI-System

### Цель
Создать устойчивую структуру панели до подключения реальных данных.

### Что проектируется
- глобальный shell панели;
- верхняя командная строка статуса;
- левая навигация;
- правая context rail;
- базовые page templates;
- единая система компонентов.

### Базовые UI-примитивы
- status badge;
- severity banner;
- metric card;
- section panel;
- dense table;
- timeline;
- event list;
- detail drawer;
- approval card;
- unavailable module state;
- stale/error/loading states.

### Результат этапа
- единый дизайн-каркас всей панели;
- набор базовых компонентов;
- структура экранов без глубокой бизнес-логики.

## Этап 3. Backend UI Facade Layer

### Цель
Сделать отдельный API-слой для панели, не смешивая UI напрямую с внутренними core-классами.

### Что создаётся
- dashboard API слой;
- DTO/view model слой;
- адаптеры к `SystemController`, `StateMachine`, `Health`, `OperatorGate`, `ConfigManager`, `EnhancedEventBus`, `Metrics`;
- единая схема ошибок и статусов;
- реестр доступности модулей.

### Почему это важно
Панель не должна зависеть от внутренних структур backend напрямую.  
Нужен стабильный слой представления, чтобы backend можно было развивать без постоянной ломки UI.

### Результат этапа
- REST endpoints для snapshot-данных;
- WebSocket канал для real-time обновлений;
- module availability registry.

## Этап 4. V1 Каркас Панели

### Цель
Запустить пустую, но рабочую панель со всей навигацией и фазируемой архитектурой.

### Что входит
- app shell;
- маршруты всех основных модулей;
- статусы `inactive/read-only/active`;
- overview page placeholder;
- общая система уведомлений;
- global header с system state area;
- глобальный индикатор alerts и approvals.

### Результат этапа
- панель открывается;
- навигация уже соответствует финальной архитектуре;
- неготовые модули отображаются корректно как roadmap-aware sections.

## Этап 5. Волна V1: Обзор Платформы

### Цель
Сделать первый реально полезный экран.

### Подключаемые данные
- текущее состояние системы;
- uptime;
- агрегированный health summary;
- active alerts summary;
- pending approvals count;
- последние события;
- краткий статус circuit breakers.

### Источники
- `SystemController.get_status()`
- health subsystem
- `EnhancedEventBus.get_metrics()`
- event snapshots
- `OperatorGate.get_stats()`

### Результат этапа
- главный экран даёт оператору понимание состояния платформы за несколько секунд.

## Этап 6. Волна V1: Control Plane

### Цель
Подключить управление жизненным циклом системы.

### Что реализуется
- экран состояния системы;
- визуализация state machine;
- allowed transitions;
- история переходов;
- причина последнего перехода;
- торговля разрешена / запрещена;
- controlled transition requests.

### Источники
- `StateMachine`
- `SystemController`
- transition history
- operator workflows

### Результат этапа
- панель показывает и контролирует `Control Plane` в реальном времени.

## Этап 7. Волна V1: Health И Observability

### Цель
Подключить техническую диагностику платформы.

### Что реализуется
- экран здоровья компонентов;
- component detail drawer;
- circuit breaker view;
- health latency/status/error data;
- базовый observability overview;
- SLO/metrics snapshot.

### Источники
- `health.py`
- `Watchdog`
- `MetricsCollector`
- `EnhancedEventBus.get_metrics()`

### Результат этапа
- оператор может быстро локализовать технический инцидент.

## Этап 8. Волна V1: Operator Gate

### Цель
Подключить безопасное управление критическими действиями.

### Что реализуется
- список pending requests;
- история approvals/rejections/expirations;
- карточка запроса;
- безопасные действия подтверждения/отклонения;
- глобальный индикатор запросов;
- audit visibility.

### Источники
- `OperatorGate`
- `DualControlRequest`
- operator stats/history

### Результат этапа
- критические операции становятся управляемыми через единый UI-поток.

## Этап 9. Волна V1: Config Snapshot И Events

### Цель
Показать текущую конфигурацию системы и поток событий.

### Что реализуется
- config summary;
- config version, environment, last update;
- risk snapshot;
- enabled exchanges and strategies;
- events page with filters;
- event detail drawer.

### Источники
- `ConfigManager`
- event bus
- config models

### Результат этапа
- оператор видит текущую конфигурацию и может быстро анализировать события вокруг инцидента.

## Этап 10. Стабилизация V1

### Цель
Довести первую волну панели до устойчивого состояния.

### Что проверить
- consistency UI state management;
- reconnect WebSocket;
- stale data handling;
- error boundaries;
- loading/empty/error/unavailable patterns;
- RBAC placeholders;
- audit correctness;
- UX критических действий.

### Тестирование
- unit tests для frontend state/formatting;
- API tests для facade layer;
- integration tests для WebSocket и REST snapshots;
- сценарии деградации и потери соединения.

### Результат этапа
- `v1` пригодна для ежедневного операторского использования.

## Этап 11. Волна V2: Риск И Ограничения

### Цель
Подключить полноценный риск-модуль по мере зрелости backend.

### Что добавляется
- risk overview;
- violations;
- risk budgets;
- drawdown tracking;
- exposure view;
- correlation summary;
- risk ledger snapshot;
- kill switch state.

### Режим запуска
- сначала `read-only`;
- после зрелости Risk Engine — `active`.

## Этап 12. Волна V2: Портфель И Капитал

### Цель
Добавить портфельную картину платформы.

### Что добавляется
- equity;
- capital allocation;
- open positions;
- pnl summary;
- exposure by symbol/strategy/exchange;
- portfolio controls при наличии backend-поддержки.

### Режим запуска
- сначала `inactive` или `read-only`;
- затем `active`.

## Этап 13. Волна V2: Стратегии И Сигналы

### Цель
Подключить уровень торговой логики.

### Что добавляется
- список стратегий;
- статус стратегии;
- signal feed;
- strategy health;
- conflict resolution summary;
- strategy-level performance.

### Режим запуска
- сначала read-only;
- активные действия только при готовом backend governance.

## Этап 14. Волна V3: Исполнение И Ордера

### Цель
Подключить execution layer.

### Что добавляется
- order book of system actions;
- active orders;
- fills/rejects;
- execution latency;
- route/failover details;
- controlled cancel workflows;
- exchange execution diagnostics.

### Режим запуска
- только после зрелости execution backend.

## Этап 15. Волна V3: Биржи И Инфраструктура Рынка

### Цель
Сделать модуль контроля внешних торговых интеграций.

### Что добавляется
- exchange connectivity;
- funding data;
- per-exchange limits;
- maintenance/degraded status;
- failover state;
- symbol availability and routing health.

## Этап 16. Волна V4: Продвинутый Конфиг И Approval Workflows

### Цель
Эволюция конфигурационного модуля.

### Что добавляется
- config diff;
- staged changes;
- approval workflow;
- rollback entry points;
- validation preview;
- signature/audit integration.

### Условие
Только после того, как backend умеет безопасный workflow изменений.

## Этап 17. Волна V4: Audit, Replay, Compliance

### Цель
Подключить глубокие операционные и комплаенс-инструменты.

### Что добавляется
- audit chain views;
- immutable event trail;
- replay entry points;
- incident timelines;
- compliance export surfaces.

## Этап 18. Волна V5: Модели, Симуляции, Аналитика

### Цель
Подключить поздние исследовательские и аналитические модули.

### Что добавляется
- model risk;
- simulation UI;
- stress scenarios;
- Monte Carlo views;
- research dashboards;
- advanced performance surfaces.

## Delivery Strategy

### Как идти практически
Каждый модуль проходит один и тот же цикл:
1. conceptual design
2. UI shell
3. backend facade
4. read-only connection
5. real-time updates
6. active actions
7. stabilization

### Правило внедрения
- сначала snapshot-данные;
- потом live updates;
- потом только mutating actions.

### Правило критических действий
Все опасные действия:
- не внедряются до появления audit;
- не внедряются до operator workflow;
- не размещаются как “обычные кнопки” на произвольных страницах.

## Test Plan

### На каждом модуле проверять
- `inactive` state;
- `read-only` state;
- `active` state;
- ошибки backend;
- потерю WebSocket;
- stale data;
- неавторизованный доступ;
- критические workflow;
- поведение при деградации системы.

### Сквозные сценарии
1. Система переходит `TRADING -> DEGRADED`, и это видно во всех релевантных местах.
2. Появляется pending approval, и он отражается глобально и в `Operator Gate`.
3. Компонент становится unhealthy, и оператор видит и summary, и detail.
4. Модуль переводится из `inactive` в `read-only` без переделки layout.
5. Модуль переводится в `active` без изменения общей архитектуры панели.

## Assumptions

- Панель будет строиться внутри текущего проекта, а не как полностью отдельная система.
- Базовый стек: `React + TypeScript + FastAPI + WebSocket`.
- Первая полезная версия панели — операторская, а не торгово-аналитическая.
- Все будущие модули заранее присутствуют в информационной архитектуре панели.
- Подключение функциональности идёт строго по готовности backend и по принципу безопасности, а не по визуальному желанию.
