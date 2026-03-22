# РЕЗУЛЬТАТ ФАЗЫ P_9: STRATEGY FOUNDATION

## Статус

- Целевая версия финализации: `v1.9.0`
- Фаза: `P_9`
- Итоговый статус: `closed`
- Реализация: узкая `Strategy Foundation`

---

## Что реально вошло в P_9

- Отдельный package boundary:
  - `src/cryptotechnolog/strategy`
- Typed strategy contracts:
  - strategy direction
  - strategy status
  - strategy validity / readiness semantics
  - strategy freshness semantics
  - strategy context
  - strategy action candidate
- Typed strategy event vocabulary:
  - `STRATEGY_CANDIDATE_UPDATED`
  - `STRATEGY_ACTIONABLE`
  - `STRATEGY_INVALIDATED`
- Explicit `StrategyRuntime` с:
  - `start()` / `stop()`
  - query/state-first surface
  - diagnostics
  - deterministic lifecycle / freshness handling
- Deterministic strategy context assembly внутри strategy layer поверх signal truth
- Один узкий deterministic strategy contour
- Composition-root integration в `bootstrap`
- Operator-visible runtime / health / readiness truth для strategy layer
- Hardening strategy lifecycle semantics:
  - `CANDIDATE`
  - `ACTIONABLE`
  - `SUPPRESSED`
  - `INVALIDATED`
  - `EXPIRED`

---

## Архитектурный summary

`P_9` не строит portfolio governor и не открывает execution platform.

Фактическая архитектурная роль фазы:

- strategy layer становится отдельным consumer contour;
- strategy layer не владеет:
  - `market_data`
  - `analysis`
  - `intelligence`
  - `signals`
  - `risk`
- `StrategyContext` собирается внутри strategy layer, а не в bootstrap;
- composition root только проводит signal truth в `StrategyRuntime`;
- event truth не подменяет query/state truth;
- strategy runtime не подменяет execution или portfolio governance.

Ключевые границы:

- signal layer остаётся source of truth для `SignalSnapshot`;
- strategy layer работает поверх signal truth как отдельный runtime contour;
- execution, portfolio и supervisor semantics остаются future lines.

---

## Verification truth

Подтверждено на phase scope `P_9`:

- unit tests для:
  - contracts
  - runtime
  - lifecycle / freshness semantics
  - invalidation / degraded behavior
- bootstrap-level unit tests для:
  - explicit wiring
  - strategy diagnostics в runtime truth
  - boundary между bootstrap и strategy layer
- integration tests для:
  - composition-root wiring
  - strategy event publication semantics
  - non-actionable / invalidated paths
  - shutdown / cleanup truth
- Redis/DB-backed integration subset:
  - `tests/integration/test_bootstrap_integration.py`
- `ruff format --check`
- `ruff check`
- `mypy` через корректный project invocation с `MYPYPATH=src`

Честный нюанс verification:

- relevant integration subset подтверждает real external environment path через Redis и TimescaleDB;
- остаётся только неблокирующий `PytestCacheWarning` по `.pytest_cache`.

Это не считается blocker-ом для closure текущего узкого scope `P_9`.

---

## Что сознательно не вошло в P_9

- `Portfolio Governor`
- `CapitalManager`
- `VelocityMonitor`
- `ExposureLimits`
- `DrawdownProtection`
- `OpportunityEngine`
- `MetaClassifier`
- `StrategyManager`
- multi-strategy orchestration
- portfolio / supervisor logic
- pyramiding
- execution semantics beyond strategy foundation
- persistence-first implementation line
- broad analysis/intelligence expansion
- dashboard / UI line

---

## Follow-up lines после P_9

Следующие линии могут открываться только отдельно:

- opportunity / ranking line
- meta / selection line
- strategy manager / orchestration line
- portfolio / supervisor line
- execution expansion line
- persistence hardening line

Они не являются частью closure scope `P_9`.

---

## Итоговая truth

`P_9` реализована как узкая `Strategy Foundation`:

- typed strategy contracts;
- explicit `StrategyRuntime`;
- deterministic strategy context assembly;
- narrow production-compatible runtime integration;
- operator-visible lifecycle truth;
- strategy candidate invalidation / expiry / degraded semantics.

Это foundation для следующих strategy/opportunity/orchestration фаз, а не скрытый portfolio governor или supervisor runtime.
