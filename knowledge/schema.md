---
type: schema
status: active
owner: codex
updated: 2026-05-20
---

# Knowledge Base Schema

This document defines how Codex maintains the CRYPTOTEHNOLOG knowledge base.

The operating principle is based on Karpathy's LLM Wiki pattern: raw sources remain immutable, while Codex maintains a persistent, interlinked Markdown wiki that compounds over time.

## Directory Layout

- `knowledge/raw/` - immutable source notes and source metadata. Codex may add files here, but must not rewrite existing source captures except to fix broken metadata.
- `knowledge/wiki/` - synthesized pages owned by Codex.
- `knowledge/templates/` - reusable page templates.
- `knowledge/index.md` - content-oriented map of the wiki.
- `knowledge/log.md` - append-only chronological maintenance log.
- `knowledge/schema.md` - this operating contract.

## Page Types

Every Markdown page managed by Codex must use YAML frontmatter:

```yaml
---
type: concept|decision|source|workflow|risk|strategy|venue|metric|system
status: draft|active|superseded|rejected
confidence: low|medium|high
updated: YYYY-MM-DD
sources:
  - source-id
---
```

## Quality Rules

Codex must:

- Separate facts, assumptions, opinions, and decisions.
- Cite sources by linking to raw source notes or canonical project files.
- Mark uncertain claims with `confidence: low` or an explicit caveat.
- Update `knowledge/index.md` after every knowledge-base edit.
- Append to `knowledge/log.md` after every ingest, query synthesis, lint pass, or major rewrite.
- Prefer small focused pages over large monolithic notes.
- Create cross-links using relative Markdown links.
- Preserve contradictory claims instead of silently overwriting them.

Codex must not:

- Treat model output as a source of truth.
- Rewrite immutable raw sources.
- Promote a hypothesis to a decision without an explicit decision page.
- Hide rejected ideas. Rejections are valuable project memory.
- Store secrets, API keys, private credentials, or exchange account details in the wiki.

## Automation Workflow

When processing a new source:

1. Create a raw source note in `knowledge/raw/sources/`.
2. Extract claims, assumptions, decisions, and open questions.
3. Update or create synthesized pages in `knowledge/wiki/`.
4. Add links from affected pages to the raw source note.
5. Update `knowledge/index.md`.
6. Append a dated entry to `knowledge/log.md`.
7. Run `scripts/kb_health_check.ps1`.

When answering an architectural question:

1. Read `knowledge/index.md`.
2. Read the relevant wiki pages.
3. If the answer creates a reusable synthesis, file it as a wiki page.
4. Update `knowledge/log.md`.

When linting the wiki:

1. Check for missing frontmatter.
2. Check for missing index entries.
3. Check for stale `updated` dates.
4. Check for orphan pages.
5. Check for unresolved contradictions or low-confidence claims that need source work.

## Naming Conventions

Use lowercase kebab-case filenames:

- `concept-probability-basis.md`
- `decision-first-mvp.md`
- `workflow-source-ingestion.md`
- `risk-settlement-mismatch.md`

## Source Identifiers

Use stable IDs:

- `karpathy-llm-wiki-2026-04-04`
- `project-review-2026-05-19`
- `user-vision-2026-05-19`

