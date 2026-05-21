---
type: strategy
status: active
confidence: medium
stability: volatile
updated: 2026-05-21
review_after: 2026-06-19
sources:
  - deribit-api-2026-05-20
  - polymarket-api-2026-05-20
  - quantum-bot-polymarket-2026-05-20
  - project-review-2026-05-19
---

# Strategy: Probability Basis

Probability basis - первая MVP-стратегия CRYPTOTEHNOLOG. Она сравнивает Deribit option-implied probabilities с Polymarket outcome prices и ищет расхождения, которые переживают fees, spread, slippage, liquidity и settlement mismatch.

Это research strategy, не live trading strategy.

## Assumptions

- Polymarket outcome price приблизительно отражает market-implied probability события.
- Deribit option market содержит информацию о future distribution underlying asset.
- Сопоставление события возможно только если underlying, threshold, event date и settlement wording достаточно близки.
- Любой observed edge должен считаться gross edge, пока не вычтены costs и mismatch penalties.

## Matching Algorithm

Первый deterministic matcher должен работать консервативно:

1. Получить active Polymarket crypto events через Gamma API.
2. Отфильтровать events по underlying: сначала только `ETH`.
3. Извлечь threshold из question/slug, например `ETH above 3000`.
4. Извлечь target date и сравнить с Deribit option expiry.
5. Найти ближайший Deribit ETH call/put с matching strike и expiry.
6. Проверить settlement wording: если event wording неоднозначен, reject.
7. Проверить liquidity и spread на обеих площадках.
8. Сохранить matched/rejected decision с reason.

## Edge Formula

Минимальная рабочая формула:

```text
polymarket_mid_probability = (bid_probability + ask_probability) / 2

gross_mid_edge = deribit_model_probability - polymarket_mid_probability

if deribit_model_probability >= polymarket_mid_probability:
    polymarket_executable_probability = ask_probability
else:
    polymarket_executable_probability = bid_probability

gross_executable_edge = deribit_model_probability - polymarket_executable_probability
estimated_cost = deribit_spread_cost + polymarket_spread_cost + fees + slippage + mismatch_penalty
net_edge = abs(gross_executable_edge) - estimated_cost
```

Кандидат считается интересным только если:

```text
net_edge >= min_net_edge_probability
```

Текущий config использует `min_net_edge_probability = 0.025`.

## Phase 0 Alignment Policy

В Phase 0 только `basis_alignment_status = exact` считается чистым basis candidate.

Все остальные статусы являются diagnostic-only:

- `deribit_expiry_nearby` - Deribit option выбран как ближайший доступный expiry, но дата не совпадает с target event date.
- `polymarket_date_mismatch` - Polymarket settlement/end date не совпадает с target event date.
- `strike_mismatch` - выбранный option strike не совпадает с target threshold.
- `missing` - одна из сторон пары не выбрана.

Diagnostic-only candidates можно сохранять и анализировать для улучшения discovery, но их нельзя считать подтверждением working edge, включать в clean candidate metrics или использовать как основание для paper/live trading gate.

`gross_mid_edge` остается диагностикой, но не должен быть решающим edge для matched decision. Это защищает Phase 0 от ложноположительных сигналов, где midpoint выглядит привлекательным, но executable side рынка уже уничтожает edge.

Если `gross_mid_edge` после costs прошел бы `min_net_edge_probability`, но `gross_executable_edge` после costs не проходит threshold, matcher отклоняет пару как `MidEdgeFalsePositive`. Этот счетчик должен быть виден в replay reports и CI, потому что он показывает, сколько кажущихся opportunities исчезает при переходе от midpoint к executable pricing.

## Probability Model

На первом этапе нельзя притворяться, что модель уже решена.

MVP допускает два режима:

- использовать Deribit IV/mark data как input и явно помечать model risk;
- параллельно сохранять raw quotes, чтобы позже пересчитать probabilities другой моделью.

Open question: нужна отдельная спецификация `source-deribit-iv-calculation.md`, если Deribit IV fields и Black-Scholes/Merton assumptions окажутся недостаточно прозрачными.

## Implementation Status

Первый matcher skeleton реализован в `crates/common/src/probability_basis.rs`.

Текущий scope:

- deterministic pair matching на mock data,
- matched/rejected decisions,
- rejection reasons,
- net edge calculation,
- separate mid-edge vs executable-edge reporting,
- golden replay fixture test.

`model_probability` теперь рассчитывается через Black-Scholes `N(d2)` для call-like события `S_T > K` с MVP assumptions `r=0`, `q=0`.

Ограничение: модель все еще использует single-strike `mark_iv` и не строит volatility surface. Это достаточно для deterministic MVP tests, но не является финальной pricing model.

## Risks

- settlement mismatch,
- expiry mismatch,
- low liquidity,
- stale quotes,
- model risk,
- Polymarket resolution risk,
- Deribit smile/skew interpolation risk.

Подробно: [Risk: Probability Basis](risk-probability-basis.md).

## Success Metrics

MVP считается исследовательски полезным, если он производит:

- auditable matched/rejected candidate reports,
- reproducible net edge calculations,
- preserved raw events,
- deterministic replay output,
- достаточное количество observations для последующего statistical review.

## Exit Criteria

Стратегия отклоняется или понижается в приоритете, если:

- meaningful matches встречаются слишком редко,
- observed net edge исчезает после costs,
- settlement mismatch нельзя надежно формализовать,
- liquidity недостаточна даже для paper-realistic simulation.
