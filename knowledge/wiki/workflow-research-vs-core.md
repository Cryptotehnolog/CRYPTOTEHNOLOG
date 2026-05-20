---
type: workflow
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
  - hermes-agent-2026-05-20
  - omniroute-2026-05-20
---

# Workflow: Research Vs Deterministic Core

Эта страница фиксирует границу между research layer и deterministic core.

## Deterministic Core

Deterministic core - это код, который может влиять на signals, risk decisions, orders, execution или portfolio state.

В core входят:

- ingestion adapters,
- event normalization,
- feature calculation,
- strategy rules,
- risk checks,
- paper/live execution,
- event journal,
- deterministic replay.

Core должен быть:

- deterministic,
- testable,
- replayable,
- config-driven,
- free of LLM runtime dependencies.

## Research Layer

Research layer - это инструменты и агенты, которые анализируют данные и предлагают идеи.

В research layer входят:

- notebooks/scripts в `research/`,
- Hermes Agent,
- OmniRoute,
- Obsidian/wiki review,
- reports,
- hypothesis generation.

Research layer может читать данные и писать recommendations, но не может менять runtime behavior напрямую.

## Allowed Direction

Разрешенный поток:

```text
deterministic core data
  -> read-only export
  -> research analysis
  -> hypothesis
  -> human review
  -> Git-tracked config/code change
  -> tests/replay
  -> deployment
```

Запрещенный поток:

```text
LLM/agent output
  -> live config mutation
  -> Redis Streams
  -> risk bypass
  -> orders
```

## Probability Basis Status

`probability_basis` сейчас является research strategy. Это значит:

- код может быть production-quality,
- данные должны быть reproducible,
- но live trading запрещен до отдельного decision review.

## Promotion Rule

Research output становится частью deterministic core только если:

1. оформлен в wiki или issue,
2. прошел human review,
3. реализован как code/config change,
4. покрыт tests/replay,
5. не нарушает risk constraints.

