# CRYPTOTEHNOLOG

Deterministic research and trading infrastructure for testing crypto probability-basis ideas.

The first MVP is deliberately narrow: compare Deribit ETH option-implied probabilities with Polymarket event prices, record observations, and prove whether the spread survives fees, spreads, slippage, settlement mismatch, and liquidity constraints.

No live trading is part of the MVP.

## Current Decision

We are starting with `Deribit + Polymarket probability_basis`, not funding carry.

This is not called arbitrage yet. The current goal is evidence:

- Can matching events be found reliably?
- Do expiry and settlement definitions match closely enough?
- Is there enough liquidity on both sides?
- Does the observed spread survive estimated costs?
- Can the same raw event log be replayed deterministically?

## Repository Layout

- `crates/common` - canonical Rust event contracts.
- `crates/replay` - deterministic replay skeleton.
- `config/` - human-approved strategy, risk, venue, and instrument config.
- `knowledge/` - LLM-maintained project knowledge base.
- `migrations/` - PostgreSQL schema for event sourcing and observations.
- `research/` - Python research scripts and notebooks later.
- `scripts/` - local automation scripts.
- `tests/` - Python tests later.
- `PROJECT_REVIEW.md` - initial engineering review.

## Local Infrastructure

PostgreSQL is the source of truth. Redis will be used as a transient message bus after the contracts stabilize.

Start local infra:

```powershell
docker compose up -d
```

Run the current Rust replay smoke test:

```powershell
cargo run -p cryptotehnolog-replay
```

Run the knowledge-base health check:

```powershell
.\scripts\kb_health_check.ps1
```

Run the local Markdown link check:

```powershell
.\scripts\validate_local_links.ps1
```

Run all fast local checks:

```powershell
.\scripts\check_all.ps1
```

Create a raw source note:

```powershell
.\scripts\new_source_note.ps1 -Title "Source title" -Url "https://example.com"
```

## Knowledge Base

The project uses a local Markdown knowledge base inspired by Karpathy's LLM Wiki pattern.

- Raw source notes live in `knowledge/raw/`.
- Synthesized project pages live in `knowledge/wiki/`.
- The operating contract is `knowledge/schema.md`.
- `knowledge/index.md` is the content map.
- `knowledge/log.md` is the append-only maintenance history.

Codex should update the knowledge base automatically whenever a durable project decision, source analysis, risk critique, or reusable synthesis appears.

Codex usage rule:

- before architecture or strategy code, read `knowledge/index.md` and the relevant wiki pages;
- after durable decisions or reusable analysis, update the relevant wiki page, `knowledge/index.md`, and `knowledge/log.md`;
- run `.\scripts\kb_health_check.ps1` before committing knowledge changes.

Obsidian usage:

- open `D:\CRYPTOTEHNOLOG\knowledge` as an Obsidian vault;
- use it for reading, graph navigation, backlinks, and manual review;
- do not make Obsidian plugins a runtime dependency of the trading system.

## Risk Stance

MVP constraints:

- No live orders.
- No AI agent in the execution path.
- No Kelly sizing.
- No short Deribit options.
- No short Polymarket outcomes.
- PostgreSQL event journal before derived features.
- Deterministic replay before real ingestion.

## Next Improvements To Automate

1. Add `justfile` or `Makefile` equivalents for Windows-friendly commands.
2. Add a migration runner.
3. Add deterministic replay tests.
4. Add JSON serialization once external dependencies are allowed.
5. Add Deribit and Polymarket discovery adapters behind traits.
6. Add a report that lists candidate market pairs and rejects bad matches with reasons.
