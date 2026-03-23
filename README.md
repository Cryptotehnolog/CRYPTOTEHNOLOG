# CRYPTOTEHNOLOG

## Институциональная криптотрейдинговая платформа

Мультибиржевая алгоритмическая торговая платформа для small prop firm / crypto fund уровня с расчётом на капитал $100M+.

---

## Обзор проекта

`CRYPTOTEHNOLOG` — это автономная, self-healing платформа, которая должна обеспечивать:

- мультибиржевое исполнение на крупных криптобиржах (`Bybit`, `OKX`, `Binance`);
- институциональный уровень риск-менеджмента на базе `Phase 5 Risk Engine`;
- длительную автономную работу без постоянного ручного сопровождения;
- многослойную деградацию и восстановление runtime;
- криптографически надёжный audit trail;
- низколатентные критические торговые контуры.

---

## Архитектура

### Мультиязычная архитектура

Ниже показана честная current architecture truth после closure-ready `P_18`
как узкой `Validation Foundation`,
с отдельной пометкой для следующих planned contours.

```text
CRYPTOTEHNOLOG Platform
│
├── Control Plane (Python)
│   ├── State Machine
│   ├── Config Manager
│   ├── Risk Engine (Phase 5 orchestration)
│   ├── Operator Gate / Watchdog / Health truth
│   └── Portfolio Governor / [Closure-Ready] Protection contour
│
├── Data Plane
│   ├── Event Bus (Rust) ← high-performance messaging
│   ├── Rust Risk Ledger (legacy/high-performance path)
│   ├── Audit Chain (Rust) ← cryptographic hashing
│   ├── Market Data Layer (Python)
│   ├── Analysis Layer (Python)
│   ├── Intelligence Layer (Python)
│   └── Signal Layer (Python)
│
├── Trading Runtime Layers (Python + Rust)
│   ├── Order Execution Core / bridge contours (Rust + Python)
│   ├── Execution Foundation
│   ├── OMS Foundation
│   ├── Opportunity / Selection Foundation
│   ├── Strategy Orchestration / Meta Layer
│   ├── Position Expansion Foundation
│   ├── Portfolio Governor / Capital Governance Foundation
│   ├── Strategy Manager / Workflow Foundation
│   └── Validation Foundation
│
├── Observability (Python + Web)
│   ├── Metrics Collector (Python)
│   ├── [Planned/Parallel] Web Dashboard (React + TypeScript)
│   └── Grafana/Prometheus Integration
│
└── Storage
    ├── PostgreSQL + TimescaleDB (states, audit, time-series)
    ├── Redis (cache, state machine, pub/sub)
    └── Infisical (secrets management)
```

### Технологический стек

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| **Языки** | Python 3.11+, Rust 1.75+, TypeScript | Мультиязычная архитектура |
| **Базы данных** | PostgreSQL 15, TimescaleDB, Redis 7 | Персистентное хранение и кэш |
| **Секреты** | Infisical, `.env` | Управление секретами |
| **Наблюдаемость** | Grafana, Prometheus | Метрики и мониторинг |
| **Контейнеризация** | Docker, Docker Compose | Среда разработки |
| **Оркестрация** | Kubernetes | Production deployment (`Phase 19`) |
| **CI/CD** | GitHub Actions | Автоматические проверки и deployment |

---

## Статус разработки

