---
type: concept
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - deribit-api-2026-05-20
---

# Spec: Deribit IV Calculation

Эта страница фиксирует MVP-спецификацию расчета `deribit_model_probability` для стратегии [Probability Basis](strategy-probability-basis.md).

Важно: это не окончательная quantitative model. Это минимальная воспроизводимая модель для research/replay.

## Цель

Получить число:

```text
deribit_model_probability = P(S_T > K)
```

где:

- `S_T` - цена ETH в момент expiry,
- `K` - threshold/strike события,
- `T` - time to expiry в годах.

Это число сравнивается с Polymarket `Yes` midpoint probability.

## Black-Scholes Probability

Для call-like события `ETH > K` используем риск-нейтральную вероятность:

```text
d2 = (ln(S / K) + (r - q - 0.5 * sigma^2) * T) / (sigma * sqrt(T))
P(S_T > K) = N(d2)
```

Где:

- `S` - текущая цена underlying ETH,
- `K` - strike/threshold,
- `r` - risk-free rate,
- `q` - dividend/convenience yield; для MVP `q = 0`,
- `sigma` - implied volatility,
- `T` - time to expiry в годах,
- `N()` - standard normal CDF.

Для MVP:

```text
r = 0
q = 0
```

Это упрощение обязательно помечается как model risk.

## Какие Данные Нужны Из Deribit

Минимальный набор:

- instrument name,
- option kind: call/put,
- expiry timestamp,
- strike,
- bid/ask или mark price,
- `mark_iv` или другое IV-related поле,
- underlying/index price.

Если Deribit дает `mark_iv`, MVP может использовать его напрямую как `sigma`, но обязан сохранять raw payload, чтобы позже пересчитать probability другой моделью.

## Практический Алгоритм MVP

1. Получить Deribit ETH option instrument metadata.
2. Найти option с strike, близким к Polymarket threshold.
3. Проверить expiry mismatch.
4. Получить option snapshot: bid/ask/mark/IV/underlying.
5. Рассчитать `T`:

```text
T = (expiry_ts - observation_ts) / milliseconds_per_year
```

6. Рассчитать `d2`.
7. Рассчитать `N(d2)`.
8. Сохранить `model_probability`.
9. Сохранить все assumptions в observation metadata.

## Implementation Status

Black-Scholes `N(d2)` реализован в `crates/common/src/probability_basis.rs` для MVP matcher.

Текущая model version:

```text
black_scholes_single_strike_v1
```

В коде эта версия зафиксирована константой `PRICING_MODEL_VERSION` в `crates/common/src/probability_basis.rs`.

Текущие assumptions берутся из `ProbabilityBasisConfig`:

- `risk_free_rate = 0.0`,
- `dividend_yield = 0.0`,
- `milliseconds_per_year = 365.25 * 24 * 60 * 60 * 1000`,
- `sigma = mark_iv`,
- single-strike IV без volatility surface,
- `S = underlying_price`,
- `K = strike`,
- `T` рассчитывается из `expiry_ts_ms - exchange_ts_ms`.

Эти значения пока являются MVP defaults, а не утверждением о реальной crypto funding curve. Изменение `risk_free_rate`, `dividend_yield` или calendar basis должно проходить как изменение pricing assumptions и сопровождаться replay/golden review.

Реализация покрыта unit tests для expired options, invalid IV, deep ITM/OTM behavior и deterministic normal CDF approximation.

Любая замена этой модели на volatility surface, non-zero rates или alternative probability model должна менять model version и golden/replay expectations осознанно.

## Model Version Change Policy

Любое изменение `PRICING_MODEL_VERSION` означает изменение pricing model contract.

В том же commit/PR разработчик обязан:

1. Запустить:

```powershell
.\scripts\update_golden_fixture.ps1
```

2. Закоммитить обновленные replay golden reports из `fixtures/probability_basis/`.
3. Обновить эту страницу, если изменились assumptions модели.

`scripts/check_pricing_model_fixture_update.ps1` включен в `scripts/check_all.ps1` и CI. Он падает, если `PRICING_MODEL_VERSION` изменен без обновления golden report fixtures.

## Важные Caveats

- Black-Scholes probability является risk-neutral, а не physical probability.
- Polymarket price может включать liquidity, resolution и capital lockup premia.
- Deribit smile/skew может делать single-strike IV недостаточной.
- Expiry и settlement timestamp могут не совпадать с wording события.
- `mark_iv` нельзя считать абсолютной истиной.

## Open Questions

- Нужно ли строить volatility surface уже в MVP или достаточно single-strike `mark_iv`?
- Как штрафовать expiry mismatch в `estimated_cost_probability`?
- Как использовать put/call parity для проверки consistency?
- Нужно ли учитывать non-zero `r` после появления live-size капитала?
