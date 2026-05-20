---
type: system
status: draft
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - lightrag-github-2026-05-20
  - lightrag-arxiv-2024-10-08
  - lightrag-mcp-g99-2026-05-20
---

# Tool: LightRAG

LightRAG - preferred research-memory candidate для будущего исследовательского слоя (research layer) CRYPTOTEHNOLOG.

Это не утвержденный production component и не часть текущего MVP.

## Role In Phase 1

После прохождения Phase 0 exit gate LightRAG может быть оценен как память для:

- post-trade analysis,
- retrieval по прошлым observations и rejected candidates,
- хранения research hypotheses,
- связывания стратегий, рисков, market regimes и результатов replay,
- помощи Hermes Agent и другим AI tools в подготовке recommendations.

## Current Decision

LightRAG документируется сейчас, но до прохождения Phase 0 exit gate запрещены:

- установка LightRAG в проектную инфраструктуру,
- добавление LightRAG в Docker Compose,
- MCP wiring,
- ingestion данных в LightRAG,
- agent workflows, которые зависят от LightRAG,
- runtime dependency deterministic core от LightRAG.

## Why Deferred

Текущая цель - доказать probability basis через deterministic Rust code, replay и paper observations.

LightRAG может быть полезен позже, но сейчас он увеличивает:

- infrastructure complexity,
- количество failure modes,
- нагрузку на секреты и LLM credentials,
- риск преждевременного overengineering,
- риск смешения research layer и execution path.

## Evaluation Criteria

Перед внедрением LightRAG нужно отдельно проверить:

- стабильность server/API deployment,
- качество retrieval на наших research notes и observations,
- способность хранить rejected hypotheses без потери контекста,
- стоимость обслуживания,
- возможность read-only интеграции с PostgreSQL exports,
- безопасность MCP/tool permissions.

## Boundary

LightRAG может читать sanitized research exports, но не должен:

- читать secrets или exchange credentials,
- писать в Redis Streams,
- менять config deterministic core,
- участвовать в signal/risk/execution decisions,
- быть required dependency для replay или paper trading.
