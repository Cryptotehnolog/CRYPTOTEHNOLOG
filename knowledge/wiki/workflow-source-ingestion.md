---
type: workflow
status: active
confidence: high
stability: stable
updated: 2026-05-20
review_after: 2026-08-18
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Workflow: Source Ingestion

Когда Codex обрабатывает новый source, он должен создавать долговременную project memory, а не оставлять анализ источника в чате.

## Steps

1. Создать raw source note в `knowledge/raw/sources/`.
2. Извлечь reusable claims, decisions, risks и open questions.
3. Обновить релевантные wiki pages.
4. Создать новые focused pages, если concept переиспользуемый.
5. Добавить source links на затронутые pages.
6. Обновить `knowledge/index.md`.
7. Добавить запись в `knowledge/log.md`.
8. Запустить `scripts/kb_health_check.ps1`.

## Качество Output

Каждая synthesis page должна явно отделять facts, inference и то, что остается unverified.
