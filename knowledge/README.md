---
type: system
status: active
confidence: high
stability: stable
updated: 2026-05-20
review_after: 2026-08-18
sources:
  - karpathy-llm-wiki-2026-04-04
  - project-review-2026-05-19
---

# База Знаний CRYPTOTEHNOLOG

Эта папка является Markdown-wiki проекта. Она хранит решения, источники, риски, архитектуру, roadmap и правила разработки.

## С Чего Начать

1. [Индекс](index.md) - главная карта базы знаний.
2. [Граф](graph.md) - curated Mermaid-граф ключевых связей.
3. [Журнал](log.md) - история изменений базы знаний.
4. [Схема](schema.md) - полный operating contract для Codex и разработчиков.

## Важные Страницы Для Разработки

- [Coding Standards](wiki/coding-standards.md)
- [Onboarding](wiki/workflow-onboarding.md)
- [Rust Events Contracts](wiki/rust-events-contracts.md)
- [Probability Basis Strategy](wiki/strategy-probability-basis.md)
- [Deribit IV Calculation](wiki/spec-deribit-iv-calculation.md)
- [Research Vs Deterministic Core](wiki/workflow-research-vs-core.md)

## Правило

Если появляется долговременное знание проекта, оно должно попасть в wiki, а не остаться только в чате.

После изменений запускать:

```powershell
.\scripts\check_all.ps1
```

