---
type: system
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
---

# Rust Events Contracts

Эта страница описывает Rust event contracts для MVP.

Важно: часть контрактов уже реализована в `crates/common/src/events.rs`, `crates/common/src/adapters.rs` и `crates/common/src/journal.rs`, а часть является proposed next step.

## Implemented Now

### `EventMeta`

Общий metadata block для событий.

| Field | Type | Meaning |
| --- | --- | --- |
| `event_id` | `String` | Stable event id. |
| `source` | `String` | Источник события. |
| `exchange_ts_ms` | `i64` | Exchange/API timestamp в milliseconds. |
| `received_ts_ms` | `i64` | Local receive timestamp в milliseconds. |
| `instrument_id` | `String` | Normalized instrument id. |
| `schema_version` | `u16` | Event schema version. |
| `config_version` | `String` | Config version. |

### `MarketEvent`

Enum normalized market events:

```text
MarketEvent::DeribitOptionQuote(DeribitOptionQuote)
MarketEvent::PolymarketOutcomeQuote(PolymarketOutcomeQuote)
```

### `DeribitOptionQuote`

| Field | Type | Meaning |
| --- | --- | --- |
| `meta` | `EventMeta` | Shared metadata. |
| `underlying` | `String` | Example: `ETH`. |
| `expiry_ts_ms` | `i64` | Option expiry timestamp. |
| `strike` | `f64` | Option strike. |
| `option_kind` | `OptionKind` | `Call` or `Put`. |
| `underlying_price` | `f64` | Current underlying/index price used by Black-Scholes MVP model. |
| `bid` | `f64` | Best bid/normalized bid. |
| `ask` | `f64` | Best ask/normalized ask. |
| `mark_iv` | `f64` | Deribit IV input for MVP model. |

### `PolymarketOutcomeQuote`

| Field | Type | Meaning |
| --- | --- | --- |
| `meta` | `EventMeta` | Shared metadata. |
| `event_slug` | `String` | Polymarket event slug. |
| `market_slug` | `String` | Polymarket market slug. |
| `outcome` | `String` | Outcome label, e.g. `Yes`. |
| `bid_probability` | `f64` | Bid as probability-like price. |
| `ask_probability` | `f64` | Ask as probability-like price. |
| `liquidity_usd` | `f64` | Liquidity estimate. |

### `ProbabilityBasisFeature`

| Field | Type | Meaning |
| --- | --- | --- |
| `meta` | `EventMeta` | Shared metadata. |
| `deribit_instrument_id` | `String` | Deribit option id. |
| `polymarket_market_slug` | `String` | Polymarket market slug. |
| `model_probability` | `f64` | Deribit-derived probability. |
| `polymarket_mid_probability` | `f64` | Polymarket midpoint probability. |
| `gross_edge_probability` | `f64` | Difference before costs. |
| `estimated_cost_probability` | `f64` | Cost estimate. |

Implemented methods:

```text
net_edge_probability()
survives_costs(threshold_probability)
```

### `BasisObservation`

`BasisObservation` реализован в `crates/common/src/observations.rs` и является Rust-моделью будущей таблицы `basis_observations`.

| Field | Type | Meaning |
| --- | --- | --- |
| `event_id` | `String` | Stable observation id. |
| `observed_at_ts_ms` | `i64` | Observation timestamp в milliseconds. |
| `deribit_instrument_id` | `String` | Deribit option id. |
| `polymarket_market_slug` | `String` | Polymarket market slug. |
| `model_probability` | `f64` | Deribit-derived model probability. |
| `polymarket_mid_probability` | `f64` | Polymarket midpoint probability. |
| `gross_edge_probability` | `f64` | Difference before costs. |
| `estimated_cost_probability` | `f64` | Estimated fees/spread/slippage/mismatch costs. |
| `net_edge_probability` | `f64` | Net edge после estimated costs. |
| `survives_costs` | `bool` | Проходит ли threshold после costs. |
| `schema_version` | `u16` | Schema version from source feature. |
| `config_version` | `String` | Config version from source feature. |

Implemented helper:

```text
BasisObservation::from_feature(feature, min_net_edge_probability)
observations_from_match_decisions(decisions, config)
```

### `BasisObservationRow`

`BasisObservationRow` - PostgreSQL-oriented serialization boundary для будущей таблицы `basis_observations`.

Он отделяет domain observation от storage row contract:

```text
BasisObservation
  -> BasisObservationRow
  -> future PostgreSQL adapter
```

Fixed column order:

```text
event_id
observed_at
deribit_instrument_id
polymarket_market_slug
model_probability
polymarket_mid_probability
gross_edge_probability
estimated_cost_probability
net_edge_probability
survives_costs
```

