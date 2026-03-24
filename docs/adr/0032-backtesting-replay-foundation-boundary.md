# Backtesting / Replay Foundation как узкий replay/backtest layer

**Дата:** 2026-03-24  
**Статус:** Принято  

## Контекст

После реализации foundation шагов `P_20` проект уже имеет последовательную chain of truth:

- `Execution Foundation`;
- `OMS Foundation`;
- `Opportunity / Selection Foundation`;
- `Strategy Orchestration / Meta Layer`;
- `Position Expansion Foundation`;
- `Portfolio Governor / Capital Governance Foundation`;
- `Protection / Supervisor Foundation`;
- `Strategy Manager / Workflow Foundation`;
- `Validation Foundation`;
- `Paper Trading Foundation`;
- единый production composition root и runtime truth discipline;
- уже существующий `backtest` contour в репозитории, исторически более широкий, чем фактическая phase truth `P_20`.

На этом фоне `P_20` открывает новый слой:

- `Backtesting / Replay Foundation`.

Но именно на этой границе historical lineage особенно опасна:

- historical backtesting expectations тянут replay line в сторону broad simulation / research platform;
- historical analytics / reporting expectations тянут её в сторону comparison / ranking / reporting hub;
- historical dashboard expectations размывают границу между replay contour и operator-facing surface;
- historical historical-data expectations тянут её в сторону full data platform ownership;
- historical optimization expectations тянут её в сторону parameter search / Monte Carlo / walk-forward lab;
- legacy `ReplayEngine` и `EventRecorder` легко начать трактовать как authoritative Phase 20 surface;
- replay path легко ошибочно трактовать как hidden simulated owner для `Execution` / `OMS`.

Без отдельного ADR `P_20` легко начать трактовать слишком широко:

- как owner `Validation` semantics;
- как owner `Paper` rehearsal semantics;
- как simulated `Execution` platform;
- как simulated `OMS` / order-lifecycle platform;
- как analytics / reporting platform;
- как comparison / ranking platform;
- как dashboard-led operator surface;
- как full historical data platform;
- как optimization / Monte Carlo / walk-forward / research-lab line;
- как full virtual portfolio / exchange simulation platform.

Phase plan и код `P_20` уже удерживают scope узко, но до formal finalization нужен отдельный
architecture lock, который:

- формально закрепит ownership boundary;
- зафиксирует relationship replay layer с соседними implemented foundations;
- отделит authoritative replay surface от legacy compatibility contour;
- отделит `P_20` от future analytics / historical-data / optimization lines;
- не позволит переосмыслить фазу задним числом после релиза.

## Рассмотренные альтернативы

1. Финализировать `P_20` без нового ADR, полагаясь только на `README.md`, `P_20.md` и код.
2. Описать `Backtesting / Replay Foundation` как ранний simulation / comparison hub с ownership над analytics, historical-data ingestion, optimization и broader replay platform semantics.
3. Закрепить `P_20` отдельным ADR как узкий replay/backtest foundation layer с явным исключением `Validation`, `Paper`, `Execution`, `OMS`, `Manager`, analytics, dashboard, historical-data platform и research/optimization ownership.

## Решение

Принят вариант 3.

### 1. `Backtesting / Replay Foundation` является narrow replay/backtest layer

- `Replay` — это отдельный replay/backtest layer внутри текущей package discipline проекта.
- Этот слой не является analytics platform.
- Этот слой не является reporting platform.
- Этот слой не является comparison / ranking platform.
- Этот слой не является dashboard / operator surface.
- Этот слой не является full historical data platform.
- Этот слой не является optimization / Monte Carlo / walk-forward / research-lab line.
- Его задача в `P_20` — узко и детерминированно строить replay truth поверх historical inputs и existing typed truths.

### 2. Replay layer потребляет only existing typed truths и historical inputs

- `Replay` использует:
  - typed replay/backtest contracts;
  - typed replay event vocabulary;
  - explicit replay runtime boundary;
  - deterministic historical-input ingestion;
  - first ingress path truth;
  - anti-lookahead integrity guard.
- Replay layer может ссылаться на adjacent truths через metadata/context references:
  - `Validation`;
  - `Paper`;
  - existing runtime-originated truths.
- Bootstrap / composition root не собирает replay domain context на текущем этапе.
- Внутренняя сборка `ReplayContext`, lifecycle semantics, integrity truth и replay candidate truth принадлежат replay layer.

Это означает:

- `Replay` не тянет ownership у `Validation`;
- `Replay` не тянет ownership у `Paper`;
- `Replay` не тянет ownership у `Execution`;
- `Replay` не тянет ownership у `OMS`;
- `Replay` не тянет ownership у `Manager`.

### 3. Реальный scope `P_20`

В scope `P_20` входят только:

- replay/backtest contracts;
- typed replay event vocabulary;
- explicit replay runtime boundary;
- deterministic historical-input ingestion;
- narrow replay-state / query surface;
- first ingress path truth;
- anti-lookahead integrity guard;
- narrow package-level integration внутри `backtest`;
- minimal recorder/state semantics только в той мере, в какой они нужны foundation contour.

### 4. Что `P_20` не владеет

`Backtesting / Replay Foundation` в рамках `P_20` не владеет:

- `Validation`;
- `Paper`;
- `Execution`;
- `OMS`;
- `Manager`;
- analytics / reporting platform;
- plotting / dashboard / operator line;
- comparison / ranking platform;
- full historical data platform;
- optimization / Monte Carlo / walk-forward line;
- broader research lab;
- full virtual portfolio / exchange simulation platform.

