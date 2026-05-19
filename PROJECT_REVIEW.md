# CRYPTOTEHNOLOG - engineering review

Date: 2026-05-19

## Executive position

The project idea is technically interesting, but the current proposal is too broad for an MVP and mixes three different problem classes:

1. reliable market-data infrastructure,
2. statistically defensible trading research,
3. AI-assisted post-trade analysis.

The deterministic core must come first. The AI layer should remain out of scope until the system has clean data, reproducible backtests, and paper-trading telemetry. That part of your plan is correct.

The weakest parts of the current design are the proposed market assumptions:

- BitMEX commodity perpetual availability and liquidity must be verified before building around XAUtUSDT and BRENTUSDT.
- The funding carry strategy is not market-neutral in the MVP version if it shorts only the perpetual without a real hedge.
- The Deribit-to-Polymarket "probability arbitrage" is not a simple arbitrage. It is a basis trade across different settlement definitions, liquidity regimes, margin models, expiries, and resolution risk.
- Redis Streams are useful for decoupling services, but they should not become the source of truth.
- Rust for every deterministic component may slow early research. Rust is excellent for the execution/risk path, but feature research and backtesting may move faster in Python until formulas stabilize.

## What I would change

### 1. Reduce the MVP

Start with one strategy and one exchange/data source pair.

Recommended MVP:

- Data ingestion for Deribit ETH options and Polymarket crypto markets.
- Normalized market snapshots.
- Backtest/event replay.
- Paper execution simulator.
- PostgreSQL event journal.
- No live orders.
- No Hermes, LightRAG, OmniRoute.

Reason: the probability-arbitrage thesis is the more unique edge, but it is also the most likely to fail because of market-definition mismatch. It deserves validation before we build a large execution platform.

Alternative MVP:

- BitMEX funding ingestion only.
- Funding feature calculation.
- Paper funding strategy.
- PnL simulation with adverse price movement.

This is simpler technically, but the edge is weaker unless we find a real hedge.

### 2. Treat "paper trading" as event replay plus live shadow mode

Paper trading that only consumes live quotes is not enough. We need deterministic replay from stored raw events.

Minimum requirement:

- Every raw inbound event gets persisted before feature calculation.
- Every signal, risk decision, simulated fill, and portfolio update is replayable.
- Strategy outputs must be deterministic for the same input event log and config version.

### 3. Add a schema and contract layer early

Do not use Pydantic as the internal model if the deterministic core is Rust. Use Rust structs as canonical types and serialize through JSON or MessagePack initially. Later, if needed, move to Protobuf or FlatBuffers.

Recommended event families:

- `MarketEvent`
- `FeatureEvent`
- `SignalEvent`
- `RiskDecision`
- `OrderIntent`
- `ExecutionReport`
- `PortfolioSnapshot`

Each event should include:

- `event_id`
- `source`
- `exchange_ts`
- `received_ts`
- `instrument_id`
- `schema_version`
- `config_version`

### 4. Separate research from production config

Human-approved config changes should be explicit, versioned, and auditable.

Add:

- `config/strategies.toml`
- `config/risk.toml`
- `config/instruments.toml`
- `config/venues.toml`

The AI agents may write recommendations, but not config patches that auto-apply.

### 5. Risk engine needs more than Kelly

Kelly sizing is fragile when edge estimates are noisy. In this project, the edge estimate will be very noisy at first.

Use capped fractional sizing for MVP:

- fixed notional percentage per strategy,
- hard max position size,
- hard daily loss limit,
- hard max drawdown,
- kill switch,
- per-venue exposure limit,
- stale-data rejection,
- spread/liquidity rejection.

Kelly can be added later as a research metric, not as the first production sizer.

## Strategy critique

### Funding Rate Carry

Problem: if the MVP only shorts a positive-funding perp without a hedge, this is not carry arbitrage. It is directional short exposure with funding income.

What must be added:

- hedge instrument discovery,
- basis tracking,
- liquidation/margin simulation,
- borrow/financing assumptions if spot hedge exists,
- stress test for sharp commodity rallies.

Verdict: acceptable only as a tiny paper strategy or data-collection strategy. Do not treat it as market-neutral.

### Deribit vs Polymarket Probability Trade

Problem: Deribit options do not map cleanly to Polymarket binary outcomes.

Key mismatches:

- European option payoff vs prediction-market binary payout.
- Different expiry timestamps and settlement sources.
- Path-independent option payoff vs event-specific market wording.
- Implied probability from Black-Scholes is model-dependent.
- Polymarket prices include liquidity, resolution, and capital lockup premia.
- Shorting Polymarket outcomes may not be operationally equivalent to selling probability.
- Short option positions on Deribit create convex tail risk.

Better MVP framing:

Do not call it arbitrage yet. Call it `probability_basis`.

First validate:

- whether equivalent events can be matched programmatically,
- whether the spread persists after fees/spreads/slippage,
- whether execution size exists on both venues,
- whether mark-to-market PnL behaves as expected.

Verdict: promising as research, dangerous as a claimed arbitrage.

## Architecture recommendation

Suggested initial stack:

- Rust workspace for deterministic services.
- Python only for notebooks/research/reports at first.
- PostgreSQL as source of truth.
- Redis Streams as transient bus.
- Docker Compose for local infra.
- Prometheus/Grafana after the first full event loop works.

Initial Rust crates:

- `crates/common`
- `crates/ingestion`
- `crates/features`
- `crates/strategy`
- `crates/risk`
- `crates/execution`
- `crates/replay`

Initial Python package:

- `research/`
- `scripts/`

## Immediate next step

Build a narrow foundation:

1. scaffold repo,
2. add Docker Compose with Postgres and Redis,
3. define event schemas,
4. define config files,
5. create a replay-first paper-trading loop with mocked market events,
6. add CI/lint/test commands.

Only after this should we connect real exchange APIs.

## MVP decision - 2026-05-19

Chosen first MVP: Deribit + Polymarket `probability_basis`.

The first milestone is not trading. The first milestone is to prove or disprove whether event pairs can be matched cleanly enough for systematic research:

- equivalent underlying,
- compatible event wording,
- compatible expiry and settlement timestamp,
- sufficient order-book liquidity,
- spread that survives estimated costs,
- deterministic replay from stored raw events.

Funding carry is postponed. It remains a possible second MVP, but only after we define a real hedge or explicitly label it as directional funding-income exposure.
