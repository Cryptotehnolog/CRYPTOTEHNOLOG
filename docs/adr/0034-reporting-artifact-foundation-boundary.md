# Reporting Artifact Foundation как узкая artifact-first reporting line

**Дата:** 2026-03-24  
**Статус:** Принято

## Контекст

После открытия и реализации `P_21` проект уже имеет последовательную chain of truth:

- `Validation Foundation`;
- `Paper Trading Foundation`;
- `Backtesting / Replay Foundation`;
- отдельный package boundary `src/cryptotechnolog/reporting`;
- typed reporting contracts;
- explicit reporting artifacts;
- deterministic artifact assembly;
- local read-only retrieval/catalog truth.

На этом фоне `P_21` открывает новый слой:

- `Reporting Artifact Foundation`.

Но именно на этой границе historical lineage особенно опасна:

- historical analytics expectations тянут reporting line в сторону broad analytics platform;
- historical dashboard expectations размывают границу между reporting contour и operator-facing UI surface;
- historical comparison expectations тянут её в сторону ranking / comparison hub;
- historical optimization expectations тянут её в сторону benchmarking / research lab;
- historical delivery expectations тянут её в сторону notifications / export / external reporting platform;
- local retrieval/catalog surface легко начать трактовать как service/runtime boundary;
- artifact bundle легко ошибочно трактовать как ранний analytics runtime.

Без отдельного ADR `P_21` легко начать трактовать слишком широко:

- как analytics runtime/platform;
- как reporting delivery platform;
- как dashboard / operator surface;
- как comparison / ranking hub;
- как optimization / Monte Carlo / walk-forward line;
- как historical data / report storage platform;
- как owner `Validation`, `Paper` или `Replay` semantics;
- как owner `Execution`, `OMS` или `Manager` truth;
- как line, которой уже нужен event vocabulary, orchestration и service lifecycle.

Phase plan и код `P_21` уже удерживают scope узко, но до formal finalization нужен отдельный
architecture lock, который:

- формально закрепит ownership boundary;
- зафиксирует artifact-first identity линии;
- отделит reporting package boundary от runtime/service/dashboard/comparison semantics;
- не позволит переосмыслить фазу задним числом после релиза.

## Рассмотренные альтернативы

1. Финализировать `P_21` без нового ADR, полагаясь только на `README.md`, `P_21.md` и код.
2. Описать `Reporting Artifact Foundation` как ранний analytics/reporting platform step с ownership над runtime delivery, dashboard coupling и broader comparison semantics.
3. Закрепить `P_21` отдельным ADR как узкую artifact-first reporting line с явным исключением runtime/service/dashboard/comparison ownership.

## Решение

Принят вариант 3.

### 1. `P_21 = Reporting Artifact Foundation`

- `Reporting` — это отдельная artifact-first reporting line внутри текущей package discipline проекта.
- Этот слой не является analytics runtime/platform.
- Этот слой не является reporting delivery platform.
- Этот слой не является dashboard / operator surface.
- Этот слой не является comparison / ranking platform.
- Этот слой не является optimization / research line.
- Его задача в `P_21` — узко и детерминированно формировать typed reporting artifacts поверх already existing typed truths.

### 2. Reporting line потребляет only existing typed truths

`Reporting` read-only потребляет только:

- `ValidationReviewCandidate`;
- `PaperRehearsalCandidate`;
- `ReplayCandidate`.

Bootstrap / composition root не собирает reporting domain context.

Reporting line на текущем этапе владеет только:

- typed reporting contracts;
- `ValidationReportArtifact`;
- `PaperReportArtifact`;
- `ReplayReportArtifact`;
- `ReportingArtifactBundle`;
- deterministic assembly;
- retrieval/catalog truth;
- provenance/read-only discipline.

Это означает:

- `Reporting` не тянет ownership у `Validation`;
- `Reporting` не тянет ownership у `Paper`;
- `Reporting` не тянет ownership у `Replay`;
- `Reporting` не тянет ownership у `Execution`;
- `Reporting` не тянет ownership у `OMS`;
- `Reporting` не тянет ownership у `Manager`.

### 3. Artifact-first package boundary является обязательной

- `src/cryptotechnolog/reporting` фиксируется как отдельный package boundary.
- Эта граница нужна уже на opening/foundation step, потому что без неё reporting truth начинает расползаться по:
  - `validation`;
  - `paper`;
  - `backtest`;
  - future dashboard/operator surface.
- Package boundary здесь выступает как ownership lock:
  - reporting layer читает existing truths;
  - reporting layer не подменяет upstream layers;
  - reporting line не маскируется под расширение уже закрытых фаз.

### 4. Runtime/service boundary на этой фазе не нужна

На `P_21` не требуется:

- runtime lifecycle;
- service orchestration;
- background processing;
- persistence platform semantics;
- API coupling;
- delivery/export semantics.

Причина:

- artifact-first opening truth уже полностью удерживается через:
  - contracts;
  - artifacts;
  - deterministic assembly;
  - local read-only retrieval.

Следовательно:

- введение runtime/service boundary на этой фазе было бы artificial scope expansion.

### 5. Event vocabulary на этой фазе не нужна

На `P_21` не требуется local reporting event vocabulary.

Причина:

- event vocabulary почти неизбежно тянет:
  - publication semantics;
  - event-bus expectations;
  - runtime/service lifecycle;
  - downstream dashboard/service coupling.
- current phase truth не требует этого для artifact-first reporting line.

