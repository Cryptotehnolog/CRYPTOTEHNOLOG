---
type: source
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
source_id: lightrag-github-2026-05-20
title: HKUDS LightRAG GitHub Repository
author: HKUDS
created: 2026-05-20
url: https://github.com/HKUDS/LightRAG
---

# Source Note: HKUDS LightRAG GitHub Repository

## Summary

HKUDS LightRAG - open-source implementation of graph-enhanced retrieval-augmented generation. Repository documentation positions LightRAG as a framework/server for indexing documents, building knowledge graph representations and querying them through RAG workflows.

As of review on 2026-05-20, the project appears active and has server/API-oriented documentation, but CRYPTOTEHNOLOG has not validated operational fit, failure modes, data isolation or maintenance cost.

## Key Takeaways

- LightRAG is relevant to future research memory because it combines text/vector retrieval with knowledge graph structure.
- Repository documentation recommends server/API usage for integrations rather than embedding core internals directly.
- Activity and popularity are useful signals, not production proof for this project.

## Project Impact

LightRAG may become the preferred candidate for Phase 1 research-memory storage after Phase 0 validates the deterministic probability basis MVP.

It must not be added to deterministic core, Docker Compose, runtime dependencies or MCP wiring before Phase 0 exit gate is passed.

## Open Questions

- Какая storage backend configuration нужна для project-scale research memory?
- Насколько stable LightRAG API для long-lived agent workflows?
- Как изолировать research memory от deterministic event journal?
