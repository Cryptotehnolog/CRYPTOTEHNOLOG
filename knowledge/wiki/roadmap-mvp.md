---
type: system
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
  - lightrag-github-2026-05-20
  - lightrag-arxiv-2024-10-08
  - lightrag-mcp-g99-2026-05-20
---

# Roadmap: MVP

Цель MVP - доказать или опровергнуть probability basis thesis без live trading.

## Phase 0: Deterministic Core

Текущая фаза проекта - Phase 0. Ее единственная цель: deterministic Rust core должен доказать, что probability basis генерирует воспроизводимый positive net edge after costs.

В Phase 0 запрещены:

- live trading,
- Hermes/OmniRoute в execution path,
- LightRAG installation,
- LightRAG Docker wiring,
- LightRAG MCP wiring,
- ingestion данных в LightRAG,
- agent workflows, зависящие от LightRAG.

LightRAG документируется как future research-memory candidate, но не внедряется до Phase 0 exit gate.

## Phase 0 Milestone 1: Knowledge And Contracts

Готово, когда:

- Deribit source note создана,
- Polymarket source note создана,
- strategy/risk pages созданы,
- event contracts определены,
- replay skeleton работает.

## Phase 0 Milestone 2: Read-Only Data Adapters

Готово, когда:

- Deribit adapter получает ETH option snapshots,
- Polymarket adapter получает candidate event snapshots,
- raw payloads сохраняются в `event_journal`,
- normalized events воспроизводятся через replay.

## Phase 0 Milestone 3: Matching And Observation

Готово, когда:

- matcher генерирует matched/rejected candidate reports,
- rejection reasons детерминированны,
- `basis_observations` заполняется,
- cost model явно вычитает fees/spread/slippage/mismatch penalty.

## Phase 0 Milestone 4: Paper Review

Готово, когда:

- накоплено достаточно observations для statistical review,
- replay output воспроизводим,
- edge сохраняется после realistic costs,
- liquidity constraints не уничтожают thesis.

## Phase 0 Exit Gate

Phase 1 research layer можно обсуждать только после выполнения всех условий:

- минимум `1_000` normalized observations по candidate pairs;
- минимум `100` matched basis opportunities, даже если они остаются paper-only observations;
- минимум `30` календарных дней read-only/paper collection без gaps, которые ломают replay;
- positive average `net_edge_probability` после fees, spread, slippage и settlement/mismatch penalty;
- не менее `60%` matched opportunities должны сохранять positive net edge после costs;
- max drawdown paper portfolio не хуже `5%`;
- daily loss limit simulation не нарушает `2%` initial capital;
- deterministic replay на frozen fixture и сохраненных raw events дает byte-stable matched/rejected report;
- rejection taxonomy stable: новые rejection reasons добавляются только через code review и tests;
- нет LLM, LightRAG, Hermes, OmniRoute или MCP dependency в deterministic core.

Эти числа являются минимальным gate для начала Phase 1 research-layer work, а не разрешением на live trading.

## Phase 1: Research Layer

Phase 1 начинается после Phase 0 exit gate.

Разрешенная цель Phase 1 - анализ накопленных observations, reports и rejected candidates. LightRAG может быть оценен как research-memory candidate, а Hermes/OmniRoute - как tools для reports и hypotheses.

Phase 1 не имеет права:

- отправлять orders,
- менять runtime config автоматически,
- писать в Redis Streams deterministic core,
- обходить risk engine,
- становиться dependency для replay, matching, risk или execution.

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