Следовательно:

- отсутствие event vocabulary в `P_21` является честной boundary discipline, а не missing feature.

### 6. Retrieval/catalog не является service/runtime surface

Local retrieval/catalog truth в `P_21`:

- является immutable/read-only local query surface;
- работает только поверх уже существующих artifacts и bundles;
- не хранит lifecycle state;
- не выполняет orchestration;
- не публикует события;
- не делает line owner-ом delivery semantics.

Следовательно:

- retrieval/catalog допустим как artifact-local surface;
- retrieval/catalog не превращает `P_21` в service/runtime line.

### 7. Реальный scope `P_21`

В scope `P_21` входят только:

- typed reporting contracts;
- artifact kind/status/provenance semantics;
- `ValidationReportArtifact`;
- `PaperReportArtifact`;
- `ReplayReportArtifact`;
- `ReportingArtifactBundle`;
- deterministic assembly helpers;
- local read-only retrieval/catalog surface;
- provenance/read-only discipline.

### 8. Что `P_21` не владеет

`Reporting Artifact Foundation` в рамках `P_21` не владеет:

- dashboard/UI;
- operator workflows;
- comparison/ranking;
- optimization / Monte Carlo / walk-forward;
- historical data platform ownership;
- plotting;
- research lab semantics;
- analytics runtime/platform;
- notification/delivery surface;
- `Execution`;
- `OMS`;
- `Manager`;
- takeover `Validation`;
- takeover `Paper`;
- takeover `Replay`.

Если такие линии понадобятся, они открываются отдельно и не считаются скрытым продолжением `P_21`.

### 9. Как проходит граница с соседними и будущими линиями

#### Adjacent: `Validation`

- `Validation` владеет narrow review / evaluation truth.
- `Reporting` может только read-only производить derived artifacts поверх review truth.
- `Reporting` не подменяет validation lifecycle или review semantics.

#### Adjacent: `Paper`

- `Paper` владеет narrow rehearsal truth.
- `Reporting` может только read-only производить derived artifacts поверх rehearsal truth.
- `Reporting` не становится rehearsal/comparison platform.

#### Adjacent: `Replay`

- `Replay` владеет narrow replay/backtest truth.
- `Reporting` может только read-only производить derived artifacts поверх replay truth.
- `Reporting` не становится analytics/replay runtime и не получает ownership над replay lifecycle.

#### Future lines: dashboard / operator

- Dashboard/operator surface не принадлежит `P_21`.
- Dashboard позже может только потреблять reporting artifacts read-only.

#### Future lines: comparison / ranking

- Ranking, richer comparison и benchmarking hub semantics не принадлежат `P_21`.
- Если позже понадобится comparison line, она открывается отдельно.

#### Future lines: analytics runtime / delivery

- Runtime delivery, report export, notification routing и broader analytics runtime semantics не принадлежат `P_21`.
- Если позже понадобится service/runtime contour, он открывается отдельно.

### 10. Почему этот ADR нужен до formal finalization `P_21`

Этот ADR нужен именно до formal finalization, потому что:

- `P_21` находится на высокой risk-of-scope-inflation boundary;
- reporting territory особенно легко расползается в dashboard/runtime/comparison semantics;
- retrieval/catalog surface без ADR можно ошибочно трактовать как ранний service layer;
- после релиза ADR выглядел бы как ретроспективное оправдание уже принятого решения;
- до релиза он работает как честный architecture lock, который ограничивает interpretation drift.

Следовательно:

- `P_21` не должна финализироваться как release step, пока эта boundary не зафиксирована отдельным ADR.

## Последствия

- **Плюсы:** formal finalization `P_21` получает жёсткую архитектурную рамку и перестаёт зависеть только от phase-plan wording.
- **Плюсы:** граница между reporting layer, `Validation`, `Paper`, `Replay` и future dashboard/comparison/runtime lines становится явной.
- **Плюсы:** retrieval/catalog больше нельзя честно трактовать как service/runtime contour.
- **Минусы:** subsequent steps требуют большей дисциплины и не позволяют "удобно" расширять `P_21` в dashboard, delivery или analytics runtime behavior под тем же phase label.
- **Минусы:** если позже понадобится richer reporting-supporting behavior, его придётся оформлять как новый scope, а не как тихое расширение `P_21`.

## Что становится обязательным для formal finalization `P_21`

1. Читать `Reporting Artifact Foundation` только как narrow artifact-first reporting line.
2. Не трактовать `P_21` как analytics runtime/platform, dashboard, comparison/ranking, delivery или service line.
3. Сохранять `ValidationReviewCandidate`, `PaperRehearsalCandidate` и `ReplayCandidate` как единственные authoritative upstream inputs текущей реализации.
4. Любой follow-up, который требует runtime/service lifecycle, dashboard-led presentation, ranking/comparison ownership, delivery semantics или broader analytics platform behavior, открывать отдельной line после `P_21`.

## Связанные ADR

- Логически продолжает [0030-validation-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0030-validation-foundation-boundary.md)
- Логически продолжает [0031-paper-trading-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0031-paper-trading-foundation-boundary.md)
- Логически продолжает [0032-backtesting-replay-foundation-boundary.md](D:/CRYPTOTEHNOLOG/docs/adr/0032-backtesting-replay-foundation-boundary.md)
- Логически продолжает [P_21.md](D:/CRYPTOTEHNOLOG/prompts/plan/P_21.md)
