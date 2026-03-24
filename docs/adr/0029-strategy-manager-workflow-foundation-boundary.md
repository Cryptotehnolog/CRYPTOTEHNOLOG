# Strategy Manager / Workflow Foundation как узкий coordination layer

**Дата:** 2026-03-23  
**Статус:** Принято  

## Контекст

После реализации `P_17` проект уже имеет последовательную chain of truth:

- `Execution Foundation`;
- `OMS Foundation`;
- `Opportunity / Selection Foundation`;
- `Strategy Orchestration / Meta Layer`;
- `Position Expansion Foundation`;
- `Portfolio Governor / Capital Governance Foundation`;
- `Protection / Supervisor Foundation`;
- единый production composition root и runtime truth discipline;
- operator-visible diagnostics / readiness / degraded semantics.

На этом фоне `P_17` открывает новый слой:

- `Strategy Manager / Workflow Foundation`.

Но именно на этой границе historical lineage особенно опасна:

- historical `Strategy Manager` prompt тянет manager line в сторону broad central-platform ownership;
- historical workflow expectations тянут её в сторону notifications / approval workflow platform;
- historical operational expectations размывают границу между manager contour и liquidation / ops line;
- historical analytics expectations тянут manager в сторону validation / performance / dashboard cluster;
- historical multi-strategy expectations создают ложное ожидание full policy ownership уже на foundation step.

Без отдельного ADR `P_17` легко начать трактовать слишком широко:

- как owner `Execution` и `OMS`;
- как broader workflow engine;
- как approval / notification platform;
- как liquidation / ops coordination layer;
- как analytics / validation hub;
- как full multi-strategy platform;
- как верхнеуровневый central brain всей платформы.

Phase plan и код `P_17` уже удерживают scope узко, но до formal finalization нужен отдельный
architecture lock, который:

- формально закрепит ownership boundary;
- зафиксирует relationship manager layer с upstream runtime truths;
- отделит manager line от `OMS`, `Portfolio Governor`, `Protection` и future operational lines;
- не позволит переосмыслить фазу задним числом после релиза.

## Рассмотренные альтернативы

1. Финализировать `P_17` без нового ADR, полагаясь только на `README.md`, `P_17.md` и код.
2. Описать `Strategy Manager / Workflow Foundation` как ранний central-platform layer с ownership над workflow, `OMS`, approvals, notifications и multi-strategy policy.
3. Закрепить `P_17` отдельным ADR как узкий coordination layer поверх existing typed truths, с явным исключением `Execution`, `OMS`, `Portfolio Governor`, `Protection`, notifications, liquidation, validation и broader multi-strategy ownership.

## Решение

Принят вариант 3.

### 1. `Strategy Manager / Workflow Foundation` является narrow coordination layer

- `Manager` — это отдельный workflow-coordination layer внутри текущей package discipline проекта.
- Этот слой не является новым central control-plane universe.
- Этот слой не владеет всей platform-control semantics.
- Его задача в `P_17` — узко и детерминированно координировать existing typed truth и формировать narrow manager workflow state.

### 2. Manager layer потребляет only existing typed truths

- `Manager` потребляет upstream truth через:
  - `OpportunitySelectionCandidate`;
  - `OrchestrationDecisionCandidate`;
  - `PositionExpansionCandidate`;
  - `PortfolioGovernorCandidate`;
  - `ProtectionSupervisorCandidate`.
- Bootstrap / composition root не собирает `ManagerContext`.
- Bootstrap только wiring-ит existing typed truths в `ManagerRuntime`.
- Внутренняя сборка `ManagerContext`, lifecycle semantics и manager workflow truth принадлежат manager layer.

Это означает:

- `Manager` не тянет ownership у `Execution`;
- `Manager` не тянет ownership у `OMS`;
- `Manager` не подменяет `Opportunity` / `Orchestration`;
- `Manager` не подменяет `Position Expansion`;
- `Manager` не подменяет `Portfolio Governor`;
- `Manager` не подменяет `Protection`.

### 3. Реальный scope `P_17`

В scope `P_17` входят только:

- manager / workflow contracts;
- explicit runtime boundary;
- deterministic `ManagerContext` assembly;
- narrow coordination contour;
- query/state-first manager surface;
- narrow diagnostics / readiness / degraded truth;
- narrow composition-root integration;
- typed local event vocabulary manager layer.

### 4. Что `P_17` не владеет

`Strategy Manager / Workflow Foundation` в рамках `P_17` не владеет:

