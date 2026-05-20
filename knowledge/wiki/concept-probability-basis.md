---
type: concept
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
---

# Probability Basis

Probability basis - текущая research-формулировка для сравнения event probabilities, подразумеваемых опционами Deribit, с ценами prediction markets на Polymarket.

Пока это не называется arbitrage. Спред может отражать реальные costs и risks:

- разные settlement definitions,
- expiry mismatch,
- liquidity mismatch,
- transaction costs,
- capital lockup,
- model risk,
- short-option tail risk,
- prediction-market resolution risk.

## Вопрос MVP

Можем ли мы надежно сопоставлять Deribit ETH options с Polymarket crypto events и наблюдать net probability spread, который переживает realistic costs?

## Текущее Ограничение

MVP только наблюдает и воспроизводит данные (observation and replay). Он не размещает live orders.
