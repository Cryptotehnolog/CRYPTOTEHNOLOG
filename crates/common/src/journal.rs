use crate::events::{
    DeribitOptionQuote, EventMeta, MarketEvent, OptionKind, PolymarketOutcomeQuote,
    RawDeribitEvent, RawPolymarketEvent, ReplayEventFilter,
};

pub const EVENT_JOURNAL_TABLE: &str = "event_journal";

pub const EVENT_JOURNAL_COLUMNS: [&str; 9] = [
    "event_id",
    "event_type",
    "source",
    "exchange_ts",
    "received_ts",
    "instrument_id",
    "schema_version",
    "config_version",
    "payload",
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JournalErrorKind {
    DuplicateEvent,
    MalformedPayload,
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

    pub fn malformed_payload(event_id: &str, message: impl Into<String>) -> Self {
        Self::new(
            JournalErrorKind::MalformedPayload,
            format!(
                "malformed event_journal payload for {event_id}: {}",
                message.into()
            ),
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

#[derive(Debug, Clone, PartialEq)]
pub struct EventJournalRow {
    pub event_id: String,
    pub event_type: String,
    pub source: String,
    pub exchange_ts_ms: i64,
    pub received_ts_ms: i64,
    pub instrument_id: String,
    pub schema_version: u16,
    pub config_version: String,
    pub payload_json: String,
}

impl EventJournalRow {
    pub fn from_raw_deribit_event(event: &RawDeribitEvent) -> Self {
        Self {
            event_id: event.meta.event_id.clone(),
            event_type: "raw_deribit_event".to_string(),
            source: event.meta.source.clone(),
            exchange_ts_ms: event.meta.exchange_ts_ms,
            received_ts_ms: event.meta.received_ts_ms,
            instrument_id: event.meta.instrument_id.clone(),
            schema_version: event.meta.schema_version,
            config_version: event.meta.config_version.clone(),
            payload_json: event.payload_json.clone(),
        }
    }

    pub fn from_raw_polymarket_event(event: &RawPolymarketEvent) -> Self {
        Self {
            event_id: event.meta.event_id.clone(),
            event_type: "raw_polymarket_event".to_string(),
            source: event.meta.source.clone(),
            exchange_ts_ms: event.meta.exchange_ts_ms,
            received_ts_ms: event.meta.received_ts_ms,
            instrument_id: event.meta.instrument_id.clone(),
            schema_version: event.meta.schema_version,
            config_version: event.meta.config_version.clone(),
            payload_json: event.payload_json.clone(),
        }
    }

    pub fn from_market_event(event: &MarketEvent) -> Self {
        let meta = event.meta();
        Self {
            event_id: meta.event_id.clone(),
            event_type: event.event_type().to_string(),
            source: meta.source.clone(),
            exchange_ts_ms: meta.exchange_ts_ms,
            received_ts_ms: meta.received_ts_ms,
            instrument_id: meta.instrument_id.clone(),
            schema_version: meta.schema_version,
            config_version: meta.config_version.clone(),
            payload_json: normalized_market_event_payload(event),
        }
    }

    pub fn columns() -> &'static [&'static str; 9] {
        &EVENT_JOURNAL_COLUMNS
    }

    pub fn values(&self) -> [EventJournalRowValue; 9] {
        [
            EventJournalRowValue::Text(self.event_id.clone()),
            EventJournalRowValue::Text(self.event_type.clone()),
            EventJournalRowValue::Text(self.source.clone()),
            EventJournalRowValue::TimestampMillis(self.exchange_ts_ms),
            EventJournalRowValue::TimestampMillis(self.received_ts_ms),
            EventJournalRowValue::Text(self.instrument_id.clone()),
            EventJournalRowValue::Integer(self.schema_version as i64),
            EventJournalRowValue::Text(self.config_version.clone()),
            EventJournalRowValue::Json(self.payload_json.clone()),
        ]
    }

    pub fn to_market_event(&self) -> Result<Option<MarketEvent>, JournalError> {
        match self.event_type.as_str() {
            "deribit_option_quote" => self.deribit_option_quote().map(|event| Some(event)),
            "polymarket_outcome_quote" => self.polymarket_outcome_quote().map(|event| Some(event)),
            _ => Ok(None),
        }
    }

    fn meta(&self) -> EventMeta {
        EventMeta {
            event_id: self.event_id.clone(),
            source: self.source.clone(),
            exchange_ts_ms: self.exchange_ts_ms,
            received_ts_ms: self.received_ts_ms,
            instrument_id: self.instrument_id.clone(),
            schema_version: self.schema_version,
            config_version: self.config_version.clone(),
        }
    }

    fn deribit_option_quote(&self) -> Result<MarketEvent, JournalError> {
        let payload = parse_payload(self)?;
        let option_kind = match required_str(self, &payload, "option_kind")? {
            "Call" => OptionKind::Call,
            "Put" => OptionKind::Put,
            other => {
                return Err(JournalError::malformed_payload(
                    &self.event_id,
                    format!("unsupported option_kind: {other}"),
                ));
            }
        };

        Ok(MarketEvent::DeribitOptionQuote(DeribitOptionQuote {
            meta: self.meta(),
            underlying: required_str(self, &payload, "underlying")?.to_string(),
            expiry_ts_ms: required_i64(self, &payload, "expiry_ts_ms")?,
            strike: required_f64(self, &payload, "strike")?,
            option_kind,
            underlying_price: required_f64(self, &payload, "underlying_price")?,
            bid: required_f64(self, &payload, "bid")?,
            ask: required_f64(self, &payload, "ask")?,
            mark_iv: required_f64(self, &payload, "mark_iv")?,
        }))
    }

    fn polymarket_outcome_quote(&self) -> Result<MarketEvent, JournalError> {
        let payload = parse_payload(self)?;

        Ok(MarketEvent::PolymarketOutcomeQuote(
            PolymarketOutcomeQuote {
                meta: self.meta(),
                event_slug: required_str(self, &payload, "event_slug")?.to_string(),
                market_slug: required_str(self, &payload, "market_slug")?.to_string(),
                outcome: required_str(self, &payload, "outcome")?.to_string(),
                target_expiry_ts_ms: required_i64(self, &payload, "target_expiry_ts_ms")?,
                bid_probability: required_f64(self, &payload, "bid_probability")?,
                ask_probability: required_f64(self, &payload, "ask_probability")?,
                liquidity_usd: required_f64(self, &payload, "liquidity_usd")?,
            },
        ))
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum EventJournalRowValue {
    Text(String),
    TimestampMillis(i64),
    Integer(i64),
    Json(String),
}

pub const NORMALIZED_EVENT_TYPES_FOR_REPLAY: [&str; 2] =
    ["deribit_option_quote", "polymarket_outcome_quote"];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventJournalReplayQuery {
    pub start_ts_ms: i64,
    pub end_ts_ms: i64,
    pub event_types: Vec<String>,
    pub instrument_ids: Vec<String>,
    pub config_version: Option<String>,
}

impl EventJournalReplayQuery {
    pub fn from_filter(filter: ReplayEventFilter) -> Self {
        let event_types = if filter.event_types.is_empty() {
            NORMALIZED_EVENT_TYPES_FOR_REPLAY
                .iter()
                .map(|event_type| (*event_type).to_string())
                .collect()
        } else {
            filter.event_types
        };

        Self {
            start_ts_ms: filter.start_ts_ms,
            end_ts_ms: filter.end_ts_ms,
            event_types,
            instrument_ids: filter.instrument_ids,
            config_version: filter.config_version,
        }
    }

    fn matches_row(&self, row: &EventJournalRow) -> bool {
        if row.received_ts_ms < self.start_ts_ms || row.received_ts_ms > self.end_ts_ms {
            return false;
        }

        if !self
            .event_types
            .iter()
            .any(|candidate| candidate == &row.event_type)
        {
            return false;
        }

        if !self.instrument_ids.is_empty()
            && !self
                .instrument_ids
                .iter()
                .any(|candidate| candidate == &row.instrument_id)
        {
            return false;
        }

        if let Some(config_version) = &self.config_version {
            if &row.config_version != config_version {
                return false;
            }
        }

        true
    }
}

pub trait EventJournalRowReader {
    fn read_event_journal_rows(
        &self,
        query: &EventJournalReplayQuery,
    ) -> Result<Vec<EventJournalRow>, JournalError>;
}

pub trait EventJournalRowWriter {
    fn append_event_journal_row(&mut self, row: EventJournalRow) -> Result<(), JournalError>;
}

#[derive(Debug, Default, Clone, PartialEq)]
pub struct InMemoryEventJournalRowWriter {
    rows: Vec<EventJournalRow>,
}

impl InMemoryEventJournalRowWriter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn rows(&self) -> &[EventJournalRow] {
        &self.rows
    }

    fn contains_event_id(&self, event_id: &str) -> bool {
        self.rows.iter().any(|row| row.event_id == event_id)
    }
}

impl EventJournalRowWriter for InMemoryEventJournalRowWriter {
    fn append_event_journal_row(&mut self, row: EventJournalRow) -> Result<(), JournalError> {
        if self.contains_event_id(&row.event_id) {
            return Err(JournalError::duplicate_event(&row.event_id));
        }

        self.rows.push(row);
        Ok(())
    }
}

#[derive(Debug, Default, Clone, PartialEq)]
pub struct InMemoryEventJournalRowReader {
    rows: Vec<EventJournalRow>,
}

impl InMemoryEventJournalRowReader {
    pub fn new(rows: Vec<EventJournalRow>) -> Self {
        Self { rows }
    }

    pub fn rows(&self) -> &[EventJournalRow] {
        &self.rows
    }
}

impl EventJournalRowReader for InMemoryEventJournalRowReader {
    fn read_event_journal_rows(
        &self,
        query: &EventJournalReplayQuery,
    ) -> Result<Vec<EventJournalRow>, JournalError> {
        let mut rows: Vec<EventJournalRow> = self
            .rows
            .iter()
            .filter(|row| query.matches_row(row))
            .cloned()
            .collect();

        rows.sort_by_key(|row| (row.received_ts_ms, row.event_id.clone()));
        Ok(rows)
    }
}

pub fn read_market_events_for_replay_from_rows<R>(
    reader: &R,
    filter: ReplayEventFilter,
) -> Result<Vec<MarketEvent>, JournalError>
where
    R: EventJournalRowReader,
{
    let query = EventJournalReplayQuery::from_filter(filter);
    let rows = reader.read_event_journal_rows(&query)?;
    let mut events = Vec::with_capacity(rows.len());

    for row in rows {
        if let Some(event) = row.to_market_event()? {
            events.push(event);
        }
    }

    Ok(events)
}

pub struct PostgresEventJournalAdapter;

impl PostgresEventJournalAdapter {
    pub fn table_name() -> &'static str {
        EVENT_JOURNAL_TABLE
    }

    pub fn columns() -> &'static [&'static str; 9] {
        &EVENT_JOURNAL_COLUMNS
    }

    pub fn insert_sql() -> &'static str {
        "INSERT INTO event_journal (event_id, event_type, source, exchange_ts, received_ts, instrument_id, schema_version, config_version, payload) VALUES ($1, $2, $3, to_timestamp($4::double precision / 1000.0), to_timestamp($5::double precision / 1000.0), $6, $7, $8, $9::jsonb)"
    }

    pub fn select_replay_sql() -> &'static str {
        "SELECT event_id, event_type, source, (extract(epoch from exchange_ts) * 1000)::bigint AS exchange_ts_ms, (extract(epoch from received_ts) * 1000)::bigint AS received_ts_ms, instrument_id, schema_version, config_version, payload::text AS payload FROM event_journal WHERE received_ts >= to_timestamp($1::double precision / 1000.0) AND received_ts <= to_timestamp($2::double precision / 1000.0) AND event_type = ANY($3::text[]) AND ($4::text[] IS NULL OR instrument_id = ANY($4::text[])) AND ($5::text IS NULL OR config_version = $5) ORDER BY received_ts ASC, event_id ASC"
    }
}

