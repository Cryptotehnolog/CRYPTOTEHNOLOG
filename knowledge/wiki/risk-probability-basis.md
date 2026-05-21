---
type: risk
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - deribit-api-2026-05-20
  - polymarket-api-2026-05-20
  - project-review-2026-05-19
---

# Risk: Probability Basis

Probability basis выглядит как арбитраж только на поверхности. В MVP мы считаем его risky basis observation, пока собственные данные не докажут обратное.

## MVP Ограничения

- No live orders.
- No short Deribit options.
- No short Polymarket outcomes.
- No Kelly sizing.
- No AI agent in execution path.
- Все raw events сохраняются до derived calculations.

## Почему Запрещены Short Options

Short option positions создают convex tail risk. Маленькая ошибка в implied probability или settlement mapping может привести к крупному убытку.

Для MVP short options не нужны: сначала мы проверяем data/matching thesis.

## Почему Запрещены Short Polymarket Outcomes

Short/negative exposure на prediction market может иметь operational complexity:

- settlement mismatch,
- liquidity asymmetry,
- capital lockup,
- resolution risk,
- execution constraints.

MVP не должен зависеть от этого.

## Rejection Rules

Candidate должен быть rejected, если:

- underlying не совпадает,
- threshold нельзя извлечь однозначно,
- event date не сопоставляется с Deribit expiry,
- settlement wording неоднозначен,
- Polymarket liquidity ниже минимального порога,
- spread слишком широкий,
- market data stale,
- model probability зависит от непроверенного IV assumption.

В Phase 0 `deribit_expiry_nearby`, `polymarket_date_mismatch`, `strike_mismatch` и `missing` не являются чистыми basis candidates. Их можно логировать как diagnostic observations для улучшения discovery, но они не должны попадать в clean candidate metrics, paper-trading readiness или live gate.

## Cost Assumptions

Все cost assumptions должны быть явными:

- Deribit bid/ask spread,
- Polymarket bid/ask spread,
- fees,
- slippage,
- mismatch penalty.

Если cost нельзя оценить, observation получает `confidence: low`.

## Success Condition

Risk page считается актуальной, пока MVP не размещает live orders. Перед live phase нужна новая risk review page.
