# Validation Foundation как узкий review / evaluation layer

**Дата:** 2026-03-23  
**Статус:** Принято  

## Контекст

После реализации `P_18` проект уже имеет последовательную chain of truth:

- `Execution Foundation`;
- `OMS Foundation`;
- `Opportunity / Selection Foundation`;
- `Strategy Orchestration / Meta Layer`;
- `Position Expansion Foundation`;
- `Portfolio Governor / Capital Governance Foundation`;
- `Protection / Supervisor Foundation`;
- `Strategy Manager / Workflow Foundation`;
- единый production composition root и runtime truth discipline;
- operator-visible diagnostics / readiness / degraded semantics.

На этом фоне `P_18` открывает новый слой:

- `Validation Foundation`.

Но именно на этой границе historical lineage особенно опасна:

- historical performance/analytics expectations тянут validation line в сторону broad analytics / reporting platform;
- historical backtesting expectations тянут её в сторону simulation / replay / optimization engine;
- historical paper-trading expectations тянут её в сторону live-like virtual execution platform;
- historical dashboard expectations размывают границу между validation contour и operator-facing UI surface;
- historical operational expectations создают ложное ожидание approval / notification / ops ownership;
- adjacent `OMS` truth легко начать трактовать как скрытое re-ownership order lifecycle.

Без отдельного ADR `P_18` легко начать трактовать слишком широко:

- как owner analytics / reporting semantics;
- как owner benchmark / optimization / Monte Carlo / walk-forward platform;
- как backtesting engine;
- как paper trading system;
- как dashboard-led review surface;
- как approval / notification line;
- как liquidation / ops support layer;
- как owner broader strategy comparison / ranking semantics;
- как evaluation hub, который подменяет `Execution`, `OMS` или `Manager`.

Phase plan и код `P_18` уже удерживают scope узко, но до formal finalization нужен отдельный
architecture lock, который:

- формально закрепит ownership boundary;
- зафиксирует relationship validation layer с upstream / adjacent runtime truths;
- отделит validation line от future analytics / reporting / backtesting / paper-trading lines;
- не позволит переосмыслить фазу задним числом после релиза.

## Рассмотренные альтернативы

1. Финализировать `P_18` без нового ADR, полагаясь только на `README.md`, `P_18.md` и код.
2. Описать `Validation Foundation` как ранний analytics / review hub с ownership над reporting, benchmarking, paper/live comparison и broader evaluation platform semantics.
3. Закрепить `P_18` отдельным ADR как узкий review / evaluation layer поверх existing typed truths, с явным исключением analytics / reporting / backtesting / paper trading / dashboard / notifications / ops ownership.

## Решение

Принят вариант 3.

### 1. `Validation Foundation` является narrow review / evaluation layer

- `Validation` — это отдельный review / evaluation layer внутри текущей package discipline проекта.
- Этот слой не является analytics platform.
- Этот слой не является reporting platform.
- Этот слой не является backtesting engine.
- Этот слой не является paper trading system.
- Его задача в `P_18` — узко и детерминированно оценивать existing typed truths и формировать narrow validation review state.

### 2. Validation layer потребляет only existing typed truths

- `Validation` потребляет upstream / adjacent truth через:
  - `ManagerWorkflowCandidate`;
  - `PortfolioGovernorCandidate`;
  - `ProtectionSupervisorCandidate`;
  - optional adjacent `OmsOrderRecord`.
- Bootstrap / composition root не собирает `ValidationContext`.
- Bootstrap только wiring-ит existing typed truths в `ValidationRuntime`.
- Внутренняя сборка `ValidationContext`, lifecycle semantics и validation review truth принадлежат validation layer.

Это означает:

- `Validation` не тянет ownership у `Execution`;
- `Validation` не тянет ownership у `OMS`;
- `Validation` не тянет ownership у `Manager`;
- `Validation` не подменяет `Portfolio Governor`;
- `Validation` не подменяет `Protection`.

### 3. Реальный scope `P_18`

В scope `P_18` входят только:

- validation / review contracts;
- explicit runtime boundary;
- deterministic `ValidationContext` assembly;
- narrow validation contour;
- query/state-first validation surface;
- narrow diagnostics / readiness / degraded truth;
- narrow composition-root integration;
- typed local event vocabulary validation layer.

### 4. Что `P_18` не владеет

`Validation Foundation` в рамках `P_18` не владеет:

- `Execution`;
- `OMS`;
- `Manager`;
- analytics / reporting platform;
- benchmark / optimization / Monte Carlo / walk-forward platform;
- backtesting engine;
- paper trading system;
- dashboard line;
- notifications / PagerDuty / SMS platform;
- approval workflow platform;
- liquidation / ops platform;
- broader strategy comparison / ranking ownership.