| Фаза | Название | Статус | Версия |
|------|----------|--------|--------|
| 0 | Подготовка среды | ✅ Done | v1.0.0 |
| 1 | Ядро инфраструктуры | ✅ Done | v1.1.0 |
| 2 | Control Plane | ✅ Done | v1.2.0 |
| 3 | Event Bus (Enhanced) | ✅ Done | v1.3.0 |
| 4 | Config Manager | ✅ Done | v1.4.0 |
| 5 | Risk Engine | ✅ Done | v1.5.0 |
| 5.1 | Production Alignment | ✅ Done | v1.5.1 |
| 6 | Market Data Layer + Universe Engine | ✅ Done | v1.6.0 |
| 7 | Indicators + Intelligence Foundation | ✅ Done | v1.7.0 |
| 8 | Signal Generation Foundation | ✅ Done | v1.8.0 |
| 9 | Strategy Foundation | ✅ Done | v1.9.0 |
| 10 | Execution Foundation | ✅ Done | v1.10.0 |
| 11 | Opportunity / Selection Foundation | ✅ Done | v1.11.0 |
| 12 | Strategy Orchestration / Meta Layer | ✅ Done | v1.12.0 |
| 13 | Position Expansion Foundation | ✅ Done | v1.13.0 |
| 14 | Portfolio Governor / Capital Governance Foundation | ✅ Done | v1.14.0 |
| 15 | Protection / Supervisor Foundation | ✅ Closure-Ready | v1.15.0 |
| 16 | OMS Foundation | ✅ Closure-Ready | v1.16.0 |
| 17 | Strategy Manager / Workflow Foundation | ✅ Closure-Ready | v1.17.0 |
| 18 | Validation Foundation | ✅ Closure-Ready | v1.18.0 |
| 19 | Deployment | ⏳ Planned | v1.19.0 |

---

## Phase 5 Risk Engine + v1.5.1 Production Alignment

`Phase 5` ввела новый Python-based `Risk Engine` как typed domain layer, встроенный в event-driven runtime без повторного использования legacy risk listener path как основы реализации.

Что было реализовано в `v1.5.0`:

- доменные модели для orders, positions, risk records, trailing updates и funding snapshots;
- `PositionSizer` с `Decimal`-only R-unit sizing и жёсткими инвариантами;
- position-oriented `RiskLedger` как source of truth для риска по открытым позициям;
- `TrailingPolicy` с tiered trailing, emergency mode и обязательной синхронизацией ledger;
- `PortfolioState`, `DrawdownMonitor`, `CorrelationEvaluator` и `FundingManager`;
- `RiskEngine` pre-trade orchestration и event-driven handlers для:
  - `ORDER_FILLED`
  - `POSITION_CLOSED`
  - `BAR_COMPLETED`
  - `STATE_TRANSITION`
- optional persistence foundation для:
  - `risk_checks`
  - `position_risk_ledger`
  - `position_risk_ledger_audit`
  - `trailing_stops`
  - `trailing_stop_movements`
- runtime composition через `create_risk_runtime(...)` с явной регистрацией listeners.

Production alignment в `v1.5.1`:

- официальный production bootstrap через [bootstrap.py](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/bootstrap.py);
- единая runtime identity для version, bootstrap mode, active risk path и config truth;
- production runtime принудительно использует только один active risk path: `phase5_risk_engine`;
- startup, readiness, health, shutdown и fail-fast semantics централизованы и operator-visible;
- risk event vocabulary выровнен между runtime publication, audit и metrics listeners;
- integration/bootstrap tests покрывают реальный production composition root.

Controlled coexistence после `v1.5.1`:

- новый `Phase 5` risk contour — единственный production risk path;
- legacy `core.listeners.risk` остаётся в репозитории только как non-production compatibility / test-only path;
- физическое удаление legacy-кода не входит в scope `v1.5.1`; production bootstrap исключает его явно.

---

## Phase 6 Market Data Layer + Universe Engine Foundation

`Phase 6` на линии `v1.6.0` добавила contract-first `Market Data Layer`, встроенный в production runtime discipline, введённую в `P_5_1`.

Реализованный scope `P_6`:

- typed contracts для ticks, bars, orderbook snapshots, symbol metrics, universe snapshots и confidence semantics;
- foundation-модули для нормализации тиков, построения баров, обработки L2 orderbook и валидации качества market data;
- `SymbolMetricsCollector` и `UniversePolicy` для deterministic admissibility filtering;
- explicit `MarketDataRuntime` как runtime entrypoint `Phase 6` внутри текущего `Event Bus / bootstrap` discipline;
- identity-aware multi-exchange semantics across runtime state, admissibility and universe event payloads;
- market-data readiness, degraded и blocked semantics, встроенные в operator-facing health/runtime diagnostics.

