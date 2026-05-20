# AGENTS.md

This file defines the operating rules for AI agents working in this repository.

## Before Work

For architecture, strategy, risk, market-data, research, or knowledge-base changes:

1. Read `knowledge/schema.md`.
2. Read `knowledge/index.md`.
3. Open relevant pages from `knowledge/wiki/`.
4. Check active decisions, rejected ideas, low-confidence assumptions, and known risks.

Small mechanical actions such as `git status`, formatting, or reading a file do not require a full wiki review.

## During Work

- Prefer small, reviewable changes.
- Keep runtime trading behavior in code, tests, configs, migrations, and event logs.
- Do not make deterministic trading services depend on Markdown, Obsidian, or LLM-generated summaries.
- Do not store secrets, API keys, exchange credentials, or private account details in the knowledge base.

## After Work

If the work creates durable project knowledge, update:

1. the relevant page in `knowledge/wiki/`,
2. `knowledge/index.md` if a new page was added,
3. `knowledge/log.md`.

Before committing, run:

```powershell
.\scripts\kb_health_check.ps1
```

## Check Policy

Pre-commit checks must remain fast, local, deterministic, and network-free.

They must not:

- call LLMs,
- call external APIs,
- validate external URLs,
- run heavy tests or long audits.

If a check becomes slow or needs network access, move it to CI or a separate manual audit script.

