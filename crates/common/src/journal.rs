use crate::events::{MarketEvent, RawDeribitEvent, RawPolymarketEvent, ReplayEventFilter};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JournalErrorKind {
    DuplicateEvent,
    Storage,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JournalError {
    pub kind: JournalErrorKind,
    pub message: String,
}

impl JournalError {
    pub fn new(kind: JournalErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }

    pub fn duplicate_event(event_id: &str) -> Self {
        Self::new(
            JournalErrorKind::DuplicateEvent,
            format!("duplicate event_id: {event_id}"),
        )
    }
}

pub trait EventJournal {
    fn append_raw_deribit_event(&mut self, event: RawDeribitEvent) -> Result<(), JournalError>;

    fn append_raw_polymarket_event(
        &mut self,
        event: RawPolymarketEvent,
    ) -> Result<(), JournalError>;

    fn append_market_event(&mut self, event: MarketEvent) -> Result<(), JournalError>;

    fn read_events_for_replay(
        &self,
        filter: ReplayEventFilter,
    ) -> Result<Vec<MarketEvent>, JournalError>;
}

#[derive(Debug, Default, Clone)]
pub struct InMemoryEventJournal {
    raw_deribit_events: Vec<RawDeribitEvent>,
    raw_polymarket_events: Vec<RawPolymarketEvent>,
    market_events: Vec<MarketEvent>,
}

impl InMemoryEventJournal {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn raw_deribit_events(&self) -> &[RawDeribitEvent] {
        &self.raw_deribit_events
    }

    pub fn raw_polymarket_events(&self) -> &[RawPolymarketEvent] {
        &self.raw_polymarket_events
    }

    pub fn market_events(&self) -> &[MarketEvent] {
        &self.market_events
    }

    fn contains_event_id(&self, event_id: &str) -> bool {
        self.raw_deribit_events
            .iter()
            .any(|event| event.meta.event_id == event_id)
            || self
                .raw_polymarket_events
                .iter()
                .any(|event| event.meta.event_id == event_id)
            || self
                .market_events
                .iter()
                .any(|event| event.meta().event_id == event_id)
    }
}

impl EventJournal for InMemoryEventJournal {
    fn append_raw_deribit_event(&mut self, event: RawDeribitEvent) -> Result<(), JournalError> {
        if self.contains_event_id(&event.meta.event_id) {
            return Err(JournalError::duplicate_event(&event.meta.event_id));
        }
        self.raw_deribit_events.push(event);
        Ok(())
    }

    fn append_raw_polymarket_event(
        &mut self,
        event: RawPolymarketEvent,
    ) -> Result<(), JournalError> {
        if self.contains_event_id(&event.meta.event_id) {
            return Err(JournalError::duplicate_event(&event.meta.event_id));
        }
        self.raw_polymarket_events.push(event);
        Ok(())
    }

    fn append_market_event(&mut self, event: MarketEvent) -> Result<(), JournalError> {
        if self.contains_event_id(&event.meta().event_id) {
            return Err(JournalError::duplicate_event(&event.meta().event_id));
        }
        self.market_events.push(event);
        Ok(())
    }

    fn read_events_for_replay(
        &self,
        filter: ReplayEventFilter,
    ) -> Result<Vec<MarketEvent>, JournalError> {
        let mut events: Vec<MarketEvent> = self
            .market_events
            .iter()
            .filter(|event| filter.matches_market_event(event))
            .cloned()
            .collect();

        events.sort_by_key(|event| {
            let meta = event.meta();
            (meta.received_ts_ms, meta.event_id.clone())
        });

        Ok(events)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::events::{
        DeribitOptionQuote, EventMeta, MarketEvent, OptionKind, PolymarketApiLayer,
        PolymarketOutcomeQuote, RawDeribitEvent, RawPolymarketEvent, ReplayEventFilter,
    };

    fn meta(event_id: &str, instrument_id: &str, received_ts_ms: i64) -> EventMeta {
        EventMeta {
            event_id: event_id.to_string(),
            source: "mock".to_string(),
            exchange_ts_ms: received_ts_ms - 100,
            received_ts_ms,
            instrument_id: instrument_id.to_string(),
            schema_version: 1,
            config_version: "test".to_string(),
        }
    }

    fn deribit_quote(event_id: &str, received_ts_ms: i64) -> MarketEvent {
        MarketEvent::DeribitOptionQuote(DeribitOptionQuote {
            meta: meta(event_id, "ETH-20260601-3000-C", received_ts_ms),
            underlying: "ETH".to_string(),
            expiry_ts_ms: 1_780_000_000_000,
            strike: 3000.0,
            option_kind: OptionKind::Call,
            bid: 0.12,
            ask: 0.13,
            mark_iv: 0.62,
        })
    }

    fn polymarket_quote(event_id: &str, received_ts_ms: i64) -> MarketEvent {
        MarketEvent::PolymarketOutcomeQuote(PolymarketOutcomeQuote {
            meta: meta(event_id, "eth-above-3000-june-1", received_ts_ms),
            event_slug: "eth-above-3000".to_string(),
            market_slug: "eth-above-3000-june-1".to_string(),
            outcome: "Yes".to_string(),
            bid_probability: 0.51,
            ask_probability: 0.53,
            liquidity_usd: 10_000.0,
        })
    }

    #[test]
    fn journal_preserves_raw_events_and_rejects_duplicates() {
        let mut journal = InMemoryEventJournal::new();
        let raw_deribit = RawDeribitEvent {
            meta: meta("raw-1", "ETH-20260601-3000-C", 1000),
            endpoint_or_channel: "public/ticker".to_string(),
            payload_json: "{}".to_string(),
        };
        let raw_polymarket = RawPolymarketEvent {
            meta: meta("raw-2", "eth-above-3000-june-1", 1001),
            api_layer: PolymarketApiLayer::Gamma,
            payload_json: "{}".to_string(),
        };

        journal
            .append_raw_deribit_event(raw_deribit.clone())
            .unwrap();
        journal
            .append_raw_polymarket_event(raw_polymarket.clone())
            .unwrap();

        assert_eq!(journal.raw_deribit_events(), &[raw_deribit.clone()]);
        assert_eq!(journal.raw_polymarket_events(), &[raw_polymarket]);

        let error = journal.append_raw_deribit_event(raw_deribit).unwrap_err();
        assert_eq!(error.kind, JournalErrorKind::DuplicateEvent);
    }

    #[test]
    fn journal_reads_replay_events_in_deterministic_order() {
        let mut journal = InMemoryEventJournal::new();
        journal
            .append_market_event(deribit_quote("b", 2000))
            .unwrap();
        journal
            .append_market_event(polymarket_quote("poly", 1500))
            .unwrap();
        journal
            .append_market_event(deribit_quote("a", 2000))
            .unwrap();

        let events = journal
            .read_events_for_replay(ReplayEventFilter {
                start_ts_ms: 1000,
                end_ts_ms: 2500,
                event_types: vec![],
                instrument_ids: vec![],
                config_version: Some("test".to_string()),
            })
            .unwrap();

        let event_ids: Vec<&str> = events
            .iter()
            .map(|event| event.meta().event_id.as_str())
            .collect();

        assert_eq!(event_ids, vec!["poly", "a", "b"]);
    }

    #[test]
    fn journal_replay_filter_matches_event_type_and_instrument() {
        let mut journal = InMemoryEventJournal::new();
        journal
            .append_market_event(deribit_quote("d", 2000))
            .unwrap();
        journal
            .append_market_event(polymarket_quote("p", 2001))
            .unwrap();

        let events = journal
            .read_events_for_replay(ReplayEventFilter {
                start_ts_ms: 0,
                end_ts_ms: 3000,
                event_types: vec!["polymarket_outcome_quote".to_string()],
                instrument_ids: vec!["eth-above-3000-june-1".to_string()],
                config_version: None,
            })
            .unwrap();

        assert_eq!(events.len(), 1);
        assert_eq!(events[0].meta().event_id, "p");
    }
}
