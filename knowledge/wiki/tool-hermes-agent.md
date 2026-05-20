---
type: system
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - hermes-agent-2026-05-20
  - omniroute-2026-05-20
---

# Tool: Hermes Agent

Hermes Agent - будущий research-layer agent runtime для CRYPTOTEHNOLOG.

Его задача - превращать накопленные observations, replay results и post-trade data в research hypotheses и human-reviewable recommendations.

## Role

Hermes может:

- читать historical data,
- анализировать `basis_observations`,
- готовить daily/weekly reports,
- предлагать hypothesis backlog,
- формировать draft parameter-change proposals,
- сохранять research memory.

Hermes не может:

- отправлять orders,
- менять live config автоматически,
- писать в Redis Streams deterministic core,
- обходить risk engine,
- быть dependency для strategy/risk/execution services.

## Integration Shape

```text
PostgreSQL read-only views
  -> research script / Hermes task
  -> OmniRoute LLM call
  -> research note / recommendation
  -> human review
  -> explicit config/code change
```

## Security Boundary

Hermes получает только read-only доступ к торговым данным. Любая рекомендация должна проходить human approval и обычный Git workflow.

## Status

Not implemented. Эта страница фиксирует future role и boundary, чтобы AI research layer не смешался с deterministic core.