#[cfg(feature = "postgres-writer")]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PostgresEventJournalWriter {
    connection_label: String,
}

#[cfg(feature = "postgres-writer")]
impl PostgresEventJournalWriter {
    pub fn new(connection_label: impl Into<String>) -> Self {
        Self {
            connection_label: connection_label.into(),
        }
    }

    pub fn connection_label(&self) -> &str {
        &self.connection_label
    }

    pub fn insert_sql(&self) -> &'static str {
        PostgresEventJournalAdapter::insert_sql()
    }
}

#[cfg(feature = "postgres-writer")]
impl EventJournalRowWriter for PostgresEventJournalWriter {
    fn append_event_journal_row(&mut self, _row: EventJournalRow) -> Result<(), JournalError> {
        Err(JournalError::new(
            JournalErrorKind::Storage,
            "postgres event journal writer is a Phase 0 skeleton without database connector",
        ))
    }
}

#[derive(Debug, Default, Clone)]
pub struct InMemoryEventJournal {
    raw_deribit_events: Vec<RawDeribitEvent>,
    raw_polymarket_events: Vec<RawPolymarketEvent>,
    market_events: Vec<MarketEvent>,
    event_journal_rows: Vec<EventJournalRow>,
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

    pub fn event_journal_rows(&self) -> &[EventJournalRow] {
        &self.event_journal_rows
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
        self.event_journal_rows
            .push(EventJournalRow::from_raw_deribit_event(&event));
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
        self.event_journal_rows
            .push(EventJournalRow::from_raw_polymarket_event(&event));
        self.raw_polymarket_events.push(event);
        Ok(())
    }

