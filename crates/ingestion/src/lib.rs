use std::fs;
use std::path::Path;

use cryptotehnolog_common::events::{MarketEvent, RawDeribitEvent, RawPolymarketEvent};
use cryptotehnolog_common::journal::{EventJournal, JournalError};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IngestionSource {
    Deribit,
    Polymarket,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IngestionConfig {
    pub source: IngestionSource,
    pub endpoint: String,
    pub reconnect_backoff_ms: u64,
    pub request_timeout_ms: u64,
    pub max_batch_size: usize,
    pub config_version: String,
}

impl IngestionConfig {
    pub fn phase0_deribit(endpoint: impl Into<String>) -> Self {
        Self {
            source: IngestionSource::Deribit,
            endpoint: endpoint.into(),
            reconnect_backoff_ms: 1_000,
            request_timeout_ms: 5_000,
            max_batch_size: 100,
            config_version: "phase0-ingestion".to_string(),
        }
    }

    pub fn phase0_polymarket(endpoint: impl Into<String>) -> Self {
        Self {
            source: IngestionSource::Polymarket,
            endpoint: endpoint.into(),
            reconnect_backoff_ms: 1_000,
            request_timeout_ms: 5_000,
            max_batch_size: 100,
            config_version: "phase0-ingestion".to_string(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IngestionErrorKind {
    Api,
    ReconnectRequired,
    RateLimit,
    MalformedPayload,
    JournalWrite,
    Unsupported,
    NotImplemented,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IngestionError {
    pub kind: IngestionErrorKind,
    pub source: Option<IngestionSource>,
    pub message: String,
}

impl IngestionError {
    pub fn new(
        kind: IngestionErrorKind,
        source: Option<IngestionSource>,
        message: impl Into<String>,
    ) -> Self {
        Self {
            kind,
            source,
            message: message.into(),
        }
    }

    pub fn from_journal(source: IngestionSource, error: JournalError) -> Self {
        Self::new(
            IngestionErrorKind::JournalWrite,
            Some(source),
            format!("{:?}: {}", error.kind, error.message),
        )
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum RawIngestionEvent {
    Deribit(RawDeribitEvent),
    Polymarket(RawPolymarketEvent),
}

impl RawIngestionEvent {
    pub fn source(&self) -> IngestionSource {
        match self {
            RawIngestionEvent::Deribit(_) => IngestionSource::Deribit,
            RawIngestionEvent::Polymarket(_) => IngestionSource::Polymarket,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct IngestionBatch {
    pub source: IngestionSource,
    pub raw_events: Vec<RawIngestionEvent>,
    pub market_events: Vec<MarketEvent>,
}

impl IngestionBatch {
    pub fn empty(source: IngestionSource) -> Self {
        Self {
            source,
            raw_events: Vec::new(),
            market_events: Vec::new(),
        }
    }
}

pub trait IngestionClient {
    fn poll_once(&mut self, config: &IngestionConfig) -> Result<IngestionBatch, IngestionError>;
}

#[derive(Debug, Clone, PartialEq)]
pub enum MockIngestionStep {
    Batch(IngestionBatch),
    Error(IngestionError),
}

#[derive(Debug, Clone)]
pub struct MockIngestionClient {
    steps: Vec<MockIngestionStep>,
    next_step: usize,
}

impl MockIngestionClient {
    pub fn new(steps: Vec<MockIngestionStep>) -> Self {
        Self {
            steps,
            next_step: 0,
        }
    }
}

impl IngestionClient for MockIngestionClient {
    fn poll_once(&mut self, config: &IngestionConfig) -> Result<IngestionBatch, IngestionError> {
        let Some(step) = self.steps.get(self.next_step).cloned() else {
            return Ok(IngestionBatch::empty(config.source));
        };
        self.next_step += 1;

        match step {
            MockIngestionStep::Batch(batch) => Ok(batch),
            MockIngestionStep::Error(error) => Err(error),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct LiveIngestionClient;

impl IngestionClient for LiveIngestionClient {
    fn poll_once(&mut self, config: &IngestionConfig) -> Result<IngestionBatch, IngestionError> {
        Err(IngestionError::new(
            IngestionErrorKind::NotImplemented,
            Some(config.source),
            "live ingestion client is a Phase 0 skeleton; no network calls are implemented",
        ))
    }
}

pub fn ingest_once<C, J>(
    client: &mut C,
    journal: &mut J,
    config: &IngestionConfig,
) -> Result<IngestionBatch, IngestionError>
where
    C: IngestionClient,
    J: EventJournal,
{
    let batch = client.poll_once(config)?;

    for raw_event in &batch.raw_events {
        match raw_event {
            RawIngestionEvent::Deribit(event) => journal
                .append_raw_deribit_event(event.clone())
                .map_err(|error| IngestionError::from_journal(raw_event.source(), error))?,
            RawIngestionEvent::Polymarket(event) => journal
                .append_raw_polymarket_event(event.clone())
                .map_err(|error| IngestionError::from_journal(raw_event.source(), error))?,
        }
    }

    for market_event in &batch.market_events {
        journal
            .append_market_event(market_event.clone())
            .map_err(|error| IngestionError::from_journal(batch.source, error))?;
    }

    Ok(batch)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IngestionScenarioStep {
    pub step: u32,
    pub source: IngestionSource,
    pub outcome: IngestionScenarioOutcome,
    pub message: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IngestionScenarioOutcome {
    ApiError,
    Reconnect,
    Batch,
}

pub fn load_ingestion_scenario(path: &Path) -> Result<Vec<IngestionScenarioStep>, String> {
    let content = fs::read_to_string(path)
        .map_err(|error| format!("cannot read ingestion scenario {}: {error}", path.display()))?;
    parse_ingestion_scenario(&content)
}

pub fn parse_ingestion_scenario(content: &str) -> Result<Vec<IngestionScenarioStep>, String> {
    let mut steps = Vec::new();

    for (index, line) in content.lines().enumerate() {
        let line_number = index + 1;
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }

        let fields: Vec<&str> = trimmed.split('|').collect();
        if fields.len() != 4 {
            return Err(format!(
                "line {line_number}: expected 4 pipe-separated fields, got {}",
                fields.len()
            ));
        }

        steps.push(IngestionScenarioStep {
            step: fields[0]
                .parse::<u32>()
                .map_err(|error| format!("line {line_number}: invalid step: {error}"))?,
            source: parse_source(line_number, fields[1])?,
            outcome: parse_outcome(line_number, fields[2])?,
            message: fields[3].trim().to_string(),
        });
    }

    if steps.is_empty() {
        return Err("ingestion scenario contains no steps".to_string());
    }

    Ok(steps)
}

fn parse_source(line_number: usize, raw: &str) -> Result<IngestionSource, String> {
    match raw.trim() {
        "deribit" => Ok(IngestionSource::Deribit),
        "polymarket" => Ok(IngestionSource::Polymarket),
        other => Err(format!("line {line_number}: unsupported source `{other}`")),
    }
}

fn parse_outcome(line_number: usize, raw: &str) -> Result<IngestionScenarioOutcome, String> {
    match raw.trim() {
        "api_error" => Ok(IngestionScenarioOutcome::ApiError),
        "reconnect" => Ok(IngestionScenarioOutcome::Reconnect),
        "batch" => Ok(IngestionScenarioOutcome::Batch),
        other => Err(format!("line {line_number}: unsupported outcome `{other}`")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cryptotehnolog_common::events::{
        DeribitOptionQuote, EventMeta, OptionKind, PolymarketApiLayer, PolymarketOutcomeQuote,
        RawDeribitEvent, RawPolymarketEvent, ReplayEventFilter,
    };
    use cryptotehnolog_common::journal::InMemoryEventJournal;
    use cryptotehnolog_common::observations::{
        BasisObservationWriter, InMemoryBasisObservationWriter, observations_from_match_decisions,
    };
    use cryptotehnolog_common::probability_basis::{
        MatchDecision, ProbabilityBasisConfig, match_from_market_events,
    };

    fn meta(event_id: &str) -> EventMeta {
        EventMeta {
            event_id: event_id.to_string(),
            source: "mock-ingestion".to_string(),
            exchange_ts_ms: 1_779_200_000_000,
            received_ts_ms: 1_779_200_000_100,
            instrument_id: "ETH-20260601-3000-C".to_string(),
            schema_version: 1,
            config_version: "phase0-ingestion".to_string(),
        }
    }

    fn deribit_batch() -> IngestionBatch {
        IngestionBatch {
            source: IngestionSource::Deribit,
            raw_events: vec![RawIngestionEvent::Deribit(RawDeribitEvent {
                meta: meta("raw-deribit-1"),
                endpoint_or_channel: "public/ticker".to_string(),
                payload_json: "{\"instrument_name\":\"ETH-20260601-3000-C\"}".to_string(),
            })],
            market_events: vec![MarketEvent::DeribitOptionQuote(DeribitOptionQuote {
                meta: meta("market-deribit-1"),
                underlying: "ETH".to_string(),
                expiry_ts_ms: 1_780_000_000_000,
                strike: 3000.0,
                option_kind: OptionKind::Call,
                underlying_price: 3100.0,
                bid: 0.12,
                ask: 0.13,
                mark_iv: 0.62,
            })],
        }
    }

    fn polymarket_meta(event_id: &str) -> EventMeta {
        EventMeta {
            event_id: event_id.to_string(),
            source: "mock-ingestion".to_string(),
            exchange_ts_ms: 1_780_000_000_000,
            received_ts_ms: 1_780_000_000_100,
            instrument_id: "eth-above-3000-june-1".to_string(),
            schema_version: 1,
            config_version: "phase0-ingestion".to_string(),
        }
    }

    fn polymarket_batch() -> IngestionBatch {
        IngestionBatch {
            source: IngestionSource::Polymarket,
            raw_events: vec![RawIngestionEvent::Polymarket(RawPolymarketEvent {
                meta: polymarket_meta("raw-polymarket-1"),
                api_layer: PolymarketApiLayer::Gamma,
                payload_json: "{\"market_slug\":\"eth-above-3000-june-1\"}".to_string(),
            })],
            market_events: vec![MarketEvent::PolymarketOutcomeQuote(
                PolymarketOutcomeQuote {
                    meta: polymarket_meta("market-polymarket-1"),
                    event_slug: "eth-above-3000".to_string(),
                    market_slug: "eth-above-3000-june-1".to_string(),
                    outcome: "Yes".to_string(),
                    bid_probability: 0.51,
                    ask_probability: 0.53,
                    liquidity_usd: 10_000.0,
                },
            )],
        }
    }

    fn probability_basis_config() -> ProbabilityBasisConfig {
        ProbabilityBasisConfig {
            min_net_edge_probability: 0.025,
            max_expiry_mismatch_ms: 86_400_000,
            min_polymarket_liquidity_usd: 1_000.0,
            estimated_cost_probability: 0.010,
        }
    }

    #[test]
    fn ingest_once_writes_raw_events_before_normalized_events() {
        let mut client = MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut journal = InMemoryEventJournal::new();

        let batch = ingest_once(
            &mut client,
            &mut journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
        )
        .expect("mock ingestion should succeed");

        assert_eq!(batch.raw_events.len(), 1);
        assert_eq!(batch.market_events.len(), 1);
        assert_eq!(journal.raw_deribit_events().len(), 1);
        assert_eq!(journal.market_events().len(), 1);
        assert_eq!(
            journal.raw_deribit_events()[0].meta.event_id,
            "raw-deribit-1"
        );
        assert_eq!(
            journal.market_events()[0].meta().event_id,
            "market-deribit-1"
        );
    }

    #[test]
    fn mock_ingestion_surfaces_api_error_without_writing_events() {
        let mut client =
            MockIngestionClient::new(vec![MockIngestionStep::Error(IngestionError::new(
                IngestionErrorKind::Api,
                Some(IngestionSource::Deribit),
                "temporary 502",
            ))]);
        let mut journal = InMemoryEventJournal::new();

        let error = ingest_once(
            &mut client,
            &mut journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
        )
        .expect_err("api error should be returned");

        assert_eq!(error.kind, IngestionErrorKind::Api);
        assert!(journal.raw_deribit_events().is_empty());
        assert!(journal.market_events().is_empty());
    }

    #[test]
    fn api_error_reconnect_fixture_documents_recovery_sequence() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("fixtures")
            .join("ingestion")
            .join("api_error_reconnect_sequence.psv");

        let scenario = load_ingestion_scenario(&path).expect("scenario fixture should parse");

        assert_eq!(scenario.len(), 3);
        assert_eq!(scenario[0].outcome, IngestionScenarioOutcome::ApiError);
        assert_eq!(scenario[1].outcome, IngestionScenarioOutcome::Reconnect);
        assert_eq!(scenario[2].outcome, IngestionScenarioOutcome::Batch);
    }

    #[test]
    fn happy_path_batches_flow_from_ingestion_to_basis_observation() {
        let fixture_path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("fixtures")
            .join("ingestion")
            .join("happy_path_batches.psv");
        let scenario =
            load_ingestion_scenario(&fixture_path).expect("happy path fixture should parse");
        assert_eq!(scenario.len(), 2);
        assert_eq!(scenario[0].source, IngestionSource::Deribit);
        assert_eq!(scenario[0].outcome, IngestionScenarioOutcome::Batch);
        assert_eq!(scenario[1].source, IngestionSource::Polymarket);
        assert_eq!(scenario[1].outcome, IngestionScenarioOutcome::Batch);

        let mut deribit_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut polymarket_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(polymarket_batch())]);
        let mut journal = InMemoryEventJournal::new();

        ingest_once(
            &mut deribit_client,
            &mut journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
        )
        .expect("deribit batch should ingest");
        ingest_once(
            &mut polymarket_client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
        )
        .expect("polymarket batch should ingest");

        assert_eq!(journal.raw_deribit_events().len(), 1);
        assert_eq!(journal.raw_polymarket_events().len(), 1);

        let replay_events = journal
            .read_events_for_replay(ReplayEventFilter {
                start_ts_ms: 0,
                end_ts_ms: 1_781_000_000_000,
                event_types: vec![],
                instrument_ids: vec![],
                config_version: Some("phase0-ingestion".to_string()),
            })
            .expect("journal should return replay events");
        assert_eq!(replay_events.len(), 2);

        let config = probability_basis_config();
        let decisions = match_from_market_events(&replay_events, &config);
        assert_eq!(decisions.len(), 1);
        match &decisions[0] {
            MatchDecision::Matched {
                feature,
                net_edge_probability,
                survives_costs,
            } => {
                assert_eq!(feature.deribit_instrument_id, "ETH-20260601-3000-C");
                assert_eq!(feature.polymarket_market_slug, "eth-above-3000-june-1");
                assert!((*net_edge_probability - 0.081338).abs() < 1e-6);
                assert!(*survives_costs);
            }
            MatchDecision::Rejected { reason, .. } => {
                panic!("expected matched decision, got {reason:?}");
            }
        }

        let observations = observations_from_match_decisions(&decisions, &config);
        assert_eq!(observations.len(), 1);
        let mut writer = InMemoryBasisObservationWriter::new();
        writer
            .append_basis_observation(observations[0].clone())
            .expect("basis observation should append");

        let observation = &writer.observations()[0];
        assert_eq!(
            observation.event_id,
            "probability-basis:market-deribit-1:market-polymarket-1"
        );
        assert!(observation.survives_costs);
        assert!((observation.net_edge_probability - 0.081338).abs() < 1e-6);
    }

    #[test]
    fn live_ingestion_client_is_explicitly_not_implemented() {
        let mut client = LiveIngestionClient;
        let error = client
            .poll_once(&IngestionConfig::phase0_polymarket(
                "https://example.invalid",
            ))
            .expect_err("live client must not perform network calls in skeleton");

        assert_eq!(error.kind, IngestionErrorKind::NotImplemented);
    }

    #[test]
    fn raw_polymarket_event_variant_preserves_source() {
        let raw = RawIngestionEvent::Polymarket(RawPolymarketEvent {
            meta: EventMeta {
                instrument_id: "eth-above-3000".to_string(),
                ..meta("raw-polymarket-1")
            },
            api_layer: PolymarketApiLayer::Gamma,
            payload_json: "{}".to_string(),
        });

        assert_eq!(raw.source(), IngestionSource::Polymarket);
    }
}