`observed_at` в row boundary передается как `observed_at_ts_ms`, а future PostgreSQL adapter должен конвертировать milliseconds в `timestamptz`.

### `RawDeribitEvent`

Raw API payload wrapper before normalization.

| Field | Type | Meaning |
| --- | --- | --- |
| `meta` | `EventMeta` | Shared metadata. |
| `endpoint_or_channel` | `String` | Deribit endpoint/channel. |
| `payload_json` | `String` | Raw JSON payload preserved as text. |

### `RawPolymarketEvent`

Raw API payload wrapper before normalization.

| Field | Type | Meaning |
| --- | --- | --- |
| `meta` | `EventMeta` | Shared metadata. |
| `api_layer` | `PolymarketApiLayer` | `Gamma` или `Clob`. |
| `payload_json` | `String` | Raw JSON payload preserved as text. |

### `DeribitDiscoveryAdapter`, `PolymarketDiscoveryAdapter`, `EventJournal`

Реализованы sync traits и mock implementations:

- `MockDeribitAdapter`,
- `MockPolymarketAdapter`,
- `InMemoryEventJournal`.
- `InMemoryBasisObservationWriter`.
- `PostgresBasisObservationAdapter` skeleton без real DB connection.

Также реализован probability-basis matcher skeleton:

- `ProbabilityBasisConfig`,
- `MatchDecision`,
- `RejectionReason`,
- `match_probability_basis()`,
- `match_from_market_events()`.
- Black-Scholes `N(d2)` probability calculation для call-like events.
- `BasisObservationWriter` interface без PostgreSQL подключения.
- `BasisObservationRowWriter` interface для storage-row layer.

### `crates/ingestion`

Реализован read-only ingestion skeleton без network dependencies:

```text
IngestionConfig
IngestionSource
IngestionErrorKind
IngestionError
RawIngestionEvent
IngestionBatch
IngestionClient
MockIngestionClient
LiveIngestionClient
NormalizedBatchValidator
AcceptAllNormalizedBatchValidator
Phase0NormalizedBatchValidator
ValidationReport
IngestionOutcome
IngestionReport
IngestionSourceReport
IngestionRejectionSummary
ingest_once()
ingest_once_with_validator()
ingest_once_with_report()
```

Design boundary:

- `MockIngestionClient` используется для deterministic tests.
- `LiveIngestionClient` пока возвращает `NotImplemented` и не делает network calls.
- `ingest_once()` сохраняет raw events до normalized market events.
- `ingest_once_with_validator()` сохраняет raw events, затем валидирует normalized events и только после этого пишет их в journal.
- `ingest_once_with_report()` возвращает `IngestionOutcome` с `ValidationReport`; raw events сохраняются, accepted normalized events пишутся, rejected normalized events не пишутся.
- `Phase0NormalizedBatchValidator` проверяет identity fields, finite values, quote ordering и basic timestamp/value sanity без стратегических thresholds.
- `ValidationReport` содержит counters: `raw_events_received`, `normalized_events_received`, `normalized_events_accepted`, `normalized_events_rejected` и список `rejections`.
- `IngestionReport` агрегирует несколько `ValidationReport`: totals, counts by source и counts by rejection message.
- Ошибки API/reconnect/rate-limit не должны превращаться в trading rejection reasons; они относятся к ingestion health.

Sync форма выбрана намеренно, чтобы первый contracts layer компилировался без внешних dependencies. Async versions будут добавлены вместе с real HTTP/WebSocket adapters.

## Proposed Next

### `NormalizedMarketEvent`

Future alias/enum for all normalized events. Current `MarketEvent` already fills this role for MVP.

## Proposed Adapter Traits

Эти traits реализованы в sync форме. Примеры ниже показывают intended async shape для будущих real API adapters.

Правило MVP: adapters только читают market data и возвращают raw/normalized events. Они не размещают orders.

### `DeribitDiscoveryAdapter`

```rust
#[async_trait]
pub trait DeribitDiscoveryAdapter {
    async fn list_eth_options(&self) -> Result<Vec<DeribitInstrument>, AdapterError>;

    async fn get_option_snapshot(
        &self,
        instrument_id: &str,
    ) -> Result<DeribitOptionQuote, AdapterError>;

    async fn get_raw_option_snapshot(
        &self,
        instrument_id: &str,
    ) -> Result<RawDeribitEvent, AdapterError>;
}
```

Proposed supporting type:

```rust
pub struct DeribitInstrument {
    pub instrument_id: String,
    pub underlying: String,
    pub expiry_ts_ms: i64,
    pub strike: f64,
    pub option_kind: OptionKind,
}
```

Design notes:

- `list_eth_options()` используется для discovery.
- `get_raw_option_snapshot()` нужен для записи raw payload в `event_journal`.
- `get_option_snapshot()` возвращает normalized quote для feature calculation.
- Реализация должна сохранять raw event до normalized event.

