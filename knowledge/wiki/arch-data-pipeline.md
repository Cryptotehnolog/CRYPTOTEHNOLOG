---
type: workflow
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - deribit-api-2026-05-20
  - polymarket-api-2026-05-20
  - project-review-2026-05-19
---

# Architecture: Data Pipeline

Data pipeline для MVP должен быть replay-first. Redis Streams полезны как transient bus, но PostgreSQL event journal является source of truth.

## Flow

```text
Deribit API / Polymarket API
  -> raw event capture
  -> PostgreSQL event_journal
  -> normalized market events
  -> probability_basis feature calculation
  -> basis_observations
  -> reports / replay
```

Redis Streams добавляются после стабилизации event contracts:

```text
raw:deribit
raw:polymarket
features:probability_basis
signals:raw
orders:ready
execution:reports
```

Для MVP `signals`, `orders` и `execution` могут оставаться mock/paper-only.

## PostgreSQL

Текущая migration создает:

- `event_journal` - append-only raw/normalized event storage;
- `replay_runs` - metadata deterministic replay runs;
- `basis_observations` - calculated probability basis observations.

`event_journal` должен сохранять payload до derived calculations.

## Basis Observations

`basis_observations` - первый derived output probability-basis matcher.

Текущий Rust слой:

- `BasisObservation`,
- `BasisObservationRow`,
- `BasisObservationWriter`,
- `BasisObservationRowWriter`,
- `InMemoryBasisObservationWriter`,
- `PostgresBasisObservationAdapter` skeleton,
- `observations_from_match_decisions()`.

Real PostgreSQL writer намеренно не добавлен в этой итерации. Сначала фиксируется deterministic contract, row serialization и replay behavior, затем подключается storage implementation.

## Adapter Traits

Первые Rust traits должны быть read-only:

```text
DeribitDiscoveryAdapter
  - list_eth_options()
  - get_option_snapshot()

PolymarketDiscoveryAdapter
  - list_crypto_markets()
  - get_market_snapshot()

EventJournal
  - append_event()
  - read_events_for_replay()

BasisObservationWriter
  - append_basis_observation()

BasisObservationRowWriter
  - append_basis_observation_row()
```

## Ingestion Skeleton

`crates/ingestion` добавлен как Phase 0 read-only ingestion boundary.

Текущий scope:

- `IngestionConfig` - config contract для source, endpoint, timeout, reconnect backoff, batch size и config version;
- `IngestionSource` - `Deribit` или `Polymarket`;
- `IngestionErrorKind` - API/reconnect/rate-limit/malformed-payload/journal-write/not-implemented taxonomy;
- `IngestionClient` - sync skeleton trait с `poll_once(config)`;
- `MockIngestionClient` - deterministic scripted client для tests;
- `LiveIngestionClient` - explicit stub, который возвращает `NotImplemented` и не делает network calls;
- `ingest_once()` - orchestration helper, который пишет raw events в `EventJournal` до normalized `MarketEvent`.

Это не live API implementation. Real HTTP/WebSocket logic добавляется позже отдельным decision/code review.

Fixture `fixtures/ingestion/api_error_reconnect_sequence.psv` документирует сценарий: API error -> reconnect -> recovered batch. Он нужен, чтобы live ingestion проектировался с учетом failure/recovery path, а не только happy path.

Fixture `fixtures/ingestion/happy_path_batches.psv` документирует минимальный orchestration happy path:

```text
Deribit mock batch
  -> Polymarket mock batch
  -> EventJournal raw/normalized capture
  -> read_events_for_replay()
  -> probability-basis matcher
  -> BasisObservation
```

Этот тест связывает ingestion skeleton с уже готовым probability-basis pipeline без реальных API, ключей, сети, PostgreSQL подключения или trading side effects.

## Добавление Нового Источника

1. Создать source note в `knowledge/raw/sources/`.
2. Добавить adapter trait.
3. Добавить normalized event type.
4. Добавить raw payload preservation.
5. Добавить replay fixture.
6. Добавить rejection reasons в reports.

## Design Constraint

LLM/wiki/Obsidian не участвуют в runtime path. Они помогают разработке, но не принимают trading decisions.
