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

# Schema: PostgreSQL Tables

Эта страница объясняет таблицы, созданные миграцией `migrations/0001_event_journal.sql`.

## `event_journal`

Append-only журнал событий (event journal). Это source of truth для raw и normalized events.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | `bigserial primary key` | Внутренний monotonic row id. |
| `event_id` | `text unique not null` | Stable event identifier. |
| `event_type` | `text not null` | Тип события: raw Deribit, raw Polymarket, normalized quote и т.п. |
| `source` | `text not null` | Источник события: `deribit`, `polymarket`, `replay`, `mock`. |
| `exchange_ts` | `timestamptz` | Timestamp от биржи/API, если доступен. |
| `received_ts` | `timestamptz not null default now()` | Timestamp получения системой. |
| `instrument_id` | `text` | Нормализованный instrument/market id. |
| `schema_version` | `integer not null` | Версия payload schema. |
| `config_version` | `text not null` | Версия config, применимая к событию. |
| `payload` | `jsonb not null` | Raw или normalized JSON payload. |

Indexes:

- `idx_event_journal_type_received` для чтения событий по типу и времени.
- `idx_event_journal_instrument_received` для чтения истории по инструменту.

## `replay_runs`

Metadata deterministic replay runs.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | `bigserial primary key` | Внутренний row id. |
| `run_id` | `text unique not null` | Stable replay run id. |
| `started_at` | `timestamptz default now()` | Время старта replay. |
| `finished_at` | `timestamptz` | Время завершения replay. |
| `config_version` | `text not null` | Config version replay run. |
| `input_event_count` | `integer default 0` | Количество входных events. |
| `output_event_count` | `integer default 0` | Количество выходных events/observations. |
| `notes` | `text` | Человеческие notes/debug context. |

## `basis_observations`

Derived observations по probability basis.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | `bigserial primary key` | Внутренний row id. |
| `event_id` | `text unique not null` | Stable observation id. |
| `observed_at` | `timestamptz not null` | Время observation. |
| `deribit_instrument_id` | `text not null` | Deribit option instrument. |
| `polymarket_market_slug` | `text not null` | Polymarket market slug. |
| `model_probability` | `numeric not null` | Deribit-derived model probability. |
| `polymarket_mid_probability` | `numeric not null` | Mid probability на Polymarket. |
| `gross_edge_probability` | `numeric not null` | Разница до costs. |
| `estimated_cost_probability` | `numeric not null` | Estimated fees/spread/slippage/mismatch costs. |
| `net_edge_probability` | `numeric not null` | Net edge после estimated costs. |
| `survives_costs` | `boolean not null` | Проходит ли threshold после costs. |

## Design Rule

`event_journal` должен заполняться до любых derived calculations. Если derived observation нельзя воспроизвести из journal + config, это bug.

