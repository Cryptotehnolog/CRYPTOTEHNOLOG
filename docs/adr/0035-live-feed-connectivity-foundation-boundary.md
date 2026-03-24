# Live Feed Connectivity Foundation как узкая live-feed/session connectivity line

**Дата:** 2026-03-24  
**Статус:** Принято

## Контекст

После formal finalization `P_21 / v1.21.0` проект уже имеет:

- `market_data` как отдельный typed domain/runtime foundation;
- `execution` как отдельный execution contour;
- `oms` как отдельный order-lifecycle/order-state contour;
- README, phase docs и earlier ADR truth, которые последовательно выносят
  live exchange connectivity, adapter ecosystems, routing, reconciliation
  и reliability platform semantics за пределы уже закрытых фаз.

В рамках `P_22` уже собран узкий implementation contour:

- отдельный package boundary `src/cryptotechnolog/live_feed`;
- typed connection/session contracts;
- typed feed-health/readiness/degraded truth;
- narrow single-session runtime boundary;
- narrow ingest integration contour в existing `market_data`;
- unit verification на contracts, runtime и integration truth.

Но именно здесь interpretation drift особенно опасен:

- live feed connectivity легко начинают трактовать как ранний exchange adapter platform step;
- single-session runtime легко переосмыслить как начало broader connectivity service/platform;
- ingest integration легко ошибочно трактовать как ownership takeover над `market_data`;
- reconnect/backoff semantics легко расползаются в reliability platform;
- live feed layer легко потянуть в execution connectivity, routing и reconciliation territory.

Без отдельного ADR `P_22` легко начать трактовать слишком широко:

- как broad exchange adapter ecosystem;
- как execution connectivity line;
- как routing / smart-routing foundation;
- как failover / reliability platform;
- как reconciliation platform;
- как historical storage / backfill platform;
- как operator/dashboard workflow surface;
- как owner `market_data`, `execution` или `oms` truth.

Phase plan и текущий код уже удерживают scope узко, но до finalization path нужен
отдельный architecture lock, который:

- формально закрепит ownership boundary;
- отделит live-feed/session truth от `market_data` domain ownership;
- зафиксирует narrow runtime identity линии;
- не позволит задним числом расширить фазу в adapter/routing/reliability semantics.

## Рассмотренные альтернативы

1. Финализировать `P_22` без нового ADR, полагаясь только на `README.md`, `P_22.md` и код.
2. Описать `P_22` как ранний exchange connectivity platform step с future-ready ownership над adapters, execution connectivity и broader routing semantics.
3. Закрепить `P_22` отдельным ADR как узкую `Live Feed Connectivity Foundation` line с явным исключением adapter ecosystem, execution connectivity, routing, reconciliation и reliability ownership.

## Решение

Принят вариант 3.

### 1. `P_22 = Live Feed Connectivity Foundation`

- `P_22` фиксируется как узкая live-feed/session connectivity line.
- Эта линия не является broad exchange connectivity platform.
- Эта линия не является exchange adapter ecosystem.
- Эта линия не является execution connectivity layer.
- Эта линия не является routing / smart-routing foundation.
- Эта линия не является failover / reliability platform.
- Эта линия не является reconciliation platform.

Её задача в `P_22`:

- формализовать typed connection/session truth;
- удерживать feed-health/readiness/degraded semantics;
- предоставлять narrow single-session runtime boundary;
- предоставлять narrow ingest handoff и integration contour в existing `market_data`.

### 2. `live_feed` является отдельным package boundary

- `src/cryptotechnolog/live_feed` фиксируется как отдельный package boundary.
- Эта граница нужна уже на текущей фазе, потому что без неё connectivity truth
  быстро растворяется в:
  - `market_data/runtime`;
  - future adapter/client logic;
  - broader live trading runtime expectations.

Package boundary здесь выступает как ownership lock:

- `live_feed` владеет session/connectivity truth;
- `live_feed` владеет narrow runtime semantics;
- `market_data` сохраняет ownership над domain contracts и interpretation;
- future adapter/platform semantics не маскируются под "небольшое расширение" `market_data`.

### 3. Что именно принадлежит `live_feed`

`Live Feed Connectivity Foundation` в рамках `P_22` владеет только:

- typed connection/session truth;
- `FeedConnectionStatus`;
- `FeedSessionIdentity`;
- `FeedConnectionState`;
- `FeedConnectivityAssessment`;
- `FeedIngressEnvelope`;
- `FeedIngestRequest`;
- narrow single-session runtime boundary;
- minimal reconnect/backoff semantics;
- narrow ingest handoff/integration contour в existing `market_data`.

### 4. Что именно не принадлежит `live_feed`

`Live Feed Connectivity Foundation` в рамках `P_22` не владеет:

- `market_data` domain contracts целиком;
- tick / bar / orderbook semantics как authoritative domain truth;
- symbol metrics / universe semantics;
- `execution`;
- `oms`;
- routing / smart-routing semantics;
- reconciliation semantics;
- broad adapter/client ecosystem;
- operator/dashboard workflow semantics;
- persistence / storage / backfill semantics.

### 5. Почему narrow runtime boundary на этой фазе нужна

В отличие от purely artifact-first phase, `P_22` по смыслу уже lifecycle-oriented.

Поэтому narrow runtime boundary на этой фазе необходима:

- explicit `start/stop`;
- connection state transitions;
- `DISCONNECTED / CONNECTING / CONNECTED / DEGRADED`;
- minimal retry/backoff truth;
- typed connectivity assessment;
- narrow ingest request generation.

Но эта runtime boundary не должна становиться:

- service platform;
- multi-session orchestration layer;
- client ecosystem;
- API/delivery layer;
- broader reliability platform.

