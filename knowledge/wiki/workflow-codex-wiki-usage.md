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

# Workflow: Использование Wiki В Codex

Codex должен использовать базу знаний как постоянную project memory.

## Перед Кодом

Перед изменениями в architecture, strategy, market-data, risk или research Codex должен:

1. Прочитать `knowledge/index.md`.
2. Открыть релевантные страницы в `knowledge/wiki/`.
3. Проверить active decisions, rejected ideas и low-confidence assumptions.
4. Использовать wiki, чтобы не повторять старые дебаты и не возвращать rejected designs.

Мелкие mechanical edits не требуют полного wiki read.

## Во Время Кода

Codex должен считать wiki guidance, а не executable truth. Runtime behavior должен приходить из code, tests, configs, migrations и explicit human-approved parameters.

## После Кода

Codex должен обновлять wiki, когда работа создает durable knowledge:

- architecture decisions,
- strategy assumptions,
- venue API findings,
- risk limits,
- testing conclusions,
- rejected designs,
- automation opportunities.

Каждое knowledge update также должно обновлять `knowledge/index.md` и добавлять запись в `knowledge/log.md`.

Если добавлена новая `decision` или `risk` page, Codex также обязан проверить `knowledge/graph.md`. Граф обновляется только для важных смысловых связей, а не для каждой Markdown-ссылки.

## Граница

Wiki не должна становиться execution dependency. Ни один deterministic trading service не должен читать Obsidian, Markdown pages или LLM-generated summaries при принятии live risk или execution decisions.
