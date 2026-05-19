---
type: concept
status: active
confidence: medium
updated: 2026-05-20
sources:
  - project-review-2026-05-19
---

# Probability Basis

Probability basis is the current research framing for comparing Deribit option-implied event probabilities against Polymarket prediction-market prices.

This is not yet called arbitrage. The spread may reflect real costs and risks:

- different settlement definitions,
- expiry mismatch,
- liquidity mismatch,
- transaction costs,
- capital lockup,
- model risk,
- short-option tail risk,
- prediction-market resolution risk.

## MVP Question

Can we reliably match Deribit ETH options to Polymarket crypto events and observe a net probability spread that survives realistic costs?

## Current Constraint

The MVP is observation and replay only. It must not place live orders.

