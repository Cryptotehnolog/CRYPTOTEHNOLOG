---
type: source
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
source_id: polymarket-api-2026-05-20
title: Polymarket Gamma and CLOB API Documentation
author: Polymarket
created: 2026-05-20
url: https://docs.polymarket.com/
---

# Source Note: Polymarket Gamma And CLOB API Documentation

## Summary

Polymarket предоставляет несколько API layers. Для MVP важны:

- Gamma API для discovery events/markets, metadata, outcomes и market descriptions.
- CLOB API для order-book/price data, если рынок поддерживает order book.

Gamma полезен для поиска candidate events, но не должен считаться полноценным execution API. CLOB нужен для более точной оценки bid/ask, spread и liquidity.

## Ключевые Возможности Для MVP

- Получать список markets/events и фильтровать по asset, date, wording и active status.
- Читать market metadata: slug, question, outcomes, condition/token identifiers, close/end dates.
- Получать цены outcome tokens как probability-like market prices.
- Использовать CLOB data для проверки spread, midpoint и depth перед расчетом net edge.

## Project Impact

Polymarket adapter для MVP должен быть read-only:

- discovery candidate crypto events,
- normalizing event wording and dates,
- extracting outcome prices and liquidity,
- rejecting ambiguous event definitions,
- preserving raw API payloads in event journal.

## Open Questions

- Какие поля Gamma API наиболее надежны для close date и resolution wording?
- Всегда ли target event date совпадает с Deribit expiry timestamp?
- Какие markets имеют достаточно CLOB liquidity для meaningful basis observation?
- Как лучше нормализовать outcomes: `Yes/No`, token IDs, probability prices?

