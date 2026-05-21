---
type: workflow
status: active
confidence: high
stability: volatile
updated: 2026-05-21
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

## Golden Fixture Policy

Golden fixture - это regression guard, а не замена unit tests.

Основная семантика проверяется Rust tests в `crates/replay/src/lib.rs`:

- количество decisions,
- количество `BasisObservation`,
- key instrument/market ids,
- numeric edge с tolerance.

JSON regression является основным semantic fixture check.

CLI text regression остается smoke test, который проверяет, что command-line output не разъехался с human-readable expected report.

Обновлять `fixtures/probability_basis/golden_report.json` и `fixtures/probability_basis/golden_report.txt` нужно только через:

```powershell
.\scripts\update_golden_fixture.ps1
```

`scripts/check_golden_fixture_current.ps1` запускает update script и падает, если после перегенерации JSON или text fixture меняется. Этот check включен в `scripts/check_all.ps1` и CI.

Если golden report меняется, PR/commit должен объяснять, какое изменение matcher/pricing/replay behavior это вызвало.

## Use Cases

- backtesting,
- debugging market matching,
- validating refactors,
- replaying bad observations,
- comparing probability models.

## Current Runner

`crates/replay` содержит Phase 0 probability-basis replay runner.

Текущая версия читает fixture files, перечисленные в `fixtures/manifest.toml`, преобразует строки в `MarketEvent`, прогоняет `match_from_market_events` и печатает deterministic matched/rejected report.

Пример human-readable output:

```text
metadata|pricing_model_version=black_scholes_single_strike_v1
summary|matched=1|rejected=1|net_edge_count=1|net_edge_avg=0.081338|net_edge_min=0.081338|net_edge_max=0.081338
summary_rejection|reason=InsufficientLiquidity|count=1
matched|ETH-20260601-3000-C|eth-above-3000-june-1|mid_edge=0.091338|executable_edge=0.081338|net_edge=0.071338|survives=true
rejected|InsufficientLiquidity|ETH-20260601-3000-C|eth-above-3000-low-liquidity
```

Manifest scenarios:

| Scenario | Покрытие | Expected result |
| --- | --- | --- |
| `probability_basis_golden` | baseline: один matched signal и один low-liquidity reject | `Matched`, `InsufficientLiquidity` |
| `probability_basis_edge_below_threshold` | strategy threshold boundary после costs | `EdgeBelowThreshold` |
| `probability_basis_mid_edge_false_positive` | midpoint edge выглядит привлекательным, но executable side после spread/costs не проходит threshold | `MidEdgeFalsePositive` |
| `probability_basis_invalid_quote` | data-quality rejection path для некорректной quote book probability | `InvalidQuote` |
| `probability_basis_expiry_mismatch` | temporal/event alignment между Deribit expiry и Polymarket event timestamp | `ExpiryMismatch` |

Еще не покрыты отдельными replay scenarios: `MissingDeribitQuote`, `MissingPolymarketQuote`, `UnsupportedUnderlying`, `UnsupportedOptionKind`, `ExpiredOption`, `InvalidModelInput`.

Primary expected output для каждого scenario хранится в JSON report, указанном в `fixtures/manifest.toml`.

Human-readable text output для каждого scenario хранится в text report, указанном в `fixtures/manifest.toml`.

`scripts/run_replay_regression.ps1` читает `fixtures/manifest.toml`, запускает runner для каждого scenario и сравнивает JSON/text output с golden reports. Скрипт включен в `scripts/check_all.ps1` и CI.

`crates/replay/src/lib.rs` содержит library-level replay core. `crates/replay/src/main.rs` является тонкой CLI-оберткой.

Runner также создает matched `BasisObservation` records через `InMemoryBasisObservationWriter`, но пока не пишет их в PostgreSQL. Storage boundary для будущей записи уже определен через `BasisObservationRow` и `PostgresBasisObservationAdapter` skeleton.

Это еще не historical replay из PostgreSQL, но уже byte-stable smoke test для matcher semantics и observation contract.

## Semantic Output Contract

`ReplayReport` в `crates/replay/src/lib.rs` является semantic report contract.

`ReplaySummary` является агрегированным слоем поверх `ReplayReport` и содержит:

- количество `matched` и `rejected` decisions,
- количество `midpoint_false_positive` rejections,
- количество rejected decisions по `reason`,
- `sample_count`, average, min и max `net_edge_probability`.

Статистика `net_edge_probability` считается только по matched entries. Если matched entries отсутствуют, `average`, `min` и `max` должны быть `null` в JSON и `none` в text output. Нельзя подставлять `0`, потому что это исказит аналитику.

Он генерирует:

- JSON report как основной machine-readable эталон,
- text report как human-readable CLI output.

Текущий JSON формируется через typed `serde Serialize` contract, а не ручной `format!()`/конкатенацией строк.

`fixtures/manifest.toml` является registry для replay scenarios. Новые scenarios должны добавляться туда вместе с input fixture, primary JSON report и secondary text report.

## Network Policy

Default CI и `scripts/check_all.ps1` не должны обращаться к Deribit, Polymarket или другим внешним API.

Future network integration tests должны быть отдельным workflow/profile с явным opt-in.

## Backtest Automation Status

`run_backtest.ps1` с Sharpe, win rate и max drawdown пока не реализуется. Причина: еще нет полноценного time series PnL/trades. Такой скрипт станет полезен после появления `basis_observations`, simulated positions и realized/unrealized PnL model.

## Non-Goals

- Live execution.
- LLM-driven strategy changes.
- Hidden mutable state.
