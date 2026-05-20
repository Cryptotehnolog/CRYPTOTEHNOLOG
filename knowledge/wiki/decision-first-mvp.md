---
type: decision
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
---

# Решение: Первый MVP

Первый MVP - Deribit + Polymarket `probability_basis`.

Funding carry отложен, потому что начальная unhedged-версия является directional exposure с funding income, а не market-neutral arbitrage.

## Scope MVP

Входит:

- Deribit and Polymarket market discovery,
- candidate event matching,
- probability and cost estimation,
- deterministic replay,
- observation storage,
- quality reports.

Не входит:

- live trading,
- AI agents in execution path,
- Kelly sizing,
- short Deribit options,
- short Polymarket outcomes.

## Критерий Успеха

MVP успешен только если может выдавать auditable matched/rejected candidate reports с понятными причинами и воспроизводимыми calculations.
