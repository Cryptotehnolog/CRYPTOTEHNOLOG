---
type: strategy
status: draft
confidence: medium
stability: stable
updated: 2026-05-20
review_after: 2026-08-18
sources:
  - project-review-2026-05-19
---

# Strategy: Funding Carry

Funding carry - отложенная стратегия второго приоритета. Она не входит в первый MVP.

## Assumptions

Классическая market-neutral версия требует:

- short perpetual с положительным funding,
- long spot или другой hedge,
- контроль basis,
- учет fees, borrow/financing и margin.

Unhedged short perpetual не является арбитражем. Это directional exposure с funding income.

## Risks

- directional price risk,
- funding rate collapse,
- liquidation risk,
- hedge mismatch,
- low liquidity,
- exchange-specific margin rules.

## Current Status

Postponed. Мы не реализуем funding carry до тех пор, пока probability basis MVP не будет проверен или явно отклонен.

## Success Metrics

Будущая версия должна доказать:

- наличие hedge,
- reproducible funding income после costs,
- bounded drawdown,
- reliable data source,
- deterministic replay.

## Exit Criteria

Стратегия не должна идти в разработку, если hedge отсутствует или expected funding income не покрывает directional risk.

