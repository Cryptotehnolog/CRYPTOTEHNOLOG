---
type: system
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Обзор Базы Знаний

CRYPTOTEHNOLOG использует локальную Markdown-базу знаний, чтобы сохранять project memory по engineering, research, market assumptions, risk decisions и post-trade analysis.

У базы знаний три слоя:

- raw sources: immutable source notes и evidence,
- wiki pages: синтезированное project knowledge, поддерживаемое Codex,
- schema: правила, которые держат wiki consistent и auditable.

Дополнительно `knowledge/graph.md` содержит curated Mermaid-граф ключевых смысловых связей. Он не является полной автоматической картой всех Markdown-ссылок.

Это намеренно не runtime trading component. Детерминированное торговое ядро не должно зависеть от LLM-generated wiki content для order generation, risk checks или execution.

## Почему Это Важно

В проекте много движущихся частей: Deribit options, Polymarket markets, event matching, probability modeling, settlement mismatch, paper execution, risk controls и будущий AI-assisted analysis. Без поддерживаемой базы знаний решения будут утекать в историю чатов, и их будет сложно audit.

## Правило Поддержки

Когда Codex узнает долговременную информацию о проекте, он должен либо обновить существующую wiki page, либо создать новую сфокусированную страницу, а затем обновить index и log.
