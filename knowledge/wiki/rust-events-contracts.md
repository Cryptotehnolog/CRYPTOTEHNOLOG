---
type: system
status: active
confidence: medium
stability: volatile
updated: 2026-05-21
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
| `target_expiry_ts_ms` | `i64` | Event/settlement target timestamp для expiry matching с Deribit option. |
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
| `polymarket_executable_probability` | `f64` | Polymarket side used for executable edge: ask when model is above midpoint, bid when model is below midpoint. |
| `gross_mid_edge_probability` | `f64` | Diagnostic midpoint edge before costs. Not used as decisive edge. |
| `gross_executable_edge_probability` | `f64` | Executable-side edge before costs. |
| `gross_edge_probability` | `f64` | Backward-compatible canonical gross edge; currently equal to `gross_executable_edge_probability`. |
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
write_basis_observation_rows(observations, writer)
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
schema_version
config_version
```

`observed_at` в row boundary передается как `observed_at_ts_ms`, а future PostgreSQL adapter должен конвертировать milliseconds в `timestamptz`.

### `EventJournalRow`

`EventJournalRow` - PostgreSQL-oriented serialization boundary для будущей таблицы `event_journal`.

Он отделяет raw/normalized event domain objects от storage row contract:

```text
RawDeribitEvent | RawPolymarketEvent | MarketEvent
  -> EventJournalRow
  -> future PostgreSQL adapter
```

Fixed column order:

```text
event_id
event_type
source
exchange_ts
received_ts
instrument_id
schema_version
config_version
payload
```

`exchange_ts` и `received_ts` в row boundary передаются как Unix milliseconds, а future PostgreSQL adapter должен конвертировать их через `to_timestamp(ms / 1000.0)`. `payload` хранится как JSON text для future `jsonb` insert.

`InMemoryEventJournal` сохраняет append-order `EventJournalRow` snapshots рядом с raw и normalized in-memory collections. Это нужно для Phase 0 vertical-slice тестов: мы проверяем не только replay из normalized events, но и то, что каждое принятое событие имеет будущую PostgreSQL-oriented row representation.

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
- `InMemoryBasisObservationRowWriter`.
- `PostgresBasisObservationAdapter` skeleton без real DB connection.
- `PostgresEventJournalAdapter` skeleton без real DB connection.
- `PostgresEventJournalWriter` feature-gated skeleton за `postgres-writer` без real DB connection.
- `InMemoryEventJournalRowWriter` для тестов storage-row boundary без PostgreSQL подключения.

Также реализован probability-basis matcher skeleton:

- `ProbabilityBasisConfig`,
- `MatchDecision`,
- `RejectionReason`,
- `match_probability_basis()`,
- `match_from_market_events()`.
- Black-Scholes `N(d2)` probability calculation для call-like events.
- `BasisObservationWriter` interface без PostgreSQL подключения.
- `BasisObservationRowWriter` interface для storage-row layer.
- `EventJournalRowWriter` interface для event-journal storage-row layer.

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
LiveHttpTransport
DisabledHttpTransport
FixtureHttpTransport
ReqwestHttpTransport
LiveIngestionProbeReport
MockIngestionClient
LiveIngestionClient
DeribitOptionDiscoveryCriteria
DeribitDiscoveredOption
DeribitInstrumentName
DeribitLiveIngestionClient
PolymarketMarketDiscoveryCriteria
PolymarketDiscoveredMarket
PolymarketClobBookQuote
PolymarketLiveIngestionClient
NormalizedBatchValidator
AcceptAllNormalizedBatchValidator
Phase0NormalizedBatchValidator
ValidationReport
IngestionOutcome
IngestionReport
IngestionSourceReport
IngestionRejectionSummary
Phase0PipelineReport
JsonPayloadParser
ingest_once()
ingest_once_with_validator()
ingest_once_with_report()
```

Design boundary:

