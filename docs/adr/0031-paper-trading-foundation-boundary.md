# Paper Trading Foundation как узкий rehearsal / controlled-simulation layer

**Дата:** 2026-03-24  
**Статус:** Принято  

## Контекст

После реализации `P_19` проект уже имеет последовательную chain of truth:

- `Execution Foundation`;
- `OMS Foundation`;
- `Opportunity / Selection Foundation`;
- `Strategy Orchestration / Meta Layer`;
- `Position Expansion Foundation`;
- `Portfolio Governor / Capital Governance Foundation`;
- `Protection / Supervisor Foundation`;
- `Strategy Manager / Workflow Foundation`;
- `Validation Foundation`;
- единый production composition root и runtime truth discipline;
- operator-visible diagnostics / readiness / degraded semantics.

На этом фоне `P_19` открывает новый слой:

- `Paper Trading Foundation`.

Но именно на этой границе historical lineage особенно опасна:

- historical paper-trading expectations тянут paper line в сторону broad controlled-simulation platform;
- historical analytics / reporting expectations тянут её в сторону comparison / reporting hub;
- historical backtesting expectations тянут её в сторону replay / simulation engine;
- historical dashboard expectations размывают границу между paper contour и operator-facing UI surface;
- historical operational expectations создают ложное ожидание notifications / approval / liquidation / ops ownership;
- adjacent `OMS` truth легко начать трактовать как скрытое re-ownership order lifecycle.

Без отдельного ADR `P_19` легко начать трактовать слишком широко:

- как owner `Execution` semantics;
- как owner `OMS` lifecycle;
- как owner workflow-coordination / review semantics, которые уже принадлежат `Manager` и `Validation`;
- как analytics / reporting platform;
- как backtesting / replay engine;
- как dashboard-led operator surface;
- как notifications / approval / liquidation / ops line;
- как broader comparison / simulation platform;
- как full virtual portfolio / exchange simulation platform.

Phase plan и код `P_19` уже удерживают scope узко, но до formal finalization нужен отдельный
architecture lock, который:

- формально закрепит ownership boundary;
- зафиксирует relationship paper layer с upstream / adjacent runtime truths;
- отделит paper line от future analytics / reporting / backtesting / dashboard / ops lines;
- не позволит переосмыслить фазу задним числом после релиза.

## Рассмотренные альтернативы

1. Финализировать `P_19` без нового ADR, полагаясь только на `README.md`, `P_19.md` и код.
2. Описать `Paper Trading Foundation` как ранний simulation / comparison hub с ownership над virtual execution, reporting и broader rehearsal semantics.
3. Закрепить `P_19` отдельным ADR как узкий rehearsal / controlled-simulation layer поверх existing typed truths, с явным исключением `Execution`, `OMS`, `Manager`, `Validation`, analytics, backtesting, dashboard и ops ownership.

## Решение

Принят вариант 3.

### 1. `Paper Trading Foundation` является narrow rehearsal / controlled-simulation layer

- `Paper` — это отдельный rehearsal / controlled-simulation layer внутри текущей package discipline проекта.
- Этот слой не является analytics platform.
- Этот слой не является reporting platform.
- Этот слой не является backtesting / replay engine.
- Этот слой не является dashboard / operator surface.
- Этот слой не является notifications / approval / liquidation / ops platform.
- Его задача в `P_19` — узко и детерминированно строить paper rehearsal state поверх already existing typed truths.

### 2. Paper layer потребляет only existing typed truths

- `Paper` потребляет upstream / adjacent truth через:
  - `ManagerWorkflowCandidate`;
  - `ValidationReviewCandidate`;
  - optional adjacent `OmsOrderRecord`.
- Bootstrap / composition root не собирает `PaperContext`.
- Bootstrap только wiring-ит existing typed truths в `PaperRuntime`.
- Внутренняя сборка `PaperContext`, lifecycle semantics и paper rehearsal truth принадлежат paper layer.

Это означает:

- `Paper` не тянет ownership у `Execution`;
- `Paper` не тянет ownership у `OMS`;
- `Paper` не тянет ownership у `Manager`;
- `Paper` не тянет ownership у `Validation`.

### 3. Реальный scope `P_19`

В scope `P_19` входят только:

- paper / rehearsal contracts;
- explicit runtime boundary;
- deterministic `PaperContext` assembly;
- narrow rehearsal contour;
- query/state-first paper surface;
- narrow diagnostics / readiness / degraded truth;
- narrow composition-root integration;
- typed local event vocabulary paper layer.

### 4. Что `P_19` не владеет

`Paper Trading Foundation` в рамках `P_19` не владеет:

- `Execution`;
- `OMS`;
- `Manager`;
- `Validation`;
- analytics / reporting platform;
- backtesting / replay engine;
- dashboard / operator line;
- notifications / PagerDuty / SMS platform;
- approval workflow platform;
- liquidation / ops platform;
- broader comparison / simulation platform;
- full virtual portfolio / exchange simulation platform.

