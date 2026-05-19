---
type: workflow
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Workflow: Wiki Health Check

The wiki must be checked periodically so automated maintenance does not accumulate quiet errors.

## Checks

- Every managed Markdown page has YAML frontmatter.
- Every wiki page is linked from `knowledge/index.md`.
- Every knowledge edit appends to `knowledge/log.md`.
- Low-confidence pages are easy to find.
- Rejected and superseded pages remain visible.
- Contradictions are documented instead of erased.

## Frequency

Run after every source ingest and before major architecture changes.

