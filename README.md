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
- `migrations/` - PostgreSQL schema for event sourcing and observations.
- `research/` - Python research scripts and notebooks later.
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