### `PolymarketDiscoveryAdapter`

```rust
#[async_trait]
pub trait PolymarketDiscoveryAdapter {
    async fn list_crypto_markets(&self) -> Result<Vec<PolymarketMarket>, AdapterError>;

    async fn get_market_snapshot(
        &self,
        market_slug: &str,
        outcome: &str,
    ) -> Result<PolymarketOutcomeQuote, AdapterError>;

    async fn get_raw_market_snapshot(
        &self,
        market_slug: &str,
    ) -> Result<RawPolymarketEvent, AdapterError>;
}
```

Proposed supporting type:

```rust
pub struct PolymarketMarket {
    pub event_slug: String,
    pub market_slug: String,
    pub question: String,
    pub outcomes: Vec<String>,
    pub close_ts_ms: Option<i64>,
    pub liquidity_usd: Option<f64>,
}
```

Design notes:

- `list_crypto_markets()` используется для candidate discovery.
- `get_raw_market_snapshot()` сохраняет raw Gamma/CLOB payload.
- `get_market_snapshot()` возвращает normalized outcome quote.
- `outcome` должен быть явным, например `Yes`, чтобы не смешивать sides.

### `EventJournal`

```rust
#[async_trait]
pub trait EventJournal {
    async fn append_raw_deribit_event(
        &self,
        event: &RawDeribitEvent,
    ) -> Result<(), JournalError>;

    async fn append_raw_polymarket_event(
        &self,
        event: &RawPolymarketEvent,
    ) -> Result<(), JournalError>;

    async fn append_market_event(
        &self,
        event: &MarketEvent,
    ) -> Result<(), JournalError>;

    async fn read_events_for_replay(
        &self,
        filter: ReplayEventFilter,
    ) -> Result<Vec<MarketEvent>, JournalError>;
}
```

### `BasisObservationWriter`

Sync writer interface для derived probability-basis observations:

```rust
pub trait BasisObservationWriter {
    fn append_basis_observation(
        &mut self,
        observation: BasisObservation,
    ) -> Result<(), ObservationWriteError>;
}
```

Текущая реализация:

```text
InMemoryBasisObservationWriter
```

PostgreSQL implementation добавляется позже, когда появится database connector layer.

### `BasisObservationRowWriter`

Storage-row interface:

```rust
pub trait BasisObservationRowWriter {
    fn append_basis_observation_row(
        &mut self,
        row: BasisObservationRow,
    ) -> Result<(), ObservationWriteError>;
}
```

`PostgresBasisObservationAdapter` пока содержит только stable SQL template:

```text
INSERT INTO basis_observations (...)
VALUES ($1, to_timestamp($2::double precision / 1000.0), ...)
```

Он не открывает соединение и не зависит от `sqlx`, `tokio-postgres` или других DB crates.

Proposed replay filter:

```rust
pub struct ReplayEventFilter {
    pub start_ts_ms: i64,
    pub end_ts_ms: i64,
    pub event_types: Vec<String>,
    pub instrument_ids: Vec<String>,
    pub config_version: Option<String>,
}
```

## Error Types

На первом этапе реализованы simple project error enums. Adapter errors должны различать:

- network/API failure,
- malformed payload,
- stale data,
- missing required field,
- unsupported instrument/event,
- rate limit.

Это важно, потому что rejection reports должны отличать плохой market candidate от временной API ошибки.

## Tests

Текущий contracts layer покрыт unit tests:

- mock Deribit discovery/snapshot/raw lookup,
- mock Polymarket discovery/snapshot/raw lookup,
- unsupported instrument errors,
- raw event preservation,
- duplicate event rejection,
- deterministic replay ordering/filtering.
- probability-basis matched/rejected decisions,
- golden replay fixture report.
- Black-Scholes edge cases: zero/negative IV, expired option, deep ITM/OTM behavior, deterministic normal CDF approximation.
- BasisObservation mapping and duplicate observation rejection.
- BasisObservationRow column order and PostgreSQL insert SQL skeleton.
- Ingestion skeleton: raw-before-normalized write order, validator-before-normalized-write boundary, validation report counters, API error without writes, live client `NotImplemented`, API error/reconnect fixture parsing, ingestion manifest parsing.
- Ingestion semantic golden reports: `fixtures/ingestion/*_report.json` сравниваются с `IngestionReport::to_json()`.
- Thin orchestration: Deribit mock batch + Polymarket mock batch -> `EventJournal` -> `match_from_market_events()` -> `BasisObservation`.
- Negative orchestration: malformed Polymarket quote сохраняет raw event, но не создает `BasisObservation`.

## Design Rule

Raw events must be persisted before normalization. Normalized events must be deterministic functions of raw event + schema version + config version.
