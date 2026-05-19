---
type: workflow
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Workflow: Source Ingestion

When Codex processes a new source, it must create durable project memory rather than leaving the source analysis in chat.

## Steps

1. Create a raw source note in `knowledge/raw/sources/`.
2. Extract reusable claims, decisions, risks, and open questions.
3. Update relevant wiki pages.
4. Create new focused pages when the concept is reusable.
5. Add source links to affected pages.
6. Update `knowledge/index.md`.
7. Append to `knowledge/log.md`.
8. Run `scripts/kb_health_check.ps1`.

## Output Quality

Each synthesis page should make clear what is fact, what is inference, and what remains unverified.

