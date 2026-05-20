---
type: system
status: active
confidence: high
updated: 2026-05-20
sources: []
---

# Журнал Базы Знаний

## [2026-05-20] ingest | Karpathy LLM Wiki

Создана структура базы знаний CRYPTOTEHNOLOG по паттерну Karpathy LLM Wiki:

- добавлен immutable raw source note,
- добавлены schema и operating rules,
- добавлены index и append-only log,
- добавлены стартовые concept, workflow, decision и risk pages,
- добавлен health-check script.

## [2026-05-20] automation | CI and source ingest

Добавлен GitHub Actions CI для Rust checks и knowledge-base health checks. Добавлен `scripts/new_source_note.ps1`, который создает raw source notes со stable source IDs, frontmatter, index entries, log entries и immediate health-check validation.

## [2026-05-20] workflow | Codex and Obsidian usage

Задокументировано, как Codex должен читать и обновлять wiki во время engineering work, и как Obsidian используется как Markdown vault interface без превращения в runtime dependency.

## [2026-05-20] automation | Agent rules and pre-commit policy

Добавлен root `AGENTS.md` с правилами для AI agents. Добавлен Git hook installer и задокументировано, что pre-commit knowledge checks должны оставаться fast, local, deterministic и network-free.

## [2026-05-20] automation | Local checks

Добавлена local Markdown link validation и `scripts/check_all.ps1` для fast local check set. Link checker валидирует только local Markdown targets и включен в CI, но не в pre-commit.

## [2026-05-20] automation | Development status

Добавлен `scripts/dev_status.ps1` как read-only session-start diagnostic для Git status, last commit, remotes, CI workflow presence, pre-commit hook presence и core tool versions.

## [2026-05-20] documentation | Russian language policy

Проектная документация переведена на русский язык по варианту B: русский основной текст, английские technical terms сохраняются в скобках или как code/config/API contracts. Language policy добавлена в `AGENTS.md` и `knowledge/schema.md`.

## [2026-05-20] workflow | Obsidian local artifacts

После подключения Obsidian уточнено, что `.obsidian/`, `.canvas`, `.base` и daily notes являются user-specific локальными artifacts. Git игнорирует их, а `kb_health_check.ps1` проверяет только managed knowledge files.

## [2026-05-20] system | Curated knowledge graph

Добавлен `knowledge/graph.md` с curated Mermaid-графом ключевых смысловых связей. Health-check должен проверять наличие `graph.md` и YAML frontmatter, но не валидировать семантику графа.