Честные ограничения `P_6`:

- реализованный runtime entrypoint — это `MarketDataRuntime`, а не отдельный websocket-driven `MarketDataManager`;
- universe orchestration реализована через `UniversePolicy` и `MarketDataRuntime.refresh_universe(...)`, а не через отдельный scheduler-style `UniverseEngine`;
- real websocket/feed connectivity и persistence/storage path не входят в завершённый scope `Phase 6` и остаются future follow-up lines;
- ranked universe contract-ready и event-ready, но пока не является full opportunity/ranking engine.

Deferred trigger-based extensions:

- live websocket/feed manager должен вводиться только когда проект переходит от runtime foundation `Phase 6` к real exchange connectivity;
- dedicated market data persistence/history runtime должен вводиться только когда replay, backfill, historical analytics или incident reconstruction станут явной проектной потребностью;
- full ranked/opportunity engine должен вводиться только когда следующая intelligence/strategy line потребует реального ranking-driven instrument selection.

---

## Phase 7 DERYA-first Intelligence Foundation

`Phase 7` закрыта как линия `v1.7.0` в узкой, production-compatible форме:
`DERYA-first intelligence foundation`, а не как full signal/strategy phase.

Реализованный closure scope:

- typed `intelligence` contracts для indicator snapshots, intelligence assessments и DERYA-specific semantics;
- `DeryaEngine` как deterministic, stateful `OHLCV bar-efficiency proxy` regime machine;
- explicit `IntelligenceRuntime` с typed `BAR_COMPLETED` ingest, query surface и operator-facing diagnostics;
- raw market-data `BAR_COMPLETED` остаётся OHLCV event для market-data/intelligence consumers; risk trailing использует отдельный risk-specific bar event boundary;
- narrow composition-root integration в существующую runtime/health/readiness discipline;
- corrective line `C_7R` добавляет shared analysis layer в `src/cryptotechnolog/analysis` как source of truth для derived `ATR/ADX`;
- `SharedAnalysisRuntime` восстанавливает production-compatible path до `RISK_BAR_COMPLETED`, используя:
  - `mark_price` из completed bars;
  - `best_bid / best_ask` из orderbook truth;
  - `ATR / ADX` из shared analysis truth;
- Redis-backed integration verification подтверждает восстановленный production path через bootstrap/runtime wiring.

Честные ограничения после closure:

- full classical indicator runtime/library;
- signal generation, opportunity ranking или strategy integration;
- dashboard-led observability work;
- config hot-reload для broader intelligence/indicator contours.

---

## Phase 8 Signal Generation Foundation

`Phase 8` закрыта как линия `v1.8.0` в узкой, production-compatible форме:
`Signal Generation Foundation`.

Реализованный closure scope:

- typed signal contracts;
- signal validity / readiness semantics;
- typed signal context contract;
- signal event vocabulary;
- explicit `SignalRuntime`;
- deterministic signal context assembly поверх:
  - raw market-data truth;
  - shared analysis truth;
  - intelligence truth;
- narrow composition-root integration;
- operator-visible diagnostics / readiness / degraded truth;
- minimal deterministic contour;
- lifecycle semantics:
  - `ACTIVE`
  - `SUPPRESSED`
  - `INVALIDATED`
  - `EXPIRED`

Честные ограничения после closure:

- это не strategy platform;
- это не `OpportunityEngine`;
- это не `MetaClassifier`;
- это не `StrategyManager`;
- multi-strategy orchestration не входит в scope;
- pyramiding не входит в scope;
- portfolio / supervisor logic не входит в scope;
- persistence-first line не входит в scope;
- broad indicator/runtime expansion не входит в scope;
- dashboard / UI line не входит в scope;
- execution semantics beyond signal foundation не входят в scope.

