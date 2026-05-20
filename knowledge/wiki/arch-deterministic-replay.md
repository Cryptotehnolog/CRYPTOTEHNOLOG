---
type: workflow
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
---

# Architecture: Deterministic Replay

Deterministic replay - обязательная способность MVP. Один и тот же event log и config version должны давать один и тот же output.

## Inputs

- `event_journal` rows,
- config files,
- schema version,
- replay time range,
- strategy version.

Позже можно добавить CSV/Parquet export, но source of truth остается PostgreSQL event journal.

## Replay Flow

```text
read ordered events
  -> normalize by schema version
  -> calculate features
  -> run strategy/risk rules
  -> write replay output
  -> compare with golden output
```

## Regression Testing

Для каждого replay fixture нужно сохранять:

- input event IDs,
- config version,
- expected observations,
- expected rejection reasons,
- output hash.

Если изменение кода меняет output, разработчик должен видеть diff и причину.

## Use Cases

- backtesting,
- debugging market matching,
- validating refactors,
- replaying bad observations,
- comparing probability models.

## Current Runner

`crates/replay` содержит Phase 0 probability-basis replay runner.

Текущая версия использует fixed mock `MarketEvent` fixture, прогоняет `match_from_market_events` и печатает deterministic matched/rejected report:

```text
matched|ETH-20260601-3000-C|eth-above-3000-june-1|net_edge=0.081338|survives=true
rejected|InsufficientLiquidity|ETH-20260601-3000-C|eth-above-3000-low-liquidity
```

Это еще не historical replay из PostgreSQL, но уже byte-stable smoke test для matcher semantics.

## Non-Goals

- Live execution.
- LLM-driven strategy changes.
- Hidden mutable state.