    fn append_market_event(&mut self, event: MarketEvent) -> Result<(), JournalError> {
        if self.contains_event_id(&event.meta().event_id) {
            return Err(JournalError::duplicate_event(&event.meta().event_id));
        }
        self.event_journal_rows
            .push(EventJournalRow::from_market_event(&event));
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

fn normalized_market_event_payload(event: &MarketEvent) -> String {
    let payload = match event {
        MarketEvent::DeribitOptionQuote(quote) => serde_json::json!({
            "underlying": &quote.underlying,
            "expiry_ts_ms": quote.expiry_ts_ms,
            "strike": quote.strike,
            "option_kind": format!("{:?}", quote.option_kind),
            "underlying_price": quote.underlying_price,
            "bid": quote.bid,
            "ask": quote.ask,
            "mark_iv": quote.mark_iv,
        }),
        MarketEvent::PolymarketOutcomeQuote(quote) => serde_json::json!({
            "event_slug": &quote.event_slug,
            "market_slug": &quote.market_slug,
            "outcome": &quote.outcome,
            "target_expiry_ts_ms": quote.target_expiry_ts_ms,
            "bid_probability": quote.bid_probability,
            "ask_probability": quote.ask_probability,
            "liquidity_usd": quote.liquidity_usd,
        }),
    };

    payload.to_string()
}

fn parse_payload(row: &EventJournalRow) -> Result<serde_json::Value, JournalError> {
    serde_json::from_str(&row.payload_json).map_err(|error| {
        JournalError::malformed_payload(&row.event_id, format!("invalid JSON: {error}"))
    })
}

fn required_str<'a>(
    row: &EventJournalRow,
    payload: &'a serde_json::Value,
    field: &str,
) -> Result<&'a str, JournalError> {
    payload
        .get(field)
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| JournalError::malformed_payload(&row.event_id, missing_field(field)))
}