Deferred follow-up lines после `P_8`:

- `OpportunityEngine` как ranking / opportunity-selection line;
- `MetaClassifier`;
- `StrategyManager`;
- multi-strategy orchestration;
- pyramiding;
- portfolio / supervisor logic;
- signal persistence как отдельная hardening line;
- более широкая execution / orchestration line.

---

## Phase 9 Strategy Foundation

`Phase 9` закрыта как линия `v1.9.0` в узкой, production-compatible форме:
`Strategy Foundation`.

Реализованный closure scope:

- typed strategy contracts;
- strategy validity / readiness semantics;
- typed strategy action candidate contract поверх signal truth;
- typed strategy event vocabulary;
- explicit `StrategyRuntime`;
- deterministic strategy context assembly внутри strategy layer;
- один узкий deterministic strategy contour;
- narrow composition-root integration через existing signal truth;
- operator-visible strategy diagnostics / readiness / degraded truth;
- lifecycle semantics для strategy candidate truth:
  - `CANDIDATE`
  - `ACTIONABLE`
  - `SUPPRESSED`
  - `INVALIDATED`
  - `EXPIRED`
- Redis/DB-backed integration verification для relevant bootstrap/runtime subset.

Честные ограничения после closure:

- это не `Portfolio Governor`;
- это не `CapitalManager`, `VelocityMonitor`, `ExposureLimits` или `DrawdownProtection`;
- это не `OpportunityEngine`;
- это не `MetaClassifier`;
- это не `StrategyManager`;
- multi-strategy orchestration не входит в scope;
- portfolio / supervisor logic не входит в scope;
- execution semantics beyond narrow strategy foundation не входят в scope;
- persistence-first line не входит в scope;
- dashboard / UI line не входит в scope;
- broad analysis/intelligence expansion не входит в scope.

Deferred follow-up lines после `P_9`:

- opportunity / ranking line;
- meta / selection line;
- strategy manager / orchestration line;
- portfolio / supervisor line;
- execution expansion line;
- persistence hardening line.

---

## Быстрый старт

### Предварительные требования

- `Windows 10/11` или `Linux` (`WSL2` для Windows)
- `Python 3.11+`
- `Rust 1.75+`
- `Docker Desktop` с `WSL2`
- `Visual Studio Code`
- `Git`

### Установка

```bash
# Клонировать репозиторий
git clone <repository-url>
cd CRYPTOTEHNOLOG

# Создать виртуальное окружение Python
python -m venv venv

# Активировать окружение
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Установить зависимости Python
pip install -r requirements.txt

# Поднять инфраструктурные сервисы
docker-compose up -d

# Запустить тесты
pytest tests/

# Запустить runtime разработки (когда это нужно)
python -m cryptotechnolog.main
```

### Разработка

```bash
# Linter / formatter
ruff check src/
black src/

# Type checker
mypy src/

# Тесты с coverage
pytest --cov=src --cov-report=html

# Сборка Rust-компонентов
cargo build
cargo test
```

---

## Ближайшие следующие линии после P_17

После closure-ready реализации `P_17` ближайшая нормализованная последовательность фаз выглядит так:

- `P_18+` — validation-supporting и follow-up lines поверх уже отделённых execution / oms / governor / protection / manager contours

Это предварительная roadmap truth.
Authoritative implementation truth для каждой из этих фаз должна открываться отдельно через
`prompts/plan/P_X.md`.

---

## Phase 10 Execution Foundation

`Phase 10` закрыта как линия `v1.10.0` в узкой, production-compatible форме:
`Execution Foundation`.

Реализованный closure scope:

