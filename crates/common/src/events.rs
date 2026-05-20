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

impl MarketEvent {
    pub fn meta(&self) -> &EventMeta {
        match self {
            MarketEvent::DeribitOptionQuote(event) => &event.meta,
            MarketEvent::PolymarketOutcomeQuote(event) => &event.meta,
        }
    }

    pub fn event_type(&self) -> &'static str {
        match self {
            MarketEvent::DeribitOptionQuote(_) => "deribit_option_quote",
            MarketEvent::PolymarketOutcomeQuote(_) => "polymarket_outcome_quote",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RawDeribitEvent {
    pub meta: EventMeta,
    pub endpoint_or_channel: String,
    pub payload_json: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PolymarketApiLayer {
    Gamma,
    Clob,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RawPolymarketEvent {
    pub meta: EventMeta,
    pub api_layer: PolymarketApiLayer,
    pub payload_json: String,
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
pub struct DeribitInstrument {
    pub instrument_id: String,
    pub underlying: String,
    pub expiry_ts_ms: i64,
    pub strike: f64,
    pub option_kind: OptionKind,
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
pub struct PolymarketMarket {
    pub event_slug: String,
    pub market_slug: String,
    pub question: String,
    pub outcomes: Vec<String>,
    pub close_ts_ms: Option<i64>,
    pub liquidity_usd: Option<f64>,
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReplayEventFilter {
    pub start_ts_ms: i64,
    pub end_ts_ms: i64,
    pub event_types: Vec<String>,
    pub instrument_ids: Vec<String>,
    pub config_version: Option<String>,
}

impl ReplayEventFilter {
    pub fn matches_market_event(&self, event: &MarketEvent) -> bool {
        let meta = event.meta();
        let event_type = event.event_type();

        if meta.received_ts_ms < self.start_ts_ms || meta.received_ts_ms > self.end_ts_ms {
            return false;
        }

        if !self.event_types.is_empty()
            && !self
                .event_types
                .iter()
                .any(|candidate| candidate == event_type)
        {
            return false;
        }

        if !self.instrument_ids.is_empty()
            && !self
                .instrument_ids
                .iter()
                .any(|candidate| candidate == &meta.instrument_id)
        {
            return false;
        }

        if let Some(config_version) = &self.config_version {
            if &meta.config_version != config_version {
                return false;
            }
        }

        true
    }
}
