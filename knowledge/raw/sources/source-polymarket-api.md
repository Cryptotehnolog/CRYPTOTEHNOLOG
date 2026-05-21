---
type: source
status: active
confidence: high
stability: volatile
updated: 2026-05-21
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

Официальная документация Polymarket разделяет API layers: Gamma API отвечает за markets/events discovery, а CLOB API на `https://clob.polymarket.com` отвечает за orderbook data, prices, midpoints, spreads и price history. Публичный endpoint `GET /book` возвращает order book для `token_id` с массивами `bids` и `asks`; первый bid/ask level используется CRYPTOTEHNOLOG только как read-only executable pricing boundary, без order placement.

## Ключевые Возможности Для MVP

- Получать список markets/events и фильтровать по asset, date, wording и active status.
- Читать market metadata: slug, question, outcomes, condition/token identifiers, close/end dates.
- Получать цены outcome tokens как probability-like market prices.
- Использовать CLOB data для проверки spread, midpoint и depth перед расчетом net edge.
- Читать CLOB order book по `token_id`: `asset_id`, `bids[].price`, `bids[].size`, `asks[].price`, `asks[].size`, `tick_size`, `min_order_size`.

## Project Impact

Polymarket adapter для MVP должен быть read-only:

- discovery candidate crypto events,
- normalizing event wording and dates,
- extracting outcome prices and liquidity,
- rejecting ambiguous event definitions,
- preserving raw API payloads in event journal.

Phase 0 policy: Gamma `outcomePrices` разрешены как fallback `bid=ask=outcomePrice` только для discovery/probe, но не должны считаться доказательством executable edge. Для executable pricing нужен CLOB bid/ask snapshot.

## Open Questions

- Какие поля Gamma API наиболее надежны для close date и resolution wording?
- Всегда ли target event date совпадает с Deribit expiry timestamp?
- Какие markets имеют достаточно CLOB liquidity для meaningful basis observation?
- Как лучше нормализовать outcomes: `Yes/No`, token IDs, probability prices?
