---
type: concept
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# LLM Wiki

LLM Wiki - это постоянная связанная Markdown-база знаний, которую поддерживает LLM agent.

Она отличается от базового RAG тем, что LLM не просто достает raw chunks во время запроса. Она постепенно компилирует знания в стабильные страницы, обновляет summaries, создает cross-links, фиксирует contradictions и поддерживает index и log.

## Адаптация Для CRYPTOTEHNOLOG

В этом проекте wiki должна сохранять:

- architecture decisions,
- market API findings,
- strategy assumptions,
- risk critiques,
- data-quality rules,
- backtest conclusions,
- rejected ideas,
- future automation opportunities.

## Граница

Wiki может помогать разработке и research. Она не должна напрямую кормить live trading decisions.