fn required_i64(
    row: &EventJournalRow,
    payload: &serde_json::Value,
    field: &str,
) -> Result<i64, JournalError> {
    payload
        .get(field)
        .and_then(serde_json::Value::as_i64)
        .ok_or_else(|| JournalError::malformed_payload(&row.event_id, missing_field(field)))
}

fn required_f64(
    row: &EventJournalRow,
    payload: &serde_json::Value,
    field: &str,
) -> Result<f64, JournalError> {
    payload
        .get(field)
        .and_then(serde_json::Value::as_f64)
        .ok_or_else(|| JournalError::malformed_payload(&row.event_id, missing_field(field)))
}

fn missing_field(field: &str) -> String {
    format!("missing or invalid field: {field}")
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
            underlying_price: 3100.0,
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
            target_expiry_ts_ms: 1_780_000_000_000,
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
        assert_eq!(journal.event_journal_rows().len(), 2);
        assert_eq!(
            journal.event_journal_rows()[0].event_type,
            "raw_deribit_event"
        );
        assert_eq!(
            journal.event_journal_rows()[1].event_type,
            "raw_polymarket_event"
        );

        let error = journal.append_raw_deribit_event(raw_deribit).unwrap_err();
        assert_eq!(error.kind, JournalErrorKind::DuplicateEvent);
        assert_eq!(journal.event_journal_rows().len(), 2);
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
        let row_event_types: Vec<&str> = journal
            .event_journal_rows()
            .iter()
            .map(|row| row.event_type.as_str())
            .collect();
        assert_eq!(
            row_event_types,
            vec!["deribit_option_quote", "polymarket_outcome_quote"]
        );

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

    #[test]
    fn event_journal_row_maps_raw_deribit_event_to_postgres_contract() {
        let raw = RawDeribitEvent {
            meta: meta("raw-deribit-1", "ETH-20260601-3000-C", 2000),
            endpoint_or_channel: "public/ticker".to_string(),
            payload_json: "{\"instrument_name\":\"ETH-20260601-3000-C\"}".to_string(),
        };
        let row = EventJournalRow::from_raw_deribit_event(&raw);

        assert_eq!(PostgresEventJournalAdapter::table_name(), "event_journal");
        assert_eq!(
            PostgresEventJournalAdapter::columns(),
            EventJournalRow::columns()
        );
        assert_eq!(
            row.values(),
            [
                EventJournalRowValue::Text("raw-deribit-1".to_string()),
                EventJournalRowValue::Text("raw_deribit_event".to_string()),
                EventJournalRowValue::Text("mock".to_string()),
                EventJournalRowValue::TimestampMillis(1900),
                EventJournalRowValue::TimestampMillis(2000),
                EventJournalRowValue::Text("ETH-20260601-3000-C".to_string()),
                EventJournalRowValue::Integer(1),
                EventJournalRowValue::Text("test".to_string()),
                EventJournalRowValue::Json(
                    "{\"instrument_name\":\"ETH-20260601-3000-C\"}".to_string()
                ),
            ]
        );
    }

    #[test]
    fn event_journal_row_maps_normalized_market_event_payload_to_json() {
        let event = polymarket_quote("poly-quote-1", 2000);
        let row = EventJournalRow::from_market_event(&event);
        let payload: serde_json::Value =
            serde_json::from_str(&row.payload_json).expect("payload should be JSON");

        assert_eq!(row.event_type, "polymarket_outcome_quote");
        assert_eq!(payload["market_slug"], "eth-above-3000-june-1");
        assert_eq!(payload["target_expiry_ts_ms"], 1_780_000_000_000i64);
    }

    #[test]
    fn postgres_event_journal_adapter_exposes_stable_insert_contract() {
        assert_eq!(
            PostgresEventJournalAdapter::insert_sql(),
            "INSERT INTO event_journal (event_id, event_type, source, exchange_ts, received_ts, instrument_id, schema_version, config_version, payload) VALUES ($1, $2, $3, to_timestamp($4::double precision / 1000.0), to_timestamp($5::double precision / 1000.0), $6, $7, $8, $9::jsonb)"
        );
    }

    #[test]
    fn postgres_event_journal_adapter_exposes_stable_replay_select_contract() {
        assert_eq!(
            PostgresEventJournalAdapter::select_replay_sql(),
            "SELECT event_id, event_type, source, (extract(epoch from exchange_ts) * 1000)::bigint AS exchange_ts_ms, (extract(epoch from received_ts) * 1000)::bigint AS received_ts_ms, instrument_id, schema_version, config_version, payload::text AS payload FROM event_journal WHERE received_ts >= to_timestamp($1::double precision / 1000.0) AND received_ts <= to_timestamp($2::double precision / 1000.0) AND event_type = ANY($3::text[]) AND ($4::text[] IS NULL OR instrument_id = ANY($4::text[])) AND ($5::text IS NULL OR config_version = $5) ORDER BY received_ts ASC, event_id ASC"
        );
    }

    #[test]
    fn replay_query_defaults_to_normalized_event_types() {
        let query = EventJournalReplayQuery::from_filter(ReplayEventFilter {
            start_ts_ms: 0,
            end_ts_ms: 10,
            event_types: vec![],
            instrument_ids: vec![],
            config_version: None,
        });

        assert_eq!(
            query.event_types,
            vec![
                "deribit_option_quote".to_string(),
                "polymarket_outcome_quote".to_string()
            ]
        );
    }

    #[test]
    fn in_memory_event_journal_row_writer_preserves_storage_rows_and_rejects_duplicates() {
        let event = polymarket_quote("poly-quote-1", 2000);
        let row = EventJournalRow::from_market_event(&event);
        let mut writer = InMemoryEventJournalRowWriter::new();

        writer.append_event_journal_row(row.clone()).unwrap();
        assert_eq!(writer.rows(), &[row.clone()]);

        let error = writer.append_event_journal_row(row).unwrap_err();
        assert_eq!(error.kind, JournalErrorKind::DuplicateEvent);
        assert_eq!(writer.rows().len(), 1);
    }

    #[test]
    fn in_memory_event_journal_row_reader_reconstructs_replay_events_from_rows() {
        let raw = RawDeribitEvent {
            meta: meta("raw-deribit-1", "ETH-20260601-3000-C", 1000),
            endpoint_or_channel: "public/ticker".to_string(),
            payload_json: "{}".to_string(),
        };
        let rows = vec![
            EventJournalRow::from_raw_deribit_event(&raw),
            EventJournalRow::from_market_event(&deribit_quote("deribit-quote-2", 2000)),
            EventJournalRow::from_market_event(&polymarket_quote("poly-quote-1", 1500)),
        ];
        let reader = InMemoryEventJournalRowReader::new(rows);

        let events = read_market_events_for_replay_from_rows(
            &reader,
            ReplayEventFilter {
                start_ts_ms: 0,
                end_ts_ms: 3000,
                event_types: vec![],
                instrument_ids: vec![],
                config_version: Some("test".to_string()),
            },
        )
        .expect("row reader should reconstruct normalized events");

        let event_ids: Vec<&str> = events
            .iter()
            .map(|event| event.meta().event_id.as_str())
            .collect();

        assert_eq!(event_ids, vec!["poly-quote-1", "deribit-quote-2"]);
    }

    #[test]
    fn event_journal_row_to_market_event_rejects_malformed_payload() {
        let mut row = EventJournalRow::from_market_event(&deribit_quote("bad-quote", 2000));
        row.payload_json = "{\"underlying\":\"ETH\"}".to_string();

        let error = row
            .to_market_event()
            .expect_err("missing normalized fields should be rejected");

        assert_eq!(error.kind, JournalErrorKind::MalformedPayload);
        assert!(error.message.contains("missing or invalid field"));
    }

    #[cfg(feature = "postgres-writer")]
    #[test]
    fn postgres_event_journal_writer_is_feature_gated_skeleton() {
        let mut writer = PostgresEventJournalWriter::new("phase0-local");
        assert_eq!(writer.connection_label(), "phase0-local");
        assert_eq!(
            writer.insert_sql(),
            PostgresEventJournalAdapter::insert_sql()
        );

        let row = EventJournalRow::from_market_event(&polymarket_quote("poly-quote-1", 2000));
        let error = writer.append_event_journal_row(row).unwrap_err();

        assert_eq!(error.kind, JournalErrorKind::Storage);
        assert!(error.message.contains("Phase 0 skeleton"));
    }
}