Если такие линии понадобятся, они открываются отдельно и не считаются скрытым продолжением `P_18`.

### 5. Как проходит граница с соседними и будущими линиями

#### Upstream: `Manager`

- `Manager` владеет narrow workflow-coordination truth.
- `Validation` не переписывает workflow semantics и не принимает роль manager layer.
- `Validation` использует manager truth как один из upstream inputs.

#### Upstream: `Portfolio Governor` и `Protection`

- `Portfolio Governor` владеет capital-admission truth.
- `Protection` владеет narrow supervisory truth.
- `Validation` может строить review state поверх этих truths, но не получает ownership над capital governance, supervisory decisions или operational control semantics.

#### Adjacent: `OMS`

- `OMS` владеет order-state / lifecycle truth.
- `Validation` может читать optional adjacent OMS truth как один из review inputs.
- `Validation` не получает ownership над order lifecycle только потому, что использует adjacent OMS state при review.

#### Future lines: analytics / reporting

- Analytics, reporting, benchmarking и richer evaluation outputs не принадлежат validation foundation.
- `Validation` может формировать review truth, но не обязана сама превращать её в analytics / reporting platform.

#### Future lines: backtesting / paper trading

- Historical replay, simulation, virtual execution и paper/live comparison не принадлежат `P_18`.
- Эти направления открываются как отдельные future lines и не являются скрытым расширением validation foundation.

#### Future lines: dashboard / notifications / ops

- Dashboard-led operator surface, notifications / approval routing и ops / liquidation semantics не принадлежат validation foundation.
- `Validation` может выдавать review truth, но не обязана сама превращать её в dashboard, alerting или ops platform.

### 6. Почему этот ADR нужен до formal finalization `P_18`

Этот ADR нужен именно до formal finalization, потому что:

- `P_18` находится на высокой risk-of-scope-inflation boundary;
- historical materials создают ложное ожидание broad validation / analytics / simulation semantics уже на foundation step;
- после релиза ADR выглядел бы как ретроспективное оправдание уже принятого решения;
- до релиза он работает как честный architecture lock, который ограничивает interpretation drift.

Следовательно:

- `P_18` не должна финализироваться как `v1.18.0`, пока эта boundary не зафиксирована отдельным ADR.

## Последствия

- **Плюсы:** formal finalization `P_18` получает жёсткую архитектурную рамку и перестаёт зависеть только от phase-plan wording.
- **Плюсы:** граница между validation layer, `Manager`, `Portfolio Governor`, `Protection`, `OMS` и future analytics / reporting / backtesting / paper-trading lines становится явной.
- **Плюсы:** future implementation steps не смогут честно расширять `P_18` в analytics, reporting, simulation, dashboard, notifications или ops без открытия отдельной линии.
- **Минусы:** subsequent steps требуют большей дисциплины и не позволяют "удобно" добавлять broader review / evaluation behavior под тем же phase label.
- **Минусы:** если позже понадобится richer validation-supporting behavior, его придётся оформлять как новый scope, а не как тихое расширение `P_18`.

## Что становится обязательным для formal finalization `P_18`

1. Читать `Validation Foundation` только как narrow review / evaluation layer.
2. Не трактовать `P_18` как analytics / reporting / backtesting / paper trading / dashboard / notifications / ops line.
3. Сохранять existing typed truths как единственные upstream / adjacent contracts текущей реализации.
4. Любой follow-up, который требует benchmarking platform semantics, historical replay, virtual execution, dashboard-led operator workflows или broader strategy comparison ownership, открывать отдельной line после `P_18`.

## Связанные ADR

- Связан с [0024-production-alignment-composition-root-and-runtime-truth.md](D:/CRYPTOTEHNOLOG/docs/adr/0024-production-alignment-composition-root-and-runtime-truth.md)
- Логически продолжает [0028-protection-supervisor-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0028-protection-supervisor-foundation-boundary.md)
- Логически продолжает [0029-strategy-manager-workflow-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0029-strategy-manager-workflow-foundation-boundary.md)
- Логически продолжает [P_16.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_16.md), [P_17.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_17.md) и [P_18.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_18.md)
- Ограничивает interpretation drift относительно historical/reference prompts:
  - [16_ФАЗА_15_PERFORMANCE_ANALYTICS_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/16_%D0%A4%D0%90%D0%97%D0%90_15_PERFORMANCE_ANALYTICS_PROMPT.md)
  - [17_ФАЗА_16_BACKTESTING_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/17_%D0%A4%D0%90%D0%97%D0%90_16_BACKTESTING_PROMPT.md)
  - [18_ФАЗА_17_PAPER_TRADING_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/18_%D0%A4%D0%90%D0%97%D0%90_17_PAPER_TRADING_PROMPT.md)