Если такие линии понадобятся, они открываются отдельно и не считаются скрытым продолжением `P_20`.

### 5. Как проходит граница с соседними и будущими линиями

#### Adjacent: `Validation`

- `Validation` владеет narrow review / evaluation truth.
- `Replay` не подменяет review semantics и не становится evaluation hub.
- `Replay` может использовать validation references как adjacent input truth, но не получает ownership над validation lifecycle.

#### Adjacent: `Paper`

- `Paper` владеет narrow rehearsal / controlled-simulation truth.
- `Replay` не подменяет rehearsal semantics и не становится paper/live comparison platform.
- `Replay` может различать paper truth в context/candidate references, но не владеет paper runtime state.

#### Adjacent: `Execution` и `OMS`

- `Execution` владеет operational execution intent / bridge semantics.
- `OMS` владеет order-state / lifecycle truth.
- `Replay` может replay-ить existing truths, но не становится hidden simulated execution/OMS platform.
- Replay foundation не получает ownership над order lifecycle, fills, approvals или operational routing.

#### Adjacent: `Manager`

- `Manager` владеет workflow-coordination truth.
- `Replay` не становится workflow owner только потому, что future replay paths могут касаться manager-originated truths.

#### Legacy contour: `ReplayEngine`

- Legacy `ReplayEngine` остаётся compatibility contour.
- Он не задаёт authoritative Phase 20 truth.
- Наличие legacy engine не означает, что `P_20` уже владеет tick engine, simulation platform или richer replay semantics.

#### Legacy contour: `EventRecorder`

- Legacy `EventRecorder` остаётся compatibility helper.
- Он не делает `P_20` owner-ом analytics/reporting semantics.
- Recorder-state может существовать как narrow replay-side state, но не превращает phase в reporting platform.

#### Future lines: analytics / reporting

- Analytics, reporting, ranking и richer comparison outputs не принадлежат replay foundation.
- `Replay` может формировать replay truth, но не обязана сама превращать её в analytics / reporting platform.

#### Future lines: historical data

- Full historical data ingestion, storage, cataloging и data inventory platform semantics не принадлежат `P_20`.
- В `P_20` допускается только narrow historical-input ingress discipline, необходимая replay foundation.

#### Future lines: optimization / research

- Parameter sweeps, optimization, Monte Carlo, walk-forward и broader research-lab semantics не принадлежат `P_20`.
- Если позже понадобится richer experimentation contour, он открывается отдельно.

### 6. Почему этот ADR нужен до formal finalization `P_20`

Этот ADR нужен именно до formal finalization, потому что:

- `P_20` находится на высокой risk-of-scope-inflation boundary;
- historical materials создают ложное ожидание broad replay / analytics / research semantics уже на foundation step;
- legacy `ReplayEngine` и `EventRecorder` повышают риск interpretation drift сильнее, чем у обычной новой линии;
- после релиза ADR выглядел бы как ретроспективное оправдание уже принятого решения;
- до релиза он работает как честный architecture lock, который ограничивает interpretation drift.

Следовательно:

- `P_20` не должна финализироваться как `v1.20.0`, пока эта boundary не зафиксирована отдельным ADR.

## Последствия

- **Плюсы:** formal finalization `P_20` получает жёсткую архитектурную рамку и перестаёт зависеть только от phase-plan wording.
- **Плюсы:** граница между replay layer, `Validation`, `Paper`, `Execution`, `OMS`, `Manager` и future analytics / historical-data / optimization lines становится явной.
- **Плюсы:** legacy `ReplayEngine` / `EventRecorder` больше нельзя честно трактовать как authoritative Phase 20 surface.
- **Минусы:** subsequent steps требуют большей дисциплины и не позволяют "удобно" добавлять broader replay / comparison / research behavior под тем же phase label.
- **Минусы:** если позже понадобится richer replay-supporting behavior, его придётся оформлять как новый scope, а не как тихое расширение `P_20`.

## Что становится обязательным для formal finalization `P_20`

1. Читать `Backtesting / Replay Foundation` только как narrow replay/backtest layer.
2. Не трактовать `P_20` как analytics / reporting / dashboard / comparison / historical-data / optimization / research line.
3. Сохранять existing typed truths и historical-input contracts как единственные authoritative inputs текущей реализации.
4. Любой follow-up, который требует broader simulation, ranking, reporting, historical-data platform semantics, optimization, walk-forward или virtual execution ownership, открывать отдельной line после `P_20`.

## Связанные ADR

- Связан с [0024-production-alignment-composition-root-and-runtime-truth.md](D:/CRYPTOTEHNOLOG/docs/adr/0024-production-alignment-composition-root-and-runtime-truth.md)
- Логически продолжает [0030-validation-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0030-validation-foundation-boundary.md)
- Логически продолжает [0031-paper-trading-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0031-paper-trading-foundation-boundary.md)
- Логически продолжает [P_18.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_18.md), [P_19.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_19.md) и [P_20.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_20.md)
- Ограничивает interpretation drift относительно historical/reference prompts:
  - [17_ФАЗА_16_BACKTESTING_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/17_%D0%A4%D0%90%D0%97%D0%90_16_BACKTESTING_PROMPT.md)
  - [18_ФАЗА_17_PAPER_TRADING_PROMPT.md](D:/CRYPTOTEHNOLOG/prompts/18_%D0%A4%D0%90%D0%97%D0%90_17_PAPER_TRADING_PROMPT.md)