- `Execution`;
- `OMS`;
- `Portfolio Governor`;
- `Protection`;
- notifications / PagerDuty / SMS platform;
- approval workflow platform;
- liquidation / ops platform;
- broader operational command layer;
- analytics / validation;
- dashboard line;
- full multi-strategy platform;
- broader central-platform ownership semantics.

Если такие линии понадобятся, они открываются отдельно и не считаются скрытым продолжением `P_17`.

### 5. Как проходит граница с соседними линиями

#### Upstream: `Opportunity`

- `Opportunity` владеет selection truth.
- `Manager` не переписывает selection semantics и не принимает роль ranking / selection engine.
- `Manager` использует selection truth как один из upstream inputs.

#### Upstream: `Orchestration`

- `Orchestration` владеет narrow meta-decision truth.
- `Manager` не объявляет orchestration своей внутренней подсистемой.
- `Manager` строится поверх orchestration truth, а не вместо неё.

#### Upstream: `Position Expansion`

- `Position Expansion` владеет add-to-position contour.
- `Manager` не получает ownership над expansion policy.

#### Upstream: `Portfolio Governor` и `Protection`

- `Portfolio Governor` владеет capital-admission truth.
- `Protection` владеет narrow supervisory truth.
- `Manager` может координировать workflow поверх этих truths, но не получает ownership над capital governance, supervisory decisions, liquidation или approval semantics.

#### Adjacent / downstream: `OMS`

- `OMS` владеет order-state / lifecycle truth.
- `Manager` может читать downstream OMS truth только как adjacent state, если это понадобится в future narrow follow-up.
- `Manager` не получает ownership над order lifecycle только потому, что координирует workflow-level path.

#### Future lines: notifications / approval / liquidation / validation

- Operator notifications, human approval routing, escalation semantics, liquidation / ops и validation flows не принадлежат manager foundation.
- `Manager` может выдавать workflow truth, но не обязана сама превращать её в alerting, approval, liquidation или validation platform.

### 6. Почему этот ADR нужен до formal finalization `P_17`

Этот ADR нужен именно до formal finalization, потому что:

- `P_17` находится на высокой risk-of-scope-inflation boundary;
- исторические материалы создают ложное ожидание central-manager semantics уже на foundation step;
- после релиза ADR выглядел бы как ретроспективное оправдание уже принятого решения;
- до релиза он работает как честный architecture lock, который ограничивает interpretation drift.

Следовательно:

- `P_17` не должна финализироваться как `v1.17.0`, пока эта boundary не зафиксирована отдельным ADR.

## Последствия

- **Плюсы:** formal finalization `P_17` получает жёсткую архитектурную рамку и перестаёт зависеть только от phase-plan wording.
- **Плюсы:** граница между manager layer, `OMS`, `Portfolio Governor`, `Protection` и future operational lines становится явной.
- **Плюсы:** future implementation steps не смогут честно расширять `P_17` в notifications, approval workflow, liquidation, validation или full multi-strategy platform без открытия отдельной линии.
- **Минусы:** subsequent steps требуют большей дисциплины и не позволяют "удобно" добавлять broader workflow behavior под тем же phase label.
- **Минусы:** если позже понадобится richer manager behavior, его придётся оформлять как новый scope, а не как тихое расширение `P_17`.

## Что становится обязательным для formal finalization `P_17`

1. Читать `Strategy Manager / Workflow Foundation` только как narrow coordination layer.
2. Не трактовать `P_17` как `Execution`, `OMS`, notifications / approval workflow, liquidation / ops, validation или dashboard line.
3. Сохранять existing typed truths как единственные upstream contracts текущей реализации.
4. Любой follow-up, который требует order-lifecycle ownership, human-approval routing, alert delivery, liquidation orchestration или broad multi-strategy policy ownership, открывать отдельной line после `P_17`.

## Связанные ADR

- Связан с [0024-production-alignment-composition-root-and-runtime-truth.md](D:/CRYPTOTEHNOLOG/docs/adr/0024-production-alignment-composition-root-and-runtime-truth.md)
- Логически продолжает [0028-protection-supervisor-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0028-protection-supervisor-foundation-boundary.md)
- Логически продолжает [P_12.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_12.md), [P_14.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_14.md), [P_15.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_15.md), [P_16.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_16.md) и [P_17.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_17.md)
- Ограничивает interpretation drift относительно historical/reference prompt [15_ФАЗА_14_STRATEGY_MANAGER_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/15_%D0%A4%D0%90%D0%97%D0%90_14_STRATEGY_MANAGER_PROMPT.md)
