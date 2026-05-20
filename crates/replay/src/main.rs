use cryptotehnolog_common::events::{
    DeribitOptionQuote, EventMeta, MarketEvent, OptionKind, PolymarketOutcomeQuote,
};
use cryptotehnolog_common::probability_basis::{
    ProbabilityBasisConfig, match_from_market_events, render_match_report,
};

fn main() {
    for line in run_probability_basis_replay_report() {
        println!("{line}");
    }
}

fn run_probability_basis_replay_report() -> Vec<String> {
    let decisions = match_from_market_events(&golden_probability_basis_events(), &config());
    render_match_report(&decisions)
}

fn config() -> ProbabilityBasisConfig {
    ProbabilityBasisConfig {
        min_net_edge_probability: 0.025,
        max_expiry_mismatch_ms: 86_400_000,
        min_polymarket_liquidity_usd: 1000.0,
        estimated_cost_probability: 0.010,
    }
}

fn golden_probability_basis_events() -> Vec<MarketEvent> {
    vec![
        MarketEvent::DeribitOptionQuote(DeribitOptionQuote {
            meta: meta("deribit-quote-1", "ETH-20260601-3000-C", 1_779_200_000_000),
            underlying: "ETH".to_string(),
            expiry_ts_ms: 1_780_000_000_000,
            strike: 3000.0,
            option_kind: OptionKind::Call,
            underlying_price: 3100.0,
            bid: 0.12,
            ask: 0.13,
            mark_iv: 0.62,
        }),
        MarketEvent::PolymarketOutcomeQuote(PolymarketOutcomeQuote {
            meta: meta(
                "polymarket-quote-1",
                "eth-above-3000-june-1",
                1_780_000_000_000,
            ),
            event_slug: "eth-above-3000".to_string(),
            market_slug: "eth-above-3000-june-1".to_string(),
            outcome: "Yes".to_string(),
            bid_probability: 0.51,
            ask_probability: 0.53,
            liquidity_usd: 10_000.0,
        }),
        MarketEvent::PolymarketOutcomeQuote(PolymarketOutcomeQuote {
            meta: meta(
                "polymarket-quote-2",
                "eth-above-3000-low-liquidity",
                1_780_000_000_000,
            ),
            event_slug: "eth-above-3000-low-liquidity".to_string(),
            market_slug: "eth-above-3000-low-liquidity".to_string(),
            outcome: "Yes".to_string(),
            bid_probability: 0.51,
            ask_probability: 0.53,
            liquidity_usd: 500.0,
        }),
    ]
}

fn meta(event_id: &str, instrument_id: &str, exchange_ts_ms: i64) -> EventMeta {
    EventMeta {
        event_id: event_id.to_string(),
        source: "golden-replay-fixture".to_string(),
        exchange_ts_ms,
        received_ts_ms: exchange_ts_ms + 100,
        instrument_id: instrument_id.to_string(),
        schema_version: 1,
        config_version: "phase0-golden".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn probability_basis_replay_report_is_stable() {
        assert_eq!(
            run_probability_basis_replay_report(),
            [
                "matched|ETH-20260601-3000-C|eth-above-3000-june-1|net_edge=0.081338|survives=true",
                "rejected|InsufficientLiquidity|ETH-20260601-3000-C|eth-above-3000-low-liquidity",
            ]
        );
    }
}
