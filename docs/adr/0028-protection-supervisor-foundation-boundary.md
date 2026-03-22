# Protection / Supervisor Foundation как узкий supervisory consumer contour

**Дата:** 2026-03-23  
**Статус:** Принято  

## Контекст

После реализации `P_15` проект уже имеет последовательную chain of truth:

- `Execution Foundation`;
- `Opportunity / Selection Foundation`;
- `Strategy Orchestration / Meta Layer`;
- `Position Expansion Foundation`;
- `Portfolio Governor / Capital Governance Foundation`;
- единый production composition root и runtime truth discipline;
- operator-visible diagnostics / readiness / degraded semantics.

На этом фоне `P_15` открывает новый слой:

- `Protection / Supervisor Foundation`.

Но именно на этой границе historical lineage особенно опасна:

- historical kill-switch prompt тянет `protection` в сторону broad emergency-operations platform;
- historical `OMS` prompt тянет эту же линию в сторону order-control ownership;
- historical notifications / approval expectations добавляют operator-escalation semantics;
- historical broader manager expectations размывают границу между supervisory contour и workflow ownership.

Без отдельного ADR `P_15` легко начать трактовать слишком широко:

- как будущий `OMS`;
- как liquidation engine;
- как approval workflow platform;
- как notifications / PagerDuty line;
- как верхнеуровневый emergency manager.

Phase plan и result truth для `P_15` уже удерживают scope узко, но до formal finalization нужен
отдельный architecture lock, который:

- формально закрепит ownership boundary;
- свяжет `Protection` с upstream `Portfolio Governor`;
- зафиксирует, что именно не входит в `P_15`;
- не позволит переосмыслить фазу задним числом после релиза.

## Рассмотренные альтернативы

1. Финализировать `P_15` без нового ADR, полагаясь только на `README.md`, `P_15.md` и код.
2. Описать `Protection` как ранний слой full emergency-operations platform с заделом под liquidation, notifications и approval workflow.
3. Закрепить `P_15` отдельным ADR как узкий supervisory consumer contour поверх `PortfolioGovernorCandidate`, с явным исключением `OMS`, liquidation, notifications и broader manager ownership.

## Решение

Принят вариант 3.

### 1. `Protection / Supervisor Foundation` является narrow supervisory consumer contour

- `Protection` — это отдельный supervisory layer внутри текущей package discipline проекта.
- Этот слой не является новым control-plane universe.
- Этот слой не владеет всей emergency platform.
- Его задача в `P_15` — узко и детерминированно потреблять existing typed truth и формировать narrow supervisory state.

### 2. Upstream truth для `Protection` — только existing typed truth

- `Protection` потребляет upstream truth через `PortfolioGovernorCandidate`.
- Bootstrap / composition root не собирает `ProtectionContext`.
- Bootstrap только wiring-ит upstream governor truth в `ProtectionRuntime`.
- Внутренняя сборка `ProtectionContext`, lifecycle semantics и supervisory decision truth принадлежат protection layer.

Это означает:

- `Protection` не тянет напрямую `market_data`;
- `Protection` не тянет напрямую `analysis` / `intelligence`;
- `Protection` не тянет напрямую `signals`, `strategy`, `opportunity`, `orchestration`;
- `Protection` не подменяет `Portfolio Governor`, а строится поверх него.

### 3. Реальный scope `P_15`

В scope `P_15` входят только:

- supervisory contracts;
- `PROTECT` / `HALT` / `FREEZE` semantics;
- protection decision / status / validity semantics;
- explicit runtime boundary;
- query/state-first surface;
- narrow diagnostics / readiness / degraded truth;
- narrow composition-root integration;
- typed local event vocabulary protection layer.

### 4. Что `P_15` не владеет

`Protection / Supervisor Foundation` в рамках `P_15` не владеет:

- future `OMS`;
- centralized order registry;
- cancel / modify lifecycle;
- reconciliation;
- broad liquidation engine;
- close-all / portfolio liquidation orchestration;
- notifications / PagerDuty / SMS platform;
- approval workflow platform;
- broader `StrategyManager`;
- broad workflow orchestration;
- analytics / validation;
- dashboard line.

Если такие линии понадобятся, они открываются отдельно и не считаются скрытым продолжением `P_15`.

### 5. Как проходит граница с соседними линиями

#### Upstream: `Portfolio Governor`

- `Portfolio Governor` владеет narrow capital-governance / portfolio-admission truth.
- `Protection` не переписывает governor semantics и не принимает роль capital governor.
- `Protection` использует governor truth как вход для supervisory contour.

#### Downstream / future: `OMS`

- `OMS` владеет order registry, cancel / modify lifecycle, reconciliation и exchange-facing order truth.
- `Protection` не получает ownership над order lifecycle только потому, что принимает supervisory decision.

#### Downstream / future: liquidation / ops

- Даже если в будущем появится liquidation or emergency-ops line, она не считается частью `P_15`.
- `Protection` не равна liquidation engine.

#### Downstream / future: notifications / approval workflow

- Operator alerts, approval flow, escalation routing и delivery channels не принадлежат `Protection` foundation.
- `Protection` может выдавать supervisory truth, но не обязана сама превращать её в human-approval или alerting platform.

### 6. Почему этот ADR нужен до formal finalization `P_15`

Этот ADR нужен именно до formal finalization, потому что:

- `P_15` находится на высокой risk-of-scope-inflation boundary;
- исторические материалы создают ложное ожидание, что protection автоматически включает liquidation / notifications / OMS-adjacent behavior;
- после релиза ADR выглядел бы как ретроспективное оправдание уже принятого решения;
- до релиза он работает как честный architecture lock, который ограничивает interpretation drift.

Следовательно:

- `P_15` не должна финализироваться как `v1.15.0`, пока эта boundary не зафиксирована отдельным ADR.

## Последствия

- **Плюсы:** formal finalization `P_15` получает жёсткую архитектурную рамку и перестаёт зависеть только от phase-plan wording.
- **Плюсы:** граница между `Portfolio Governor`, `Protection`, future `OMS` и future operational lines становится явной.
- **Плюсы:** future implementation steps не смогут честно расширять `P_15` в liquidation / notifications / approval workflow без открытия отдельной линии.
- **Минусы:** последующие steps требуют большей дисциплины и не позволяют “удобно” добавлять emergency-adjacent поведение под тем же phase label.
- **Минусы:** если позже понадобится richer supervisory behavior, его придётся оформлять как новый scope, а не как тихое расширение `P_15`.

## Что становится обязательным для formal finalization `P_15`

1. Читать `Protection / Supervisor Foundation` только как narrow supervisory consumer contour.
2. Не трактовать `P_15` как `OMS`, liquidation engine или notifications / approval workflow line.
3. Сохранять `PortfolioGovernorCandidate` как единственный upstream contract для текущей реализации.
4. Любой follow-up, который требует order lifecycle ownership, human-approval routing или alert delivery, открывать отдельной line после `P_15`.

## Связанные ADR

- Связан с [0024-production-alignment-composition-root-and-runtime-truth.md](D:/CRYPTOTEHNOLOG/docs/adr/0024-production-alignment-composition-root-and-runtime-truth.md)
- Логически продолжает [P_14.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_14.md) и [P_15.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_15.md)
- Ограничивает interpretation drift относительно historical/reference prompts по kill switch / `OMS` / notifications / broader manager lines
