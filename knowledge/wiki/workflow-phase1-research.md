---
type: workflow
status: draft
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

# Workflow: Phase 1 Research Layer

Phase 1 начинается только после прохождения Phase 0 exit gate из [MVP Roadmap](roadmap-mvp.md).

Цель Phase 1 - превратить накопленные deterministic observations в research hypotheses без вмешательства в execution path.

## Scope

Разрешено:

- read-only exports из PostgreSQL,
- daily/weekly post-trade reports,
- hypothesis backlog,
- research memory experiments,
- LightRAG evaluation,
- Hermes/OmniRoute experiments,
- manual recommendations для human review.

Запрещено:

- live orders,
- auto-mutating configs,
- Redis messages в deterministic core,
- обход risk engine,
- LLM-dependent strategy/risk/execution logic.

## Phase 1 Candidate Architecture

```text
PostgreSQL read-only export
  -> deterministic summary script
  -> LightRAG research memory candidate
  -> Hermes Agent research task
  -> OmniRoute LLM gateway
  -> hypothesis / report / recommendation
  -> human review
  -> Git-tracked change
  -> replay and tests
```

## Entry Gate

Phase 1 нельзя начинать, пока Phase 0 не доказал:

- reproducible replay,
- достаточное количество observations/trades,
- positive net edge after costs,
- controlled drawdown,
- stable rejection taxonomy,
- отсутствие hidden LLM dependency.

## First Phase 1 Tasks

1. Создать sanitized export format для observations и reports.
2. Протестировать LightRAG на небольшой read-only копии research notes.
3. Проверить, улучшает ли graph/RAG retrieval качество research review.
4. Описать MCP permissions до подключения любых agents.
5. Зафиксировать human approval workflow для recommendations.

## Non-Goals

Phase 1 не делает систему autonomous trading agent.

Research layer может улучшать качество анализа, но deterministic core остается единственным местом, где реализуются trading rules, risk checks и execution behavior.