- typed execution contracts;
- execution validity / readiness semantics;
- typed execution event vocabulary;
- explicit `ExecutionRuntime`;
- deterministic `ExecutionContext` assembly внутри execution layer;
- один узкий deterministic execution contour;
- narrow composition-root integration через existing strategy truth;
- operator-visible execution diagnostics / readiness / degraded truth;
- lifecycle semantics для execution intent truth:
  - `CANDIDATE`
  - `EXECUTABLE`
  - `SUPPRESSED`
  - `INVALIDATED`
  - `EXPIRED`
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения после closure:

- это не OMS;
- это не multi-exchange smart routing;
- это не advanced execution algo line;
- это не exchange adapter platform;
- это не exchange failover / advanced reliability line;
- это не portfolio governance;
- это не `OpportunityEngine`, `MetaClassifier` или `StrategyManager`;
- multi-strategy orchestration не входит в scope;
- persistence-first line не входит в scope;
- dashboard / UI line не входит в scope.

---

## Phase 11 Opportunity / Selection Foundation

`Phase 11` закрыта как узкая, production-compatible линия:
`Opportunity / Selection Foundation`.

Реализованный closure scope:

- typed opportunity / selection contracts;
- opportunity validity / readiness semantics;
- typed opportunity event vocabulary;
- explicit `OpportunityRuntime`;
- deterministic `OpportunityContext` assembly внутри opportunity layer;
- один узкий deterministic selection contour;
- narrow composition-root integration через existing execution truth;
- operator-visible opportunity diagnostics / readiness / degraded truth;
- lifecycle semantics для selection candidate truth:
  - `CANDIDATE`
  - `SELECTED`
  - `SUPPRESSED`
  - `INVALIDATED`
  - `EXPIRED`
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения после closure:

- это не OMS;
- это не `MetaClassifier`;
- это не `StrategyManager`;
- это не multi-strategy orchestration;
- это не portfolio / supervisor logic;
- persistence-first line не входит в scope;
- dashboard / UI line не входит в scope.

---

## Phase 12 Strategy Orchestration / Meta Layer

`Phase 12` закрыта как линия `v1.12.0` в узкой, production-compatible форме:
`Strategy Orchestration / Meta Layer`.

Реализованный closure scope:

- typed orchestration / meta contracts;
- orchestration validity / readiness semantics;
- typed orchestration event vocabulary;
- explicit `OrchestrationRuntime`;
- deterministic `OrchestrationContext` assembly внутри orchestration layer;
- один узкий deterministic contour с явными `FORWARD` / `ABSTAIN`;
- narrow composition-root integration через existing opportunity truth;
- operator-visible orchestration diagnostics / readiness / degraded truth;
- lifecycle semantics для orchestration decision truth:
  - `CANDIDATE`
  - `ORCHESTRATED`
  - `ABSTAINED`
  - `INVALIDATED`
  - `EXPIRED`
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения после closure:

- это не full `StrategyManager`;
- это не broad workflow orchestration;
- это не `OMS`;
- это не `Kill Switch` / protection line;
- это не portfolio / supervisor logic;
- persistence-first line не входит в scope;
- dashboard / UI line не входит в scope.

---

## Phase 13 Position Expansion Foundation

`Phase 13` закрыта как линия `v1.13.0` в узкой, production-compatible форме:
`Position Expansion Foundation`.

Реализованный closure scope:

- typed position-expansion contracts;
- add-to-position eligibility / validity / readiness semantics;
- typed position-expansion event vocabulary;
- explicit `PositionExpansionRuntime`;
- deterministic `ExpansionContext` assembly внутри position-expansion layer;
- один узкий deterministic add-to-position contour с явными `ADD` / `ABSTAIN` / `REJECT`;
- narrow composition-root integration через existing orchestration truth;
- operator-visible position-expansion diagnostics / readiness / degraded truth;
- lifecycle semantics для expansion candidate truth:
  - `CANDIDATE`
  - `EXPANDABLE`
  - `ABSTAINED`
  - `REJECTED`
  - `INVALIDATED`
  - `EXPIRED`
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения после closure:

