---
type: workflow
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Workflow: Obsidian

Obsidian используется как human interface для базы знаний CRYPTOTEHNOLOG.

## Setup

Открыть эту папку как Obsidian vault:

```text
D:\CRYPTOTEHNOLOG\knowledge
```

Vault остается plain Markdown, поэтому все notes версионируются в Git и читаются без Obsidian.

## Рекомендуемое Использование

Использовать Obsidian для:

- graph navigation,
- backlinks,
- review project memory,
- поиска stale assumptions,
- чтения raw sources и synthesized pages рядом.

## Не Рекомендуется

Не делать Obsidian plugins, local graph state или UI metadata обязательными для builds, tests, trading или CI.

## Git Boundary

Obsidian может создать локальные `.obsidian/` settings, `.canvas`, `.base` и daily notes. Эти файлы user-specific и сейчас игнорируются Git через `.gitignore`.

Codex-managed knowledge files остаются в:

- `knowledge/schema.md`,
- `knowledge/index.md`,
- `knowledge/log.md`,
- `knowledge/raw/`,
- `knowledge/wiki/`,
- `knowledge/templates/`.
