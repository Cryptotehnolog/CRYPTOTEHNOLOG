---
type: source
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
source_id: deribit-api-2026-05-20
title: Deribit API Documentation
author: Deribit
created: 2026-05-20
url: https://docs.deribit.com/
---

# Source Note: Deribit API Documentation

## Summary

Deribit предоставляет JSON-RPC API поверх HTTP и WebSocket. Для MVP важны публичные market-data методы: discovery инструментов, order book, ticker и book summaries по опционам ETH.

Deribit API нужен нам как источник option quotes, implied volatility fields, expiry, strike и instrument metadata. Это не execution source для MVP.

## Ключевые Возможности Для MVP

- WebSocket API можно использовать для live market-data stream.
- HTTP JSON-RPC можно использовать для deterministic polling и первичного discovery.
- `public/get_instruments` нужен для списка ETH options и metadata инструментов.
- `public/get_order_book` и/или ticker/book summary методы нужны для bid/ask/mark data.
- Option instruments содержат expiry, strike и option kind в instrument naming convention.

## IV / Probability Open Questions

Deribit market data может содержать IV-related fields вроде `mark_iv`, но это не отменяет model risk. Нужно отдельно решить:

- используем ли Deribit `mark_iv` напрямую;
- строим ли собственную implied-volatility surface;
- как интерполируем strikes и expiries;
- как переводим option price/IV в event probability;
- как обрабатываем smile/skew.

Отдельная страница `source-deribit-iv-calculation.md` пока не создается. Вопрос зафиксирован как open issue внутри MVP knowledge package.

## Project Impact

Первая реализация ingestion должна начинаться с read-only Deribit market-data adapter:

- discovery ETH options,
- нормализация instrument metadata,
- snapshot bid/ask/mark/IV,
- запись raw events в PostgreSQL event journal,
- публикация normalized snapshots в Redis Streams позже, после стабилизации contracts.

## Open Questions

- Какие поля Deribit считать canonical для IV в MVP?
- Нужен ли WebSocket на первом шаге или достаточно REST polling для replay-oriented прототипа?
- Какие endpoints дают минимально достаточную комбинацию `bid`, `ask`, `mark_price`, `mark_iv`, `underlying_price`?