### 6. Почему adapter/client ecosystem на этой фазе не нужна

На `P_22` не требуется:

- broad exchange adapter ecosystem;
- rich client hierarchy;
- multi-exchange client platform;
- connector pool abstraction.

Причина:

- adapter/client ecosystem слишком быстро тянет за собой:
  - multi-exchange abstraction;
  - execution connectivity;
  - routing;
  - reconciliation;
  - broader integration ownership.

Следовательно:

- current `P_22` intentionally останавливается на narrow live-feed/session truth;
- richer adapter/client semantics остаются future follow-up territory.

### 7. Почему ingest integration не делает `live_feed` owner-ом `market_data`

`live_feed` integration contour:

- принимает только typed `FeedIngestRequest`;
- поддерживает только narrow handoff kinds:
  - `trade_tick`;
  - `orderbook_snapshot`;
- конвертирует handoff в existing `market_data` contracts;
- делегирует дальнейшую interpretation existing `MarketDataRuntime`.

Это означает:

- `live_feed` остаётся owner-ом transport/session/connectivity truth;
- `market_data` остаётся owner-ом:
  - `TickContract`;
  - `OrderBookSnapshotContract`;
  - runtime ingestion/validation;
  - дальнейшей domain interpretation.

Следовательно:

- ingest integration допустима как boundary bridge;
- ingest integration не является ownership takeover над `market_data`.

### 8. Почему линия не должна расширяться в execution connectivity, routing, reconciliation и reliability platform

`P_22` не должна тихо расширяться в:

- execution connectivity;
- routing;
- smart routing;
- reconciliation;
- failover/reliability platform.

Причина:

- эти contours требуют другой ownership surface;
- они затрагивают `execution`, `oms`, live decision flow и broader operator/runtime semantics;
- они существенно шире current live-feed/session foundation.

Следовательно:

- любые такие semantics должны открываться отдельно;
- они не считаются hidden continuation `P_22`.

### 9. Реальный scope `P_22`

В scope `P_22` входят только:

- отдельный package boundary `live_feed`;
- typed connection/session contracts;
- typed feed-health/readiness/degraded truth;
- typed ingress envelope / ingest request;
- narrow single-session runtime boundary;
- minimal reconnect/backoff semantics;
- narrow integration helper в existing `market_data`;
- unit verification на contracts/runtime/integration boundary.

### 10. Что `P_22` жёстко не включает

Вне scope `P_22` находятся:

- broad exchange adapter ecosystem;
- rich client hierarchy;
- execution connectivity;
- order routing / smart routing;
- failover / reliability platform;
- reconciliation;
- historical storage / backfill platform;
- dashboard/operator workflows;
- analytics / reporting / research semantics;
- `market_data` domain ownership takeover;
- `execution` ownership;
- `oms` ownership;
- broad live-trading platform rewrite.

Если такие линии понадобятся, они открываются отдельно и не считаются скрытым продолжением `P_22`.

### 11. Граница с соседними линиями

#### Adjacent: `market_data`

- `market_data` владеет domain contracts и interpretation.
- `live_feed` только поставляет narrow connectivity/session truth и ingest handoff.
- `live_feed` не становится owner-ом tick/orderbook domain semantics.

#### Adjacent: `execution`

- `execution` не входит в scope `P_22`.
- `P_22` не становится execution connectivity layer.

#### Adjacent: `oms`

- `oms` не входит в scope `P_22`.
- `P_22` не становится order-state/reconciliation layer.

#### Future lines: adapters / routing / reliability

- adapter ecosystem не принадлежит `P_22`;
- routing не принадлежит `P_22`;
- reliability/failover platform не принадлежит `P_22`;
- reconciliation не принадлежит `P_22`.

### 12. Почему этот ADR нужен до finalization path

Этот ADR нужен до `P_22_RESULT` и finalization path, потому что:

- `P_22` находится на границе с высокой вероятностью scope inflation;
- live feed/session runtime особенно легко переосмыслить как начало broader platform;
- ingest integration без ADR можно ошибочно трактовать как ownership shift в сторону `market_data`;
- adapter/client semantics без явного lock легко "просочатся" как будто они already implied.

Следовательно:

- ADR нужен как architecture lock до finalization path, а не как ретроспективное описание после расширения scope.

## Последствия

- **Плюсы:** `P_22` получает жёсткую архитектурную рамку и перестаёт зависеть только от phase-plan wording.
- **Плюсы:** граница между `live_feed`, `market_data`, `execution` и `oms` становится явной.
- **Плюсы:** narrow runtime и ingest integration больше нельзя честно трактовать как начало adapter/platform expansion.
- **Минусы:** последующие live connectivity steps потребуют отдельного scope opening и не позволят тихо расширять `P_22`.
- **Минусы:** richer adapter/client/routing/reliability behavior придётся оформлять отдельной line, а не как удобное "продолжение" текущей.

## Что становится обязательным для finalization path `P_22`

1. Читать `P_22` только как narrow `Live Feed Connectivity Foundation`.
2. Не трактовать `P_22` как adapter ecosystem, execution connectivity, routing, reconciliation или reliability platform.
3. Сохранять `market_data` как authoritative owner domain contracts и interpretation semantics.
4. Любой follow-up, который требует broader clients/adapters, execution connectivity, routing, reconciliation, failover/reliability или operator workflows, открывать отдельной line после `P_22`.

## Связанные материалы

- Логически продолжает [0025-market-data-contract-layer-and-universe-semantics.md](/D:/CRYPTOTEHNOLOG/docs/adr/0025-market-data-contract-layer-and-universe-semantics.md)
- Учитывает boundary discipline из [P_10.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_10.md)
- Учитывает boundary discipline из [P_16.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_16.md)
- Логически продолжает [P_22.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_22.md)
