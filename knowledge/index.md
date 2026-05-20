---
type: system
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
  - project-review-2026-05-19
---

# Индекс Базы Знаний

## System

- [Схема базы знаний](schema.md) - operating contract для поддержки wiki.
- [Обзор базы знаний](wiki/system-knowledge-base.md) - зачем проекту нужна постоянная LLM-maintained wiki.
- [Граф базы знаний](graph.md) - curated Mermaid-граф ключевых смысловых связей.

## Decisions

- [Первый MVP](wiki/decision-first-mvp.md) - Deribit + Polymarket probability basis является первым MVP; funding carry отложен.

## Concepts

- [LLM Wiki](wiki/concept-llm-wiki.md) - постоянная синтезированная Markdown-wiki, поддерживаемая LLM.
- [Probability Basis](wiki/concept-probability-basis.md) - research framing для сравнения Deribit option-implied probabilities и Polymarket event prices.

## Workflows

- [Использование wiki в Codex](wiki/workflow-codex-wiki-usage.md) - как Codex читает и обновляет project memory во время работы.
- [Obsidian](wiki/workflow-obsidian.md) - как использовать Obsidian как human interface поверх Markdown vault.
- [Source Ingestion](wiki/workflow-source-ingestion.md) - как новые sources превращаются в долговременное wiki knowledge.
- [Wiki Health Check](wiki/workflow-wiki-health-check.md) - recurring maintenance workflow для index, links, contradictions и stale claims.

## Risks

- [Риск качества автоматизации](wiki/risk-automation-quality.md) - почему fully automated knowledge maintenance требует confidence labels и audit trail.

## Raw Sources

- [Karpathy LLM Wiki](raw/sources/karpathy-llm-wiki-2026-04-04.md) - source note по LLM Wiki gist.
