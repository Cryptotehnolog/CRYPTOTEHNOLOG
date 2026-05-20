---
type: workflow
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Workflow: Wiki Health Check

Wiki нужно периодически проверять, чтобы automated maintenance не накапливал тихие ошибки.

## Checks

- У каждой managed Markdown page есть YAML frontmatter.
- Каждая wiki page связана из `knowledge/index.md`.
- Каждое knowledge edit добавляет запись в `knowledge/log.md`.
- Local Markdown links указывают на существующие файлы.
- Low-confidence pages легко найти.
- Rejected и superseded pages остаются видимыми.
- Contradictions документируются, а не стираются.

Managed pages - это `knowledge/schema.md`, `knowledge/index.md`, `knowledge/log.md`, а также Markdown-файлы в `knowledge/raw/`, `knowledge/wiki/` и `knowledge/templates/`. Личные Obsidian notes вне этих путей не валидируются этим скриптом.

## Pre-Commit Policy

`scripts/kb_health_check.ps1` разрешен в Git pre-commit hook. Поэтому он должен оставаться fast, local, deterministic и network-free.

`scripts/validate_local_links.ps1` проверяет только local Markdown links. Он включен в CI и `scripts/check_all.ps1`, но сейчас не установлен в pre-commit hook.

Он не должен вызывать:

- LLM,
- external APIs,
- external URL validators,
- Docker,
- databases,
- long-running audits,
- heavy test suites.

Если knowledge-base check требует network access, LLM judgment, external URL validation или heavy computation, его нужно реализовать как отдельный CI/manual audit script, а не добавлять в `kb_health_check.ps1`.

## Частота

Запускать после каждого source ingest и перед крупными architecture changes.
