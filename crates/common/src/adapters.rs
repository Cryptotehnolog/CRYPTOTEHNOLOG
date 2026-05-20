use crate::events::{
    DeribitInstrument, DeribitOptionQuote, PolymarketMarket, PolymarketOutcomeQuote,
    RawDeribitEvent, RawPolymarketEvent,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AdapterErrorKind {
    Network,
    MalformedPayload,
    StaleData,
    MissingRequiredField,
    UnsupportedInstrument,
    RateLimit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdapterError {
    pub kind: AdapterErrorKind,
    pub message: String,
}

impl AdapterError {
    pub fn new(kind: AdapterErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }

    pub fn unsupported_instrument(instrument_id: &str) -> Self {
        Self::new(
            AdapterErrorKind::UnsupportedInstrument,
            format!("unsupported instrument or market: {instrument_id}"),
        )
    }
}

pub trait DeribitDiscoveryAdapter {
    fn list_eth_options(&self) -> Result<Vec<DeribitInstrument>, AdapterError>;

    fn get_option_snapshot(&self, instrument_id: &str) -> Result<DeribitOptionQuote, AdapterError>;

    fn get_raw_option_snapshot(&self, instrument_id: &str)
    -> Result<RawDeribitEvent, AdapterError>;
}

pub trait PolymarketDiscoveryAdapter {
    fn list_crypto_markets(&self) -> Result<Vec<PolymarketMarket>, AdapterError>;

    fn get_market_snapshot(
        &self,
        market_slug: &str,
        outcome: &str,
    ) -> Result<PolymarketOutcomeQuote, AdapterError>;

    fn get_raw_market_snapshot(
        &self,
        market_slug: &str,
    ) -> Result<RawPolymarketEvent, AdapterError>;
}

#[derive(Debug, Clone)]
pub struct MockDeribitAdapter {
    instruments: Vec<DeribitInstrument>,
    quotes: Vec<DeribitOptionQuote>,
    raw_events: Vec<RawDeribitEvent>,
}

impl MockDeribitAdapter {
    pub fn new(
        instruments: Vec<DeribitInstrument>,
        quotes: Vec<DeribitOptionQuote>,
        raw_events: Vec<RawDeribitEvent>,
    ) -> Self {
        Self {
            instruments,
            quotes,
            raw_events,
        }
    }
}

impl DeribitDiscoveryAdapter for MockDeribitAdapter {
    fn list_eth_options(&self) -> Result<Vec<DeribitInstrument>, AdapterError> {
        Ok(self.instruments.clone())
    }

    fn get_option_snapshot(&self, instrument_id: &str) -> Result<DeribitOptionQuote, AdapterError> {
        self.quotes
            .iter()
            .find(|quote| quote.meta.instrument_id == instrument_id)
            .cloned()
            .ok_or_else(|| AdapterError::unsupported_instrument(instrument_id))
    }

    fn get_raw_option_snapshot(
        &self,
        instrument_id: &str,
    ) -> Result<RawDeribitEvent, AdapterError> {
        self.raw_events
            .iter()
            .find(|event| event.meta.instrument_id == instrument_id)
            .cloned()
            .ok_or_else(|| AdapterError::unsupported_instrument(instrument_id))
    }
}

#[derive(Debug, Clone)]
pub struct MockPolymarketAdapter {
    markets: Vec<PolymarketMarket>,
    quotes: Vec<PolymarketOutcomeQuote>,
    raw_events: Vec<RawPolymarketEvent>,
}

impl MockPolymarketAdapter {
    pub fn new(
        markets: Vec<PolymarketMarket>,
        quotes: Vec<PolymarketOutcomeQuote>,
        raw_events: Vec<RawPolymarketEvent>,
    ) -> Self {
        Self {
            markets,
            quotes,
            raw_events,
        }
    }
}

impl PolymarketDiscoveryAdapter for MockPolymarketAdapter {
    fn list_crypto_markets(&self) -> Result<Vec<PolymarketMarket>, AdapterError> {
        Ok(self.markets.clone())
    }

    fn get_market_snapshot(
        &self,
        market_slug: &str,
        outcome: &str,
    ) -> Result<PolymarketOutcomeQuote, AdapterError> {
        self.quotes
            .iter()
            .find(|quote| quote.market_slug == market_slug && quote.outcome == outcome)
            .cloned()
            .ok_or_else(|| AdapterError::unsupported_instrument(market_slug))
    }

    fn get_raw_market_snapshot(
        &self,
        market_slug: &str,
    ) -> Result<RawPolymarketEvent, AdapterError> {
        self.raw_events
            .iter()
            .find(|event| event.meta.instrument_id == market_slug)
            .cloned()
            .ok_or_else(|| AdapterError::unsupported_instrument(market_slug))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::events::{
        EventMeta, OptionKind, PolymarketApiLayer, RawDeribitEvent, RawPolymarketEvent,
    };

    fn meta(event_id: &str, instrument_id: &str) -> EventMeta {
        EventMeta {
            event_id: event_id.to_string(),
            source: "mock".to_string(),
            exchange_ts_ms: 1_779_200_000_000,
            received_ts_ms: 1_779_200_000_100,
            instrument_id: instrument_id.to_string(),
            schema_version: 1,
            config_version: "test".to_string(),
        }
    }

    #[test]
    fn mock_deribit_adapter_returns_instrument_quote_and_raw_event() {
        let instrument = DeribitInstrument {
            instrument_id: "ETH-20260601-3000-C".to_string(),
            underlying: "ETH".to_string(),
            expiry_ts_ms: 1_780_000_000_000,
            strike: 3000.0,
            option_kind: OptionKind::Call,
        };
        let quote = DeribitOptionQuote {
            meta: meta("quote-1", &instrument.instrument_id),
            underlying: "ETH".to_string(),
            expiry_ts_ms: instrument.expiry_ts_ms,
            strike: instrument.strike,
            option_kind: OptionKind::Call,
            underlying_price: 3100.0,
            bid: 0.12,
            ask: 0.13,
            mark_iv: 0.62,
        };
        let raw = RawDeribitEvent {
            meta: meta("raw-1", &instrument.instrument_id),
            endpoint_or_channel: "public/ticker".to_string(),
            payload_json: "{\"instrument_name\":\"ETH-20260601-3000-C\"}".to_string(),
        };
        let adapter = MockDeribitAdapter::new(vec![instrument.clone()], vec![quote], vec![raw]);

        assert_eq!(
            adapter.list_eth_options().unwrap(),
            vec![instrument.clone()]
        );
        assert_eq!(
            adapter
                .get_option_snapshot(&instrument.instrument_id)
                .unwrap()
                .mark_iv,
            0.62
        );
        assert_eq!(
            adapter
                .get_raw_option_snapshot(&instrument.instrument_id)
                .unwrap()
                .endpoint_or_channel,
            "public/ticker"
        );
    }

    #[test]
    fn mock_polymarket_adapter_returns_market_quote_and_raw_event() {
        let market = PolymarketMarket {
            event_slug: "eth-above-3000".to_string(),
            market_slug: "eth-above-3000-june-1".to_string(),
            question: "Will ETH be above 3000 on June 1?".to_string(),
            outcomes: vec!["Yes".to_string(), "No".to_string()],
            close_ts_ms: Some(1_780_000_000_000),
            liquidity_usd: Some(10_000.0),
        };
        let quote = PolymarketOutcomeQuote {
            meta: meta("poly-quote-1", &market.market_slug),
            event_slug: market.event_slug.clone(),
            market_slug: market.market_slug.clone(),
            outcome: "Yes".to_string(),
            bid_probability: 0.51,
            ask_probability: 0.53,
            liquidity_usd: 10_000.0,
        };
        let raw = RawPolymarketEvent {
            meta: meta("poly-raw-1", &market.market_slug),
            api_layer: PolymarketApiLayer::Gamma,
            payload_json: "{\"slug\":\"eth-above-3000-june-1\"}".to_string(),
        };
        let adapter = MockPolymarketAdapter::new(vec![market.clone()], vec![quote], vec![raw]);

        assert_eq!(adapter.list_crypto_markets().unwrap(), vec![market.clone()]);
        assert_eq!(
            adapter
                .get_market_snapshot(&market.market_slug, "Yes")
                .unwrap()
                .bid_probability,
            0.51
        );
        assert_eq!(
            adapter
                .get_raw_market_snapshot(&market.market_slug)
                .unwrap()
                .api_layer,
            PolymarketApiLayer::Gamma
        );
    }

    #[test]
    fn mock_adapters_return_unsupported_errors_for_missing_ids() {
        let deribit = MockDeribitAdapter::new(vec![], vec![], vec![]);
        let error = deribit.get_option_snapshot("missing").unwrap_err();

        assert_eq!(error.kind, AdapterErrorKind::UnsupportedInstrument);
    }
}
