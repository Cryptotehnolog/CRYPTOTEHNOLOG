---
type: workflow
status: active
confidence: high
updated: 2026-05-20
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Workflow: Wiki Health Check

The wiki must be checked periodically so automated maintenance does not accumulate quiet errors.

## Checks

- Every managed Markdown page has YAML frontmatter.
- Every wiki page is linked from `knowledge/index.md`.
- Every knowledge edit appends to `knowledge/log.md`.
- Local Markdown links resolve to existing files.
- Low-confidence pages are easy to find.
- Rejected and superseded pages remain visible.
- Contradictions are documented instead of erased.

## Pre-Commit Policy

`scripts/kb_health_check.ps1` is allowed to run in a Git pre-commit hook. Therefore it must remain fast, local, deterministic, and network-free.

`scripts/validate_local_links.ps1` validates only local Markdown links. It is included in CI and `scripts/check_all.ps1`, but is not currently installed in the pre-commit hook.

It must not call:

- LLMs,
- external APIs,
- external URL validators,
- Docker,
- databases,
- long-running audits,
- heavy test suites.

If a knowledge-base check needs network access, LLM judgment, external URL validation, or heavy computation, it must be implemented as a separate CI/manual audit script instead of being added to `kb_health_check.ps1`.

## Frequency

Run after every source ingest and before major architecture changes.