- `MockIngestionClient` используется для deterministic tests.
- `LiveIngestionClient` пока возвращает `NotImplemented` и не делает network calls.
- `LiveHttpTransport` задает boundary `GET url -> payload_json` без привязки к конкретному HTTP crate.
- `DisabledHttpTransport` является default no-network transport.
- `FixtureHttpTransport` используется в tests для проверки live URL -> payload -> `IngestionBatch` flow без реальной сети.
- `ReqwestHttpTransport` доступен только при feature `network-integration`; default CI его не компилирует и не запускает.
- `LiveIngestionProbeReport` фиксирует diagnostic connectivity result: endpoint, url, status, payload bytes, latency_ms, error kind и error message.
- `DeribitOptionDiscoveryCriteria` и `DeribitDiscoveredOption` задают read-only discovery boundary для выбора ближайшего Deribit option instrument перед ticker polling.
- `DeribitInstrumentName` является typed parser boundary для Deribit names вида `ETH-1JUN26-3000-C` и fixture-friendly `ETH-20260601-3000-C`; он не заменяет все `instrument_id: String` в проекте и пока применяется только в discovery/ticker parsing boundary.
- `DeribitLiveIngestionClient` строит read-only `public/get_instruments` и `public/ticker` URLs, выбирает option candidate из instruments payload и парсит fixture-shaped и real-shaped Deribit JSON-RPC ticker payloads в raw + normalized Deribit events; default `poll_once()` остается `NotImplemented`.
- `PolymarketMarketDiscoveryCriteria` и `PolymarketDiscoveredMarket` задают read-only discovery boundary для выбора Polymarket Gamma market candidate перед market-by-slug polling.
- `PolymarketLiveIngestionClient` строит read-only Gamma markets, Gamma market-by-slug и CLOB `/book?token_id=...` URLs, выбирает candidate из markets payload и парсит fixture-shaped и real-shaped Polymarket Gamma market payloads в raw + normalized Polymarket outcome events; malformed/misaligned `outcomes` и `outcomePrices` возвращают `IngestionError`, а не panic; default `poll_once()` остается `NotImplemented`.
- `PolymarketClobBookQuote` задает read-only CLOB orderbook parser boundary: `token_id`, optional `market_id`, best bid/ask probability, best bid/ask size и optional `timestamp_ms`. В combined Gamma+CLOB fixture flow CLOB best bid/ask заменяет Gamma fallback `bid=ask=outcomePrice`, а raw CLOB payload сохраняется как `RawPolymarketEvent { api_layer: Clob }`.
- Manual `live_probe_replay` использует CLOB path для Polymarket executable pricing: после Gamma discovery он делает CLOB `/book` по выбранному `token_id`; если spread `ask - bid > 0.10`, report получает warning `WideExecutableSpread`, но не fail сам по себе.
- `JsonPayloadParser` убирает дублирование JSON field extraction между live adapter skeletons. Он поддерживает Deribit `result.*`, Deribit short option expiries вроде `1JUN26`, Polymarket `slug`, JSON-encoded `outcomes`/`outcomePrices`/`clobTokenIds`, string/number liquidity и Phase 0 fallback `bid=ask=outcomePrice` для Gamma snapshots без CLOB spread. Fallback используется только если `outcomePrices` согласован с выбранным outcome.
- Timestamp contract: `meta.exchange_ts_ms` означает quote/snapshot timestamp, `meta.received_ts_ms` означает local receive time, а `PolymarketOutcomeQuote.target_expiry_ts_ms` означает target event/settlement timestamp. Matcher использует `target_expiry_ts_ms` для expiry matching и `exchange_ts_ms` для quote freshness/skew checks.
- `payload_shape_version` в manual reports фиксирует parser contract, который обработал live payload: `deribit_get_instruments_v1`, `deribit_json_rpc_ticker_v1`, `polymarket_gamma_markets_v1`, `polymarket_gamma_market_v1`, `polymarket_clob_book_v1`.
- `selection_report` в `live_probe_replay_report.json` фиксирует выбранный Deribit instrument, target/selected expiry timestamps, человекочитаемые UTC dates, `strike_distance`, derived mismatch flags `strike_mismatch`/`expiry_mismatch`, агрегированный `selection_quality` (`missing`/`exact`/`nearby`/`mismatch`) и выбранный Polymarket market slug.
- `replay_summary.edge_quality` в `live_probe_replay_report.json` фиксирует matched, `EdgeBelowThreshold` и `MidEdgeFalsePositive` counters, чтобы manual live probe показывал, сколько real payload opportunities умирает на executable pricing.
- `live_probe_replay_report.json` строится через локальные `serde Serialize` DTO в producer binary, чтобы внешний report contract был отделен от внутреннего состояния probe/replay pipeline.
- `ingest_once()` сохраняет raw events до normalized market events.
- `ingest_once_with_validator()` сохраняет raw events, затем валидирует normalized events и только после этого пишет их в journal.
- `ingest_once_with_report()` возвращает `IngestionOutcome` с `ValidationReport`; raw events сохраняются, accepted normalized events пишутся, rejected normalized events не пишутся.
- `Phase0NormalizedBatchValidator` проверяет `schema_version == 1`, `received_ts_ms >= exchange_ts_ms`, identity fields, finite values, quote ordering и basic timestamp/value sanity без стратегических thresholds.
- `ValidationReport` содержит counters: `raw_events_received`, `normalized_events_received`, `normalized_events_accepted`, `normalized_events_rejected` и список `rejections`.
- `IngestionReport` агрегирует несколько `ValidationReport`: totals, counts by source и counts by rejection message.
- `Phase0PipelineReport` агрегирует offline vertical slice counts: raw events, normalized events, journal rows, match decisions, observations и observation rows.
- `render_phase0_pipeline_report` binary печатает `Phase0PipelineReport` JSON для поддержанного happy-path fixture-сценария.
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

