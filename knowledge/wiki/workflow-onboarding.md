---
type: workflow
status: active
confidence: high
stability: stable
updated: 2026-05-20
review_after: 2026-08-18
sources:
  - project-review-2026-05-19
---

# Workflow: Onboarding

Эта страница описывает стартовую последовательность для нового разработчика или новой AI-сессии.

## Первые 5 Минут

1. Прочитать `AGENTS.md`.
2. Запустить:

```powershell
.\scripts\dev_status.ps1
```

3. Открыть `knowledge/index.md`.
4. Открыть `knowledge/graph.md`.
5. Открыть `knowledge/wiki/roadmap-mvp.md`.

## Перед Кодингом

Прочитать:

- [Coding Standards](coding-standards.md),
- [Research Vs Deterministic Core](workflow-research-vs-core.md),
- [Rust Events Contracts](rust-events-contracts.md),
- [Data Pipeline](arch-data-pipeline.md).

## Перед Коммитом

Запустить:

```powershell
.\scripts\check_all.ps1
```

Pre-commit hook дополнительно запускает быстрый `kb_health_check.ps1`.

## Как Выбрать Задачу

Использовать [MVP Roadmap](roadmap-mvp.md). Если задача меняет architecture, strategy, risk или research boundary, обновить wiki, index, graph и log.

