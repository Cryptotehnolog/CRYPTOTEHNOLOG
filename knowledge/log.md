---
type: system
status: active
confidence: high
updated: 2026-05-20
sources: []
---

# Knowledge Base Log

## [2026-05-20] ingest | Karpathy LLM Wiki

Created the CRYPTOTEHNOLOG knowledge-base structure from Karpathy's LLM Wiki pattern:

- added immutable raw source note,
- added schema and operating rules,
- added index and append-only log,
- added initial concept, workflow, decision, and risk pages,
- added health-check script.

## [2026-05-20] automation | CI and source ingest

Added GitHub Actions CI for Rust checks and knowledge-base health checks. Added `scripts/new_source_note.ps1` to create raw source notes with stable source IDs, frontmatter, index entries, log entries, and immediate health-check validation.

## [2026-05-20] workflow | Codex and Obsidian usage

Documented how Codex should read and update the wiki during engineering work, and how Obsidian should be used as a Markdown vault interface without becoming a runtime dependency.