- это не portfolio-wide governance;
- это не exposure supervisor semantics;
- это не `Kill Switch` / protection line;
- это не `OMS`;
- это не full `StrategyManager`;
- это не analytics / validation / notifications line;
- dashboard / UI line не входит в scope.

---

## Phase 14 Portfolio Governor / Capital Governance Foundation

`Phase 14` закрыта как узкая, production-compatible линия:
`Portfolio Governor / Capital Governance Foundation`.

В реализованный scope `P_14` входят:

- typed portfolio-governor contracts;
- capital-governance / portfolio-admission semantics;
- typed portfolio-governor event vocabulary;
- explicit `PortfolioGovernorRuntime`;
- deterministic `GovernorContext` assembly внутри portfolio-governor layer;
- один узкий deterministic governor contour с явными `APPROVE` / `ABSTAIN` / `REJECT`;
- narrow composition-root integration через existing position-expansion truth;
- operator-visible portfolio-governor diagnostics / readiness / degraded truth;
- lifecycle semantics для governor candidate truth:
  - `CANDIDATE`
  - `APPROVED`
  - `ABSTAINED`
  - `REJECTED`
  - `INVALIDATED`
  - `EXPIRED`
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения закрытой `P_14`:

- это не protection / `Kill Switch` line;
- это не `OMS`;
- это не full `StrategyManager`;
- это не notifications / analytics / validation line;
- dashboard / UI line не входит в scope.

---

## Phase 15 Protection / Supervisor Foundation

`Phase 15` доведена до closure-ready состояния как узкая, production-compatible линия:
`Protection / Supervisor Foundation`.

В реализованный scope `P_15` входят:

- typed protection / supervisor contracts;
- protection decision / status / validity semantics;
- typed protection event vocabulary;
- explicit `ProtectionRuntime`;
- deterministic `ProtectionContext` assembly внутри protection layer;
- один узкий deterministic contour с `PROTECT` / `HALT` / `FREEZE`;
- narrow composition-root integration через existing portfolio-governor truth;
- operator-visible protection diagnostics / readiness / degraded truth;
- lifecycle semantics для protection candidate truth:
  - `CANDIDATE`
  - `PROTECTED`
  - `HALTED`
  - `FROZEN`
  - `INVALIDATED`
  - `EXPIRED`
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения closure-ready `P_15`:

- это не `OMS`;
- это не cancel / modify lifecycle;
- это не broad close-all / liquidation engine;
- это не notifications / approval workflow line;
- это не broader `StrategyManager`;
- это не analytics / validation line;
- dashboard / UI line не входит в scope.

---

## Phase 16 OMS Foundation

`Phase 16` доведена до closure-ready состояния как узкая, production-compatible линия:
`OMS Foundation`.

В реализованный scope `P_16` входят:

- typed OMS contracts;
- order-lifecycle / order-state semantics;
- typed OMS event vocabulary;
- explicit `OmsRuntime`;
- deterministic `OmsContext` assembly внутри OMS layer;
- centralized order-state / order-registry truth;
- query/state-first surface для active / historical orders;
- narrow composition-root integration через existing execution truth;
- operator-visible OMS diagnostics / readiness / degraded truth;
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения closure-ready `P_16`:

- это не liquidation line;
- это не cancel-all / emergency ops line;
- это не notifications / approval workflow line;
- это не broader ops platform;
- это не broader `StrategyManager`;
- это не validation / dashboard line;
- persistence-first OMS platform не входит в текущий scope.

---

## Phase 17 Strategy Manager / Workflow Foundation

`Phase 17` доведена до closure-ready состояния как узкая, production-compatible линия:
`Strategy Manager / Workflow Foundation`.

В реализованный scope `P_17` входят:

- package foundation в `src/cryptotechnolog/manager`;
- typed manager / workflow contracts;
- explicit `ManagerRuntime`;
- deterministic `ManagerContext` assembly внутри manager layer;
- один узкий deterministic coordination contour с `COORDINATED` / `ABSTAINED`;
- query/state-first manager surface;
- narrow composition-root integration через existing typed truths:
  - `opportunity`
  - `orchestration`
  - `position_expansion`
  - `portfolio_governor`
  - `protection`
- operator-visible manager diagnostics / readiness / degraded truth;
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения closure-ready `P_17`:

- это не `Execution`;
- это не `OMS`;
- это не `Portfolio Governor` или `Protection`;
- это не notifications / approval workflow line;
- это не liquidation / ops line;
- это не analytics / validation line;
- это не dashboard / UI line;
- это не full multi-strategy platform;
- broader central-platform ownership semantics не входят в текущий scope.

---

## Phase 18 Validation Foundation

`Phase 18` доведена до closure-ready состояния как узкая, production-compatible линия:
`Validation Foundation`.

В реализованный scope `P_18` входят:

- package foundation в `src/cryptotechnolog/validation`;
- typed validation / review contracts;
- explicit `ValidationRuntime`;
- deterministic `ValidationContext` assembly внутри validation layer;
- один узкий deterministic validation contour с `VALIDATED` / `ABSTAINED`;
- query/state-first validation surface;
- narrow composition-root integration через existing typed truths:
  - `manager`
  - `portfolio_governor`
  - `protection`
  - optional adjacent `oms`
- operator-visible validation diagnostics / readiness / degraded truth;
- unit/integration verification на relevant runtime/bootstrap subset.

Честные ограничения closure-ready `P_18`:

- это не analytics / reporting platform;
- это не full benchmark / optimization / Monte Carlo / walk-forward line;
- это не backtesting engine;
- это не paper trading system;
- это не dashboard / UI line;
- это не notifications / approval workflow line;
- это не liquidation / ops line;
- это не `Execution`;
- это не `OMS`;
- это не `Manager`;
- broader strategy comparison / ranking ownership не входит в текущий scope.

---

## Структура проекта

```text
CRYPTOTEHNOLOG/
├── src/                           # Python source code
│   ├── config/                   # Configuration management
│   ├── core/                     # Core utilities and runtime helpers
│   ├── risk/                     # Risk engine
│   ├── market_data/              # Raw market data layer
│   ├── analysis/                 # Shared derived analysis truth
│   ├── intelligence/             # Intelligence layer
│   ├── signals/                  # Signal generation foundation
│   ├── execution/                # Order execution
│   ├── strategy/                 # Strategy foundation (done)
│   ├── opportunity/              # Opportunity / selection foundation (done)
│   ├── orchestration/            # Strategy orchestration / meta foundation (done)
│   ├── position_expansion/       # Position expansion foundation (done)
│   ├── portfolio_governor/       # Portfolio governor / capital governance foundation (done)
│   ├── protection/               # Protection / supervisor foundation (closure-ready)
│   ├── oms/                      # OMS foundation (closure-ready)
│   ├── manager/                  # Strategy manager / workflow foundation (closure-ready)
│   ├── validation/               # Validation foundation (closure-ready)
│   └── observability/            # Monitoring & metrics
├── crates/                       # Rust workspace crates
│   ├── eventbus/                 # High-performance event bus
│   ├── risk-ledger/              # Double-entry risk ledger
│   ├── audit-chain/              # Cryptographic audit chain
│   ├── execution-core/           # Low-latency execution
│   ├── ffi/                      # Python FFI bindings
│   └── common/                   # Shared types and utilities
├── tests/                        # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── e2e/                     # End-to-end tests
│   └── fixtures/                # Test data
├── docs/                         # Documentation
│   ├── adr/                     # Architecture decision records
│   ├── roadmap/                 # Roadmap, deferred scope, idea registry
│   ├── architecture/            # Architecture docs
│   ├── runbooks/                # Operational procedures
│   └── api/                     # API documentation
├── prompts/
│   ├── plan/                    # Authoritative phase plans and phase results
│   ├── reference/               # Historical/reference prompt archive
│   └── CHECKLISTS/              # Supporting checklists
├── config/                       # Configuration files
│   ├── dev/                     # Development config
│   └── prod/                    # Production config
├── scripts/                      # Automation scripts
│   ├── deployment/              # Deployment scripts
│   └── testing/                 # Testing scripts
├── .github/                      # GitHub configuration
│   ├── workflows/               # CI/CD workflows
│   └── pull_request_template/
├── docker-compose.yml            # Docker services
├── Dockerfile                    # Python service container
├── Makefile                      # Common commands
├── pyproject.toml                # Python project config
├── requirements.txt              # Python dependencies
└── README.md                     # Этот файл
```

