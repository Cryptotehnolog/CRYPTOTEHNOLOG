---
type: source
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
source_id: lightrag-mcp-g99-2026-05-20
title: Third-Party LightRAG MCP Server
author: g99 / community maintainers
created: 2026-05-20
url: https://mcpdir.dev/servers/g99-lightrag-mcp-server
---

# Source Note: Third-Party LightRAG MCP Server

## Summary

This source describes a third-party Model Context Protocol server for LightRAG. It advertises tools for document management, querying and knowledge graph operations against a running LightRAG server.

This is useful evidence that MCP integration is possible, but it is not proof that the integration is official, stable or appropriate for CRYPTOTEHNOLOG.

## Key Takeaways

- MCP wiring around LightRAG exists in the ecosystem.
- The MCP server appears to require a separate running LightRAG instance.
- Tool count and behavior are version-dependent and should not be treated as project contract.

## Project Impact

The source supports documenting MCP integration as a future Phase 1 evaluation item.

It also supports the opposite operational decision for Phase 0: do not add MCP wiring yet, because that would create integration surface before deterministic edge is proven.

## Open Questions

- Является ли выбранный MCP server maintained enough for production research workflows?
- Нужен ли нам MCP вообще, или достаточно REST API + scheduled research scripts?
