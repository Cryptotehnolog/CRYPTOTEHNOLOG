---
type: system
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
---

# Roadmap: MVP

Цель MVP - доказать или опровергнуть probability basis thesis без live trading.

## Phase 1: Knowledge And Contracts

Готово, когда:

- Deribit source note создана,
- Polymarket source note создана,
- strategy/risk pages созданы,
- event contracts определены,
- replay skeleton работает.

## Phase 2: Read-Only Data Adapters

Готово, когда:

- Deribit adapter получает ETH option snapshots,
- Polymarket adapter получает candidate event snapshots,
- raw payloads сохраняются в `event_journal`,
- normalized events воспроизводятся через replay.

## Phase 3: Matching And Observation

Готово, когда:

- matcher генерирует matched/rejected candidate reports,
- rejection reasons детерминированны,
- `basis_observations` заполняется,
- cost model явно вычитает fees/spread/slippage/mismatch penalty.

## Phase 4: Paper Review

Готово, когда:

- накоплено достаточно observations для statistical review,
- replay output воспроизводим,
- edge сохраняется после realistic costs,
- liquidity constraints не уничтожают thesis.

## Live Trading Gate

Live trading запрещен до отдельного decision review.

Минимальные условия для обсуждения live:

- positive expectation на собственных replay/paper данных,
- понятные risk limits,
- kill switch,
- no hidden LLM control,
- operational runbook,
- live-specific risk page.

## Failure Criteria

MVP считается неудачным, если:

- события нельзя надежно сопоставлять,
- spread исчезает после costs,
- liquidity слишком низкая,
- settlement mismatch не формализуется,
- observations не воспроизводятся.