### Truth и planning-дисциплина

- `prompts/plan/` хранит authoritative phase plans и phase result documents
- `prompts/reference/` хранит historical/reference prompt archives и roadmap-only материалы
- `docs/roadmap/` хранит deferred scope, long-range ideas и roadmap coordination documents
- Текущая implementation truth определяется только через `README.md`, `prompts/plan/*`, `docs/adr/*` и фактический код
- Historical prompts сохраняются, чтобы идеи не терялись, но они не являются implementation truth до нормализации в текущий phase plan
- Памятка по работе с этой схемой: [WORKING_WITH_PHASE_TRUTH.md](/D:/CRYPTOTEHNOLOG/docs/roadmap/WORKING_WITH_PHASE_TRUTH.md)
- Шаблоны рабочих сообщений для Codex: [CODEX_MESSAGE_TEMPLATES.md](/D:/CRYPTOTEHNOLOG/docs/roadmap/CODEX_MESSAGE_TEMPLATES.md)
- Предварительное распределение future lines: [FUTURE_PHASE_ALLOCATION.md](/D:/CRYPTOTEHNOLOG/docs/roadmap/FUTURE_PHASE_ALLOCATION.md)

---

## Тестирование

### Требования к покрытию

- **Critical Path** (`Risk Engine`, `Execution`): >95%
- **Business Logic** (`Signals`, `Intelligence`, `Strategies`): >90%
- **Infrastructure** (`Event Bus`, `Config`, `Bootstrap`): >85%
- **UI / Dashboard**: >70%

### Запуск тестов

```bash
# Все тесты
pytest

# Только unit tests
pytest tests/unit/

# Только integration tests
pytest tests/integration/

# С coverage
pytest --cov=src --cov-report=html

# Конкретный файл тестов
pytest tests/unit/test_settings.py
```

---

## Безопасность

- **Secrets Management**: `Infisical` или `.env` для чувствительных данных
- **Configuration Integrity**: криптографические подписи для конфигов
- **Audit Trail**: immutable cryptographic audit chain
- **Network Security**: TLS для всех внешних соединений
- **API Permissions**: только `Read/Trade`, без withdrawal permissions

---

## CI/CD

### GitHub Actions

- **On Push**: тесты, linting, type checking
- **On PR**: дополнительные security scan и review checks
- **On Merge to Main**: release/tag/deployment preparation

### Branch Protection

- `main`: protected, requires PR + approval + passing CI
- `develop`: integration branch, requires passing CI
- `feature/*`: feature branches

---

## Вклад в проект

1. Создать feature branch от актуальной базовой ветки
2. Внести изменения вместе с тестами
3. Убедиться, что проверки и coverage не деградируют
4. Подготовить PR с описанием
5. Дождаться approval и passing CI
6. Выполнить merge в целевую ветку по принятой phase discipline

---

## Лицензия

Проприетарное ПО. Все права защищены.

---

## Поддержка

Для вопросов и инцидентов:

- смотреть `docs/runbooks/`
- использовать `docs/roadmap/` для roadmap/deferred truth
- использовать `prompts/plan/` для authoritative phase truth

---

**Версия:** `v1.18.0`  
**Последнее обновление:** `2026-03-23`
