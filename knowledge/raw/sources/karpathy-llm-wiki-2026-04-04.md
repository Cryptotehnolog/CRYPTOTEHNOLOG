---
type: source
status: active
confidence: high
updated: 2026-05-20
source_id: karpathy-llm-wiki-2026-04-04
title: LLM Wiki
author: Andrej Karpathy
created: 2026-04-04
url: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
---

# Source Note: Karpathy LLM Wiki

## Summary

Karpathy describes a pattern for building personal or project knowledge bases with LLM agents. The key idea is to avoid repeatedly retrieving raw chunks from documents at query time. Instead, the LLM incrementally builds and maintains a persistent Markdown wiki that sits between the user and raw sources.

The raw sources are immutable. The wiki is generated and maintained by the LLM. A schema file instructs the LLM how to structure pages, ingest new sources, answer questions, update the index, maintain a log, and periodically lint the wiki.

## Key Takeaways For CRYPTOTEHNOLOG

- Use raw source notes as immutable evidence.
- Maintain a synthesized wiki as a project memory layer.
- Keep `index.md` as the content map.
- Keep `log.md` as the chronological audit trail.
- Let Codex handle routine maintenance: summaries, links, filing, contradiction notes, and health checks.
- Do not confuse a generated synthesis with source truth.

## Engineering Interpretation

This project should use the LLM Wiki pattern for architecture decisions, strategy research, market API notes, risk assumptions, and post-trade analysis. It should not be used as an execution-time dependency for the deterministic trading core.

## Source Handling

This note paraphrases the source and links to the original gist. It intentionally does not copy the full source text.

