---
type: source
status: active
confidence: low
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
source_id: quantum-bot-polymarket-2026-05-20
title: Quantum Bot Exploits Market Gaps, Amasses $1.8 Million on Polymarket
author: Phemex
created: 2026-05-20
url: https://phemex.com/news/article/quantum-bot-exploits-market-gaps-amasses-18-million-on-polymarket-58313
---

# Source Note: Quantum Bot Polymarket

## Summary

Phemex описывает публичный кейс бота, который якобы использовал Deribit implied volatility и Black-Scholes style probability conversion для поиска mispricing на Polymarket.

Этот источник полезен как anecdotal signal, но не является primary source и не доказывает прибыльность стратегии. Его нельзя использовать как основание для live trading.

## Key Takeaways

- Идея сравнения Deribit option-implied probabilities с Polymarket prices уже встречалась публично.
- Источник утверждает, что бот использовал options data и probability model для поиска ценовых расхождений.
- Детали methodology, execution, fees, risk controls и survivorship не раскрыты достаточно для воспроизведения.

## Project Impact

Для CRYPTOTEHNOLOG этот источник подтверждает, что направление стоит исследовать, но не подтверждает edge.

Правильная интерпретация:

- `confidence: low`,
- использовать как hypothesis support,
- проверять все на собственном event journal и replay,
- не копировать выводы без независимой валидации.

## Open Questions

- Есть ли primary source по этому боту?
- Какие exact contracts/events он торговал?
- Учитывались ли fees, spreads, slippage и capital lockup?
- Был ли PnL реализованным или mark-to-market?

