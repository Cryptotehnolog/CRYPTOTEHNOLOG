---
type: workflow
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - hermes-agent-2026-05-20
  - omniroute-2026-05-20
  - project-review-2026-05-19
---

# Workflow: Agent Research

Agent research workflow описывает, как Hermes Agent и OmniRoute могут использоваться после накопления replay/paper data.

Это future workflow. Он не входит в первый MVP execution path.

## Inputs

- `basis_observations`,
- `replay_runs`,
- rejected candidate reports,
- cost model outputs,
- strategy configs,
- risk limits,
- daily/weekly metrics.

## Flow

```text
PostgreSQL read-only export
  -> deterministic summary script
  -> Hermes Agent research task
  -> OmniRoute LLM gateway
  -> hypothesis / report / recommendation
  -> knowledge note
  -> human approval
  -> Git-tracked config/code change
```

## Example Research Questions

- В каких event types net edge чаще переживает costs?
- Какие rejection reasons доминируют?
- Стабилен ли spread после учета liquidity?
- Ухудшается ли edge около expiry?
- Какие Polymarket markets чаще имеют settlement ambiguity?

## Output

Разрешенные outputs:

- Markdown research notes,
- hypothesis backlog,
- charts/reports,
- draft recommendations,
- suggested experiments.

Запрещенные outputs:

- live orders,
- direct config mutation,
- Redis messages deterministic core,
- risk-engine bypass instructions.

## Promotion Rule

Hypothesis становится изменением стратегии только через:

1. wiki note,
2. human review,
3. Git-tracked config/code change,
4. deterministic replay,
5. risk review.

