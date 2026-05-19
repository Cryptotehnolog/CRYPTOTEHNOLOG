---
type: risk
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Risk: Automation Quality

Fully automated wiki maintenance can create a false sense of confidence if generated summaries are treated as facts.

## Failure Modes

- The LLM merges distinct concepts under one name.
- Duplicate pages appear for the same concept.
- A weak inference becomes a confident project claim.
- Old claims survive after newer sources contradict them.
- Important rejections disappear because only active decisions are indexed.

## Mitigation

- Keep raw source notes immutable.
- Require frontmatter with `confidence` and `status`.
- Keep rejected and superseded pages indexed.
- Preserve contradictions explicitly.
- Run health checks after each ingest.
- Treat the wiki as project memory, not as runtime truth for trading.