Если такие линии понадобятся, они открываются отдельно и не считаются скрытым продолжением `P_19`.

### 5. Как проходит граница с соседними и будущими линиями

#### Upstream: `Manager`

- `Manager` владеет narrow workflow-coordination truth.
- `Paper` не переписывает workflow semantics и не принимает роль manager layer.
- `Paper` использует manager truth как один из upstream inputs.

#### Upstream: `Validation`

- `Validation` владеет narrow review / evaluation truth.
- `Paper` не подменяет validation semantics и не принимает роль review layer.
- `Paper` строится поверх validation truth, а не вместо неё.

#### Adjacent: `OMS`

- `OMS` владеет order-state / lifecycle truth.
- `Paper` может читать optional adjacent OMS truth как один из rehearsal inputs.
- `Paper` не получает ownership над order lifecycle только потому, что использует adjacent OMS state при rehearsal.

#### Future lines: analytics / reporting

- Analytics, reporting, benchmarking и richer comparison outputs не принадлежат paper foundation.
- `Paper` может формировать rehearsal truth, но не обязана сама превращать её в analytics / reporting platform.

#### Future lines: backtesting / replay

- Historical replay, broader simulation, optimization и full backtesting semantics не принадлежат `P_19`.
- Эти направления открываются как отдельные future lines и не являются скрытым расширением paper foundation.

#### Future lines: dashboard / notifications / ops

- Dashboard-led operator surface, notifications / approval routing и ops / liquidation semantics не принадлежат paper foundation.
- `Paper` может выдавать rehearsal truth, но не обязана сама превращать её в dashboard, alerting или ops platform.

### 6. Почему этот ADR нужен до formal finalization `P_19`

Этот ADR нужен именно до formal finalization, потому что:

- `P_19` находится на высокой risk-of-scope-inflation boundary;
- historical materials создают ложное ожидание broader simulation / comparison / operator semantics уже на foundation step;
- после релиза ADR выглядел бы как ретроспективное оправдание уже принятого решения;
- до релиза он работает как честный architecture lock, который ограничивает interpretation drift.

Следовательно:

- `P_19` не должна финализироваться как `v1.19.0`, пока эта boundary не зафиксирована отдельным ADR.

## Последствия

- **Плюсы:** formal finalization `P_19` получает жёсткую архитектурную рамку и перестаёт зависеть только от phase-plan wording.
- **Плюсы:** граница между paper layer, `Manager`, `Validation`, `OMS` и future analytics / reporting / backtesting / dashboard / ops lines становится явной.
- **Плюсы:** future implementation steps не смогут честно расширять `P_19` в analytics, replay, dashboard, notifications или ops без открытия отдельной линии.
- **Минусы:** subsequent steps требуют большей дисциплины и не позволяют "удобно" добавлять broader simulation / comparison behavior под тем же phase label.
- **Минусы:** если позже понадобится richer paper-supporting behavior, его придётся оформлять как новый scope, а не как тихое расширение `P_19`.

## Что становится обязательным для formal finalization `P_19`

1. Читать `Paper Trading Foundation` только как narrow rehearsal / controlled-simulation layer.
2. Не трактовать `P_19` как `Execution`, `OMS`, `Manager`, `Validation`, analytics / reporting, backtesting / replay, dashboard / operator, notifications / approval или ops line.
3. Сохранять existing typed truths как единственные upstream / adjacent contracts текущей реализации.
4. Любой follow-up, который требует virtual execution ownership, order-lifecycle ownership, analytics / reporting platform semantics, replay / backtesting engine behavior, dashboard-led operator workflows или broader simulation platform ownership, открывать отдельной line после `P_19`.

## Связанные ADR

- Связан с [0024-production-alignment-composition-root-and-runtime-truth.md](D:/CRYPTOTEHNOLOG/docs/adr/0024-production-alignment-composition-root-and-runtime-truth.md)
- Логически продолжает [0029-strategy-manager-workflow-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0029-strategy-manager-workflow-foundation-boundary.md)
- Логически продолжает [0030-validation-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0030-validation-foundation-boundary.md)
- Логически продолжает [P_17.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_17.md), [P_18.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_18.md) и [P_19.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_19.md)
- Ограничивает interpretation drift относительно historical/reference prompts:
  - [16_ФАЗА_15_PERFORMANCE_ANALYTICS_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/16_%D0%A4%D0%90%D0%97%D0%90_15_PERFORMANCE_ANALYTICS_PROMPT.md)
  - [17_ФАЗА_16_BACKTESTING_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/17_%D0%A4%D0%90%D0%97%D0%90_16_BACKTESTING_PROMPT.md)
  - [18_ФАЗА_17_PAPER_TRADING_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/18_%D0%A4%D0%90%D0%97%D0%90_17_PAPER_TRADING_PROMPT.md)
