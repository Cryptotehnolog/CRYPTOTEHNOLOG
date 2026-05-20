---
type: system
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
---

# Example Config Parameters

Эта страница объясняет текущие параметры в `config/*.toml`. Значения здесь должны соответствовать файлам в `config/`.

## `config/strategies.toml`

### `[probability_basis]`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Включает probability basis strategy. |
| `min_net_edge_probability` | `0.025` | Минимальный net edge после costs. |
| `max_market_age_ms` | `3000` | Максимальный возраст market data. |
| `min_polymarket_liquidity_usd` | `1000.0` | Минимальная liquidity для candidate market. |
| `allow_short_deribit_options` | `false` | Запрещает short Deribit options в MVP. |
| `allow_short_polymarket_outcomes` | `false` | Запрещает short Polymarket outcomes в MVP. |

## `config/risk.toml`

### `[portfolio]`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `starting_capital_usd` | `100000.0` | Virtual capital для paper/replay. |
| `max_position_notional_fraction` | `0.01` | Max notional на одну позицию. |
| `max_strategy_notional_fraction` | `0.05` | Max notional на стратегию. |
| `max_total_margin_fraction` | `0.25` | Max aggregate margin usage. |
| `daily_loss_limit_fraction` | `0.02` | Daily loss limit. |
| `max_drawdown_fraction` | `0.05` | Max drawdown limit. |

### `[data_quality]`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `reject_stale_market_data` | `true` | Reject stale data. |
| `max_clock_skew_ms` | `1000` | Max allowed clock skew. |

## `config/venues.toml`

| Section | Parameter | Default |
| --- | --- | --- |
| `[deribit]` | `environment` | `testnet` |
| `[deribit]` | `base_url` | `https://test.deribit.com` |
| `[deribit]` | `ws_url` | `wss://test.deribit.com/ws/api/v2` |
| `[polymarket]` | `gamma_base_url` | `https://gamma-api.polymarket.com` |

## `config/instruments.toml`

`[[probability_basis_candidates]]` содержит стартовые research candidates.

| Parameter | Example | Meaning |
| --- | --- | --- |
| `underlying` | `ETH` | Underlying asset. |
| `target_price_usd` | `3000.0` | Threshold/strike candidate. |
| `event_date` | `2026-06-01` | Target event date. |
| `deribit_option_kind` | `call` | Option kind for matching. |
| `polymarket_query` | `ETH above 3000 June 1` | Search/query hint для Polymarket discovery. |

## `config/phase_gate.toml`

Machine-readable mirror для Phase 0 gate. Сейчас это documentation/config contract для будущей CI-проверки; сам CI еще не валидирует эти поля.

`scripts/check_phase_gate.ps1` читает этот файл и блокирует преждевременное появление LightRAG/MCP wiring, пока `phase_1_research_enabled = false`.

### `[phase]`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `current` | `phase_0_deterministic_core` | Текущая фаза проекта. |
| `phase_1_research_enabled` | `false` | Запрещает research-layer activation до Phase 0 gate. |
| `live_trading_enabled` | `false` | Явный запрет live trading. |

### `[phase_0_exit_gate]`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `min_normalized_observations` | `1000` | Минимум normalized observations. |
| `min_matched_opportunities` | `100` | Минимум matched opportunities. |
| `min_collection_days_without_replay_breaking_gaps` | `30` | Минимальный период сбора без gaps, ломающих replay. |
| `min_positive_net_edge_match_fraction` | `0.60` | Минимальная доля matched opportunities с positive net edge after costs. |
| `max_drawdown_fraction` | `0.05` | Максимальная допустимая paper drawdown. |
| `daily_loss_limit_fraction` | `0.02` | Максимальный simulated daily loss. |

### `[forbidden_until_phase_1]`

Эта секция перечисляет запреты, которые будущий CI сможет проверить автоматически: LightRAG installation/Docker/MCP wiring, ingestion в LightRAG, agent workflows на LightRAG, Hermes/OmniRoute в execution path и MCP dependency в deterministic core.

## Maintenance Note

Эта страница сейчас поддерживается вручную. Если config начнет часто меняться, нужен generator script из `config/*.toml`.
