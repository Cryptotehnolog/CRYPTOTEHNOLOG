---
type: system
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Knowledge Base Overview

CRYPTOTEHNOLOG uses a local Markdown knowledge base to preserve project memory across engineering, research, market assumptions, risk decisions, and post-trade analysis.

The knowledge base has three layers:

- raw sources: immutable source notes and evidence,
- wiki pages: synthesized project knowledge maintained by Codex,
- schema: rules that keep the wiki consistent and auditable.

This is intentionally not a runtime trading component. The deterministic trading core must not depend on LLM-generated wiki content for order generation, risk checks, or execution.

## Why This Matters

The project has many moving parts: Deribit options, Polymarket markets, event matching, probability modeling, settlement mismatch, paper execution, risk controls, and later AI-assisted analysis. Without a maintained knowledge base, decisions will leak into chat history and become hard to audit.

## Maintenance Rule

Whenever Codex learns durable information about the project, it should either update an existing wiki page or create a focused new page, then update the index and log.

