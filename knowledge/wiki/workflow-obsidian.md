---
type: workflow
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Workflow: Obsidian

Obsidian can be used as the human interface for the CRYPTOTEHNOLOG knowledge base.

## Setup

Open this folder as an Obsidian vault:

```text
D:\CRYPTOTEHNOLOG\knowledge
```

The vault is plain Markdown, so all notes remain versioned in Git and readable without Obsidian.

## Recommended Use

Use Obsidian for:

- graph navigation,
- backlinks,
- reviewing project memory,
- finding stale assumptions,
- reading raw sources and synthesized pages side by side.

## Not Recommended

Do not make Obsidian plugins, local graph state, or UI metadata required for builds, tests, trading, or CI.

## Git Boundary

Obsidian may create local `.obsidian/` settings. Those settings are user-specific and should only be committed if we intentionally decide to share a vault configuration.

