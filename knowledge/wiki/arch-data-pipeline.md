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
```

## Добавление Нового Источника

1. Создать source note в `knowledge/raw/sources/`.
2. Добавить adapter trait.
3. Добавить normalized event type.
4. Добавить raw payload preservation.
5. Добавить replay fixture.
6. Добавить rejection reasons в reports.

## Design Constraint

LLM/wiki/Obsidian не участвуют в runtime path. Они помогают разработке, но не принимают trading decisions.

