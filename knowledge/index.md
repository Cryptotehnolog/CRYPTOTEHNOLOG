---
type: system
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
  - project-review-2026-05-19
---

# Knowledge Base Index

## System

- [Knowledge Base Schema](schema.md) - operating contract for maintaining this wiki.
- [Knowledge Base Overview](wiki/system-knowledge-base.md) - why this project uses a persistent LLM-maintained wiki.

## Decisions

- [First MVP](wiki/decision-first-mvp.md) - Deribit + Polymarket probability basis is the first MVP; funding carry is postponed.

## Concepts

- [LLM Wiki](wiki/concept-llm-wiki.md) - persistent, synthesized Markdown wiki maintained by an LLM.
- [Probability Basis](wiki/concept-probability-basis.md) - research framing for Deribit option-implied probabilities versus Polymarket event prices.

## Workflows

- [Codex Wiki Usage](wiki/workflow-codex-wiki-usage.md) - how Codex reads and updates project memory while working.
- [Obsidian](wiki/workflow-obsidian.md) - how to use Obsidian as a human interface over the Markdown vault.
- [Source Ingestion](wiki/workflow-source-ingestion.md) - how new sources are converted into durable wiki knowledge.
- [Wiki Health Check](wiki/workflow-wiki-health-check.md) - recurring maintenance workflow for index, links, contradictions, and stale claims.

## Risks

- [Automation Quality Risk](wiki/risk-automation-quality.md) - why fully automated knowledge maintenance needs confidence labels and audit trails.

## Raw Sources

- [Karpathy LLM Wiki](raw/sources/karpathy-llm-wiki-2026-04-04.md) - source note for the LLM Wiki gist.
