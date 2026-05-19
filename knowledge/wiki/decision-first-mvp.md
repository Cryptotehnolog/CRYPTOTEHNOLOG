---
type: decision
status: active
confidence: high
updated: 2026-05-20
sources:
  - project-review-2026-05-19
---

# Decision: First MVP

The first MVP is Deribit + Polymarket `probability_basis`.

Funding carry is postponed because the initial unhedged version is directional exposure with funding income, not a market-neutral arbitrage.

## MVP Scope

Included:

- Deribit and Polymarket market discovery,
- candidate event matching,
- probability and cost estimation,
- deterministic replay,
- observation storage,
- quality reports.

Excluded:

- live trading,
- AI agents in execution path,
- Kelly sizing,
- short Deribit options,
- short Polymarket outcomes.

## Success Criterion

The MVP succeeds only if it can produce auditable matched/rejected candidate reports with clear reasons and reproducible calculations.

