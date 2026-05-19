use cryptotehnolog_common::events::{EventMeta, ProbabilityBasisFeature};

fn main() {
    let feature = ProbabilityBasisFeature {
        meta: EventMeta {
            event_id: "mock-feature-1".to_string(),
            source: "mock-replay".to_string(),
            exchange_ts_ms: 1_779_200_000_000,
            received_ts_ms: 1_779_200_000_100,
            instrument_id: "ETH-20260601-3000-C".to_string(),
            schema_version: 1,
            config_version: "dev".to_string(),
        },
        deribit_instrument_id: "ETH-20260601-3000-C".to_string(),
        polymarket_market_slug: "eth-above-3000-on-2026-06-01".to_string(),
        model_probability: 0.542,
        polymarket_mid_probability: 0.578,
        gross_edge_probability: -0.036,
        estimated_cost_probability: 0.010,
    };

    println!(
        "probability_basis event_id={} net_edge={:.4} survives={}",
        feature.meta.event_id,
        feature.net_edge_probability(),
        feature.survives_costs(0.025)
    );
}
