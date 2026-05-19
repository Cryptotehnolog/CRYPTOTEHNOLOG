#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventMeta {
    pub event_id: String,
    pub source: String,
    pub exchange_ts_ms: i64,
    pub received_ts_ms: i64,
    pub instrument_id: String,
    pub schema_version: u16,
    pub config_version: String,
}

#[derive(Debug, Clone, PartialEq)]
pub enum MarketEvent {
    DeribitOptionQuote(DeribitOptionQuote),
    PolymarketOutcomeQuote(PolymarketOutcomeQuote),
}

#[derive(Debug, Clone, PartialEq)]
pub struct DeribitOptionQuote {
    pub meta: EventMeta,
    pub underlying: String,
    pub expiry_ts_ms: i64,
    pub strike: f64,
    pub option_kind: OptionKind,
    pub bid: f64,
    pub ask: f64,
    pub mark_iv: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OptionKind {
    Call,
    Put,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PolymarketOutcomeQuote {
    pub meta: EventMeta,
    pub event_slug: String,
    pub market_slug: String,
    pub outcome: String,
    pub bid_probability: f64,
    pub ask_probability: f64,
    pub liquidity_usd: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ProbabilityBasisFeature {
    pub meta: EventMeta,
    pub deribit_instrument_id: String,
    pub polymarket_market_slug: String,
    pub model_probability: f64,
    pub polymarket_mid_probability: f64,
    pub gross_edge_probability: f64,
    pub estimated_cost_probability: f64,
}

impl ProbabilityBasisFeature {
    pub fn net_edge_probability(&self) -> f64 {
        self.gross_edge_probability.abs() - self.estimated_cost_probability
    }

    pub fn survives_costs(&self, threshold_probability: f64) -> bool {
        self.net_edge_probability() >= threshold_probability
    }
}
