---
type: system
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
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

## Strategies

- [Probability Basis](wiki/strategy-probability-basis.md) - первый MVP strategy для сравнения Deribit option-implied probabilities и Polymarket prices.
- [Funding Carry](wiki/strategy-funding-carry.md) - postponed strategy второго приоритета.

## Architecture

- [Data Pipeline](wiki/arch-data-pipeline.md) - replay-first pipeline, PostgreSQL event journal, Redis Streams и adapter traits.
- [Deterministic Replay](wiki/arch-deterministic-replay.md) - механизм воспроизводимого replay для backtesting/debugging/regression.
- [PostgreSQL Tables](wiki/schema-postgres-tables.md) - описание таблиц `event_journal`, `replay_runs`, `basis_observations`.
- [Rust Events Contracts](wiki/rust-events-contracts.md) - реализованные и proposed Rust event/adapter contracts.
- [Config Parameters](wiki/example-config-parameters.md) - объяснение текущих `config/*.toml`.
- [MVP Roadmap](wiki/roadmap-mvp.md) - фазы MVP, gates и failure criteria.

## Specifications

- [Deribit IV Calculation](wiki/spec-deribit-iv-calculation.md) - MVP-формула Black-Scholes для `deribit_model_probability` и open questions по IV.

## Workflows

- [Coding Standards](wiki/coding-standards.md) - технический engineering contract для dependencies, linting, typing, tests, Docker и Git.
- [Использование wiki в Codex](wiki/workflow-codex-wiki-usage.md) - как Codex читает и обновляет project memory во время работы.
- [Obsidian](wiki/workflow-obsidian.md) - как использовать Obsidian как human interface поверх Markdown vault.
- [Source Ingestion](wiki/workflow-source-ingestion.md) - как новые sources превращаются в долговременное wiki knowledge.
- [Wiki Health Check](wiki/workflow-wiki-health-check.md) - recurring maintenance workflow для index, links, contradictions и stale claims.

## Risks

- [Риск качества автоматизации](wiki/risk-automation-quality.md) - почему fully automated knowledge maintenance требует confidence labels и audit trail.
- [Probability Basis Risk](wiki/risk-probability-basis.md) - ограничения MVP, запрет шортов, rejection rules и cost assumptions.

## Raw Sources

- [Karpathy LLM Wiki](raw/sources/karpathy-llm-wiki-2026-04-04.md) - source note по LLM Wiki gist.
- [Deribit API](raw/sources/source-deribit-api.md) - official Deribit market-data API source note.
- [Polymarket API](raw/sources/source-polymarket-api.md) - official Gamma/CLOB API source note.
- [Quantum Bot Polymarket](raw/sources/source-quantum-bot-polymarket.md) - low-confidence anecdotal source по probability basis идее.
