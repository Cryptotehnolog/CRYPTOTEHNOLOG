---
type: workflow
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Workflow: Codex Wiki Usage

Codex should use the knowledge base as persistent project memory.

## Before Coding

For architecture, strategy, market-data, risk, or research changes, Codex should:

1. Read `knowledge/index.md`.
2. Open the relevant pages in `knowledge/wiki/`.
3. Check for active decisions, rejected ideas, and low-confidence assumptions.
4. Use the wiki to avoid repeating old debates or reintroducing rejected designs.

Small mechanical edits do not require a full wiki read.

## While Coding

Codex should treat the wiki as guidance, not executable truth. Runtime behavior must come from code, tests, configs, migrations, and explicit human-approved parameters.

## After Coding

Codex should update the wiki when the work creates durable knowledge:

- architecture decisions,
- strategy assumptions,
- venue API findings,
- risk limits,
- testing conclusions,
- rejected designs,
- automation opportunities.

Every knowledge update should also update `knowledge/index.md` and append to `knowledge/log.md`.

## Boundary

The wiki must not become an execution dependency. No deterministic trading service should query Obsidian, Markdown pages, or LLM-generated summaries while making live risk or execution decisions.