`write_basis_observation_rows()` фиксирует derived storage boundary: рассчитанные `BasisObservation` превращаются в `BasisObservationRow`, а ошибка writer возвращается как `ObservationWriteError`, без panic и без silent drop.

`InMemoryBasisObservationRowWriter` реализует successful storage-row sink для tests: rows сохраняются в памяти, а duplicate `event_id` отклоняется как `ObservationWriteErrorKind::DuplicateObservation`.

### `EventJournalRowWriter`

Storage-row interface:

```rust
pub trait EventJournalRowWriter {
    fn append_event_journal_row(
        &mut self,
        row: EventJournalRow,
    ) -> Result<(), JournalError>;
}
```

`PostgresEventJournalAdapter` содержит stable SQL template:

```text
INSERT INTO event_journal (...)
VALUES ($1, $2, $3, to_timestamp($4::double precision / 1000.0), ...)
```

`PostgresEventJournalWriter` существует только за feature flag `postgres-writer`. Сейчас он фиксирует future writer API и возвращает `JournalErrorKind::Storage`, потому что реальный DB connector еще не выбран и не подключен к default Phase 0 path.

`InMemoryEventJournalRowWriter` реализует тот же `EventJournalRowWriter`, но сохраняет rows в памяти и отклоняет duplicate `event_id`. Он используется для vertical-slice тестов, чтобы ingestion path проверял future storage boundary без DB connector.

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
- executable-edge rejection when midpoint edge is a false positive,
- golden replay fixture report.
- Black-Scholes edge cases: zero/negative IV, expired option, deep ITM/OTM behavior, deterministic normal CDF approximation.
- BasisObservation mapping and duplicate observation rejection.
- BasisObservationRow column order and PostgreSQL insert SQL skeleton.
- BasisObservationRowWriter failure path returns `ObservationWriteErrorKind::Storage` without panic.
- Offline derived storage flow: ingestion -> matcher -> `BasisObservation` -> `InMemoryBasisObservationRowWriter`.
- Phase 0 pipeline report serializes offline vertical-slice counters through `serde Serialize`.
- Ingestion skeleton: raw-before-normalized write order, validator-before-normalized-write boundary, validation report counters, API error without writes, live client `NotImplemented`, API error/reconnect fixture parsing, ingestion manifest parsing.
- Ingestion semantic golden reports: `fixtures/ingestion/*_report.json` сравниваются с `IngestionReport::to_json()`.
- Deribit live skeleton: ticker URL construction, fixture payload parsing и explicit no-network `poll_once()` behavior.
- Polymarket live skeleton: Gamma market URL construction, fixture payload parsing и explicit no-network `poll_once()` behavior.
- Live adapter fixture parser: shared string/number extraction для Deribit/Polymarket fixture payloads без network calls и без external dependencies.
- Live HTTP transport boundary: `DisabledHttpTransport` blocks default network calls; `FixtureHttpTransport` feeds Deribit/Polymarket live skeletons from fixture payloads.
- Feature-gated network transport: `ReqwestHttpTransport` construct test runs only with `--features network-integration`; real connectivity check lives outside default CI.
- Live ingestion probe report: success/error reports include endpoint, url, payload bytes, latency and error kind without writing to journal or producing market events.
- Thin orchestration: Deribit mock batch + Polymarket mock batch -> `EventJournal` -> `match_from_market_events()` -> `BasisObservation`.
- Live/mock vertical slice: `FixtureHttpTransport` -> Deribit/Polymarket live parser boundary -> raw events -> normalized events -> append-order `EventJournalRow` snapshots -> replay matcher -> `BasisObservation`.
- Row-writer vertical slice: ingestion может зеркалировать raw/accepted normalized events в `EventJournalRowWriter`; тестовый `InMemoryEventJournalRowWriter` проверяет тот же row contract без PostgreSQL.
- Row-writer failure path: storage-row writer error возвращается как `IngestionErrorKind::JournalWrite`, без panic и без записи normalized events после сбоя raw-row mirror.
- Negative orchestration: malformed Polymarket quote сохраняет raw event, но не создает `BasisObservation`.

## Design Rule

Raw events must be persisted before normalization. Normalized events must be deterministic functions of raw event + schema version + config version.
