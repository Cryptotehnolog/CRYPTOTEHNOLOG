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

Важно: часть контрактов уже реализована в `crates/common/src/events.rs`, а часть является proposed next step.

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

## Proposed Next

### `RawDeribitEvent`

Raw API payload wrapper before normalization.

```text
RawDeribitEvent
  meta
  endpoint_or_channel
  payload_json
```

### `RawPolymarketEvent`

Raw API payload wrapper before normalization.

```text
RawPolymarketEvent
  meta
  api_layer: Gamma|CLOB
  payload_json
```

### `NormalizedMarketEvent`

Future alias/enum for all normalized events. Current `MarketEvent` already fills this role for MVP.

## Proposed Adapter Traits

### `DeribitDiscoveryAdapter`

```text
list_eth_options() -> Vec<DeribitInstrument>
get_option_snapshot(instrument_id) -> DeribitOptionQuote
```

### `PolymarketDiscoveryAdapter`

```text
list_crypto_markets() -> Vec<PolymarketMarket>
get_market_snapshot(market_slug) -> PolymarketOutcomeQuote
```

### `EventJournal`

```text
append_event(event)
read_events_for_replay(range, filters)
```

## Design Rule

Raw events must be persisted before normalization. Normalized events must be deterministic functions of raw event + schema version + config version.

