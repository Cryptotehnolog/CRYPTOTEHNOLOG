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

    pub fn from_validation(source: IngestionSource, error: NormalizedBatchValidationError) -> Self {
        Self::new(
            IngestionErrorKind::MalformedPayload,
            Some(source),
            format!(
                "{} validation failed for event {}: {}",
                error.source_name, error.event_id, error.message
            ),
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NormalizedBatchValidationError {
    pub source_name: String,
    pub event_id: String,
    pub message: String,
}

impl NormalizedBatchValidationError {
    pub fn new(
        source_name: impl Into<String>,
        event_id: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self {
            source_name: source_name.into(),
            event_id: event_id.into(),
            message: message.into(),
        }
    }
}

pub trait NormalizedBatchValidator {
    fn validate_market_event(
        &self,
        event: &MarketEvent,
    ) -> Result<(), NormalizedBatchValidationError>;

    fn validate_batch(&self, batch: &IngestionBatch) -> Result<(), NormalizedBatchValidationError> {
        for event in &batch.market_events {
            self.validate_market_event(event)?;
        }
        Ok(())
    }

    fn validation_report(&self, batch: &IngestionBatch) -> ValidationReport {
        let mut report = ValidationReport::new(batch.raw_events.len(), batch.market_events.len());

        for event in &batch.market_events {
            match self.validate_market_event(event) {
                Ok(()) => report.normalized_events_accepted += 1,
                Err(error) => report.rejections.push(error),
            }
        }

        report.normalized_events_rejected = report.rejections.len();
        report
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationReport {
    pub raw_events_received: usize,
    pub normalized_events_received: usize,
    pub normalized_events_accepted: usize,
    pub normalized_events_rejected: usize,
    pub rejections: Vec<NormalizedBatchValidationError>,
}

impl ValidationReport {
    pub fn new(raw_events_received: usize, normalized_events_received: usize) -> Self {
        Self {
            raw_events_received,
            normalized_events_received,
            normalized_events_accepted: 0,
            normalized_events_rejected: 0,
            rejections: Vec::new(),
        }
    }

    pub fn is_clean(&self) -> bool {
        self.normalized_events_rejected == 0
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct IngestionOutcome {
    pub batch: IngestionBatch,
    pub validation_report: ValidationReport,
}

#[derive(Debug, Clone, Default)]
pub struct AcceptAllNormalizedBatchValidator;

impl NormalizedBatchValidator for AcceptAllNormalizedBatchValidator {
    fn validate_market_event(
        &self,
        _event: &MarketEvent,
    ) -> Result<(), NormalizedBatchValidationError> {
        Ok(())
    }
}

#[derive(Debug, Clone, Default)]
pub struct Phase0NormalizedBatchValidator;

impl NormalizedBatchValidator for Phase0NormalizedBatchValidator {
    fn validate_market_event(
        &self,
        event: &MarketEvent,
    ) -> Result<(), NormalizedBatchValidationError> {
        match event {
            MarketEvent::DeribitOptionQuote(quote) => {
                if quote.meta.event_id.trim().is_empty()
                    || quote.meta.instrument_id.trim().is_empty()
                    || quote.underlying.trim().is_empty()
                {
                    return Err(validation_error(
                        event,
                        "missing required Deribit identity field",
                    ));
                }
                if !quote.bid.is_finite()
                    || !quote.ask.is_finite()
                    || !quote.mark_iv.is_finite()
                    || !quote.underlying_price.is_finite()
                    || quote.bid < 0.0
                    || quote.bid > quote.ask
                    || quote.strike <= 0.0
                    || quote.mark_iv <= 0.0
                    || quote.underlying_price <= 0.0
                {
                    return Err(validation_error(
                        event,
                        "invalid Deribit normalized quote values",
                    ));
                }
                if quote.expiry_ts_ms <= quote.meta.exchange_ts_ms {
                    return Err(validation_error(
                        event,
                        "Deribit option is expired at event timestamp",
                    ));
                }
            }
            MarketEvent::PolymarketOutcomeQuote(quote) => {
                if quote.meta.event_id.trim().is_empty()
                    || quote.meta.instrument_id.trim().is_empty()
                    || quote.event_slug.trim().is_empty()
                    || quote.market_slug.trim().is_empty()
                    || quote.outcome.trim().is_empty()
                {
                    return Err(validation_error(
                        event,
                        "missing required Polymarket identity field",
                    ));
                }
                if !quote.bid_probability.is_finite()
                    || !quote.ask_probability.is_finite()
                    || !quote.liquidity_usd.is_finite()
                    || quote.bid_probability < 0.0
                    || quote.ask_probability > 1.0
                    || quote.bid_probability > quote.ask_probability
                    || quote.liquidity_usd < 0.0
                {
                    return Err(validation_error(
                        event,
                        "invalid Polymarket normalized quote values",
                    ));
                }
            }
        }

        Ok(())
    }
}

fn validation_error(
    event: &MarketEvent,
    message: impl Into<String>,
) -> NormalizedBatchValidationError {
    NormalizedBatchValidationError::new(
        event.meta().source.clone(),
        event.meta().event_id.clone(),
        message,
    )
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
    ingest_once_with_validator(client, journal, config, &AcceptAllNormalizedBatchValidator)
}

pub fn ingest_once_with_validator<C, J, V>(
    client: &mut C,
    journal: &mut J,
    config: &IngestionConfig,
    validator: &V,
) -> Result<IngestionBatch, IngestionError>
where
    C: IngestionClient,
    J: EventJournal,
    V: NormalizedBatchValidator,
{
    let batch = client.poll_once(config)?;

    write_raw_events(journal, &batch)?;

    validator
        .validate_batch(&batch)
        .map_err(|error| IngestionError::from_validation(batch.source, error))?;

    write_normalized_events(journal, &batch, &batch.market_events)?;

    Ok(batch)
}

pub fn ingest_once_with_report<C, J, V>(
    client: &mut C,
    journal: &mut J,
    config: &IngestionConfig,
    validator: &V,
) -> Result<IngestionOutcome, IngestionError>
where
    C: IngestionClient,
    J: EventJournal,
    V: NormalizedBatchValidator,
{
    let batch = client.poll_once(config)?;

    write_raw_events(journal, &batch)?;

    let validation_report = validator.validation_report(&batch);
    let accepted_events: Vec<MarketEvent> = batch
        .market_events
        .iter()
        .filter(|event| {
            !validation_report
                .rejections
                .iter()
                .any(|rejection| rejection.event_id == event.meta().event_id)
        })
        .cloned()
        .collect();

    write_normalized_events(journal, &batch, &accepted_events)?;

    Ok(IngestionOutcome {
        batch,
        validation_report,
    })
}

fn write_raw_events<J>(journal: &mut J, batch: &IngestionBatch) -> Result<(), IngestionError>
where
    J: EventJournal,
{
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

    Ok(())
}

fn write_normalized_events<J>(
    journal: &mut J,
    batch: &IngestionBatch,
    market_events: &[MarketEvent],
) -> Result<(), IngestionError>
where
    J: EventJournal,
{
    for market_event in market_events {
        journal
            .append_market_event(market_event.clone())
            .map_err(|error| IngestionError::from_journal(batch.source, error))?;
    }

    Ok(())
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
    MalformedBatch,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IngestionManifestScenario {
    pub name: String,
    pub fixture: String,
    pub expected_observations: usize,
    pub expected_raw_events: usize,
    pub expected_normalized_events: usize,
    pub expected_validation_errors: usize,
}

pub fn load_ingestion_scenario(path: &Path) -> Result<Vec<IngestionScenarioStep>, String> {
    let content = fs::read_to_string(path)
        .map_err(|error| format!("cannot read ingestion scenario {}: {error}", path.display()))?;
    parse_ingestion_scenario(&content)
}

pub fn load_ingestion_manifest(path: &Path) -> Result<Vec<IngestionManifestScenario>, String> {
    let content = fs::read_to_string(path)
        .map_err(|error| format!("cannot read ingestion manifest {}: {error}", path.display()))?;
    parse_ingestion_manifest(&content)
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
        "malformed_batch" => Ok(IngestionScenarioOutcome::MalformedBatch),
        other => Err(format!("line {line_number}: unsupported outcome `{other}`")),
    }
}

pub fn parse_ingestion_manifest(content: &str) -> Result<Vec<IngestionManifestScenario>, String> {
    let mut scenarios = Vec::new();
    let mut current_name: Option<String> = None;
    let mut current_fixture: Option<String> = None;
    let mut current_expected_observations: Option<usize> = None;
    let mut current_expected_raw_events: Option<usize> = None;
    let mut current_expected_normalized_events: Option<usize> = None;
    let mut current_expected_validation_errors: Option<usize> = None;

    for (index, line) in content.lines().enumerate() {
        let line_number = index + 1;
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }

        if trimmed == "[[scenario]]" {
            push_manifest_scenario(
                &mut scenarios,
                &mut current_name,
                &mut current_fixture,
                &mut current_expected_observations,
                &mut current_expected_raw_events,
                &mut current_expected_normalized_events,
                &mut current_expected_validation_errors,
                line_number,
            )?;
            continue;
        }

        let Some((key, value)) = trimmed.split_once('=') else {
            return Err(format!("line {line_number}: expected key = value"));
        };
        let key = key.trim();
        let value = value.trim().trim_matches('"');

        match key {
            "name" => current_name = Some(value.to_string()),
            "fixture" => current_fixture = Some(value.to_string()),
            "expected_observations" => {
                current_expected_observations = Some(value.parse::<usize>().map_err(|error| {
                    format!("line {line_number}: invalid expected_observations: {error}")
                })?)
            }
            "expected_raw_events" => {
                current_expected_raw_events = Some(value.parse::<usize>().map_err(|error| {
                    format!("line {line_number}: invalid expected_raw_events: {error}")
                })?)
            }
            "expected_normalized_events" => {
                current_expected_normalized_events =
                    Some(value.parse::<usize>().map_err(|error| {
                        format!("line {line_number}: invalid expected_normalized_events: {error}")
                    })?)
            }
            "expected_validation_errors" => {
                current_expected_validation_errors =
                    Some(value.parse::<usize>().map_err(|error| {
                        format!("line {line_number}: invalid expected_validation_errors: {error}")
                    })?)
            }
            other => {
                return Err(format!(
                    "line {line_number}: unsupported manifest key `{other}`"
                ));
            }
        }
    }

    push_manifest_scenario(
        &mut scenarios,
        &mut current_name,
        &mut current_fixture,
        &mut current_expected_observations,
        &mut current_expected_raw_events,
        &mut current_expected_normalized_events,
        &mut current_expected_validation_errors,
        content.lines().count() + 1,
    )?;

    if scenarios.is_empty() {
        return Err("ingestion manifest contains no scenarios".to_string());
    }

    for index in 0..scenarios.len() {
        let scenario = &scenarios[index];
        if scenarios[..index]
            .iter()
            .any(|candidate| candidate.name == scenario.name)
        {
            return Err(format!(
                "duplicate ingestion scenario name: {}",
                scenario.name
            ));
        }
        if scenarios[..index]
            .iter()
            .any(|candidate| candidate.fixture == scenario.fixture)
        {
            return Err(format!(
                "duplicate ingestion scenario fixture: {}",
                scenario.fixture
            ));
        }
    }

    Ok(scenarios)
}

fn push_manifest_scenario(
    scenarios: &mut Vec<IngestionManifestScenario>,
    current_name: &mut Option<String>,
    current_fixture: &mut Option<String>,
    current_expected_observations: &mut Option<usize>,
    current_expected_raw_events: &mut Option<usize>,
    current_expected_normalized_events: &mut Option<usize>,
    current_expected_validation_errors: &mut Option<usize>,
    line_number: usize,
) -> Result<(), String> {
    if current_name.is_none()
        && current_fixture.is_none()
        && current_expected_observations.is_none()
        && current_expected_raw_events.is_none()
        && current_expected_normalized_events.is_none()
        && current_expected_validation_errors.is_none()
    {
        return Ok(());
    }

    let name = current_name
        .take()
        .ok_or_else(|| format!("line {line_number}: manifest scenario missing name"))?;
    let fixture = current_fixture
        .take()
        .ok_or_else(|| format!("line {line_number}: manifest scenario missing fixture"))?;
    let expected_observations = current_expected_observations.take().ok_or_else(|| {
        format!("line {line_number}: manifest scenario missing expected_observations")
    })?;
    let expected_raw_events = current_expected_raw_events.take().ok_or_else(|| {
        format!("line {line_number}: manifest scenario missing expected_raw_events")
    })?;
    let expected_normalized_events =
        current_expected_normalized_events.take().ok_or_else(|| {
            format!("line {line_number}: manifest scenario missing expected_normalized_events")
        })?;
    let expected_validation_errors =
        current_expected_validation_errors.take().ok_or_else(|| {
            format!("line {line_number}: manifest scenario missing expected_validation_errors")
        })?;

    scenarios.push(IngestionManifestScenario {
        name,
        fixture,
        expected_observations,
        expected_raw_events,
        expected_normalized_events,
        expected_validation_errors,
    });
    Ok(())
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

    fn malformed_polymarket_batch() -> IngestionBatch {
        IngestionBatch {
            source: IngestionSource::Polymarket,
            raw_events: vec![RawIngestionEvent::Polymarket(RawPolymarketEvent {
                meta: polymarket_meta("raw-polymarket-malformed-1"),
                api_layer: PolymarketApiLayer::Gamma,
                payload_json:
                    "{\"market_slug\":\"eth-above-3000-june-1\",\"bid\":0.70,\"ask\":0.60}"
                        .to_string(),
            })],
            market_events: vec![MarketEvent::PolymarketOutcomeQuote(
                PolymarketOutcomeQuote {
                    meta: polymarket_meta("market-polymarket-malformed-1"),
                    event_slug: "eth-above-3000".to_string(),
                    market_slug: "eth-above-3000-june-1".to_string(),
                    outcome: "Yes".to_string(),
                    bid_probability: 0.70,
                    ask_probability: 0.60,
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

        let deribit_outcome = ingest_once_with_report(
            &mut deribit_client,
            &mut journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("deribit batch should ingest");
        let polymarket_outcome = ingest_once_with_report(
            &mut polymarket_client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("polymarket batch should ingest");

        assert_eq!(deribit_outcome.validation_report.raw_events_received, 1);
        assert_eq!(
            deribit_outcome.validation_report.normalized_events_accepted,
            1
        );
        assert!(deribit_outcome.validation_report.is_clean());
        assert_eq!(polymarket_outcome.validation_report.raw_events_received, 1);
        assert_eq!(
            polymarket_outcome
                .validation_report
                .normalized_events_accepted,
            1
        );
        assert!(polymarket_outcome.validation_report.is_clean());

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
    fn malformed_polymarket_batch_preserves_raw_event_without_basis_observation() {
        let fixture_path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("fixtures")
            .join("ingestion")
            .join("malformed_polymarket_quote.psv");
        let scenario =
            load_ingestion_scenario(&fixture_path).expect("malformed fixture should parse");
        assert_eq!(scenario.len(), 2);
        assert_eq!(scenario[0].source, IngestionSource::Deribit);
        assert_eq!(scenario[0].outcome, IngestionScenarioOutcome::Batch);
        assert_eq!(scenario[1].source, IngestionSource::Polymarket);
        assert_eq!(
            scenario[1].outcome,
            IngestionScenarioOutcome::MalformedBatch
        );

        let mut deribit_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut polymarket_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(malformed_polymarket_batch())]);
        let mut journal = InMemoryEventJournal::new();

        ingest_once(
            &mut deribit_client,
            &mut journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
        )
        .expect("deribit batch should ingest");
        let outcome = ingest_once_with_report(
            &mut polymarket_client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("malformed normalized quote should still return a validation report");

        assert_eq!(outcome.validation_report.raw_events_received, 1);
        assert_eq!(outcome.validation_report.normalized_events_received, 1);
        assert_eq!(outcome.validation_report.normalized_events_accepted, 0);
        assert_eq!(outcome.validation_report.normalized_events_rejected, 1);
        assert!(!outcome.validation_report.is_clean());
        assert_eq!(
            outcome.validation_report.rejections[0].event_id,
            "market-polymarket-malformed-1"
        );

        assert_eq!(journal.raw_polymarket_events().len(), 1);
        assert_eq!(
            journal.raw_polymarket_events()[0].meta.event_id,
            "raw-polymarket-malformed-1"
        );
        assert_eq!(journal.market_events().len(), 1);

        let replay_events = journal
            .read_events_for_replay(ReplayEventFilter {
                start_ts_ms: 0,
                end_ts_ms: 1_781_000_000_000,
                event_types: vec![],
                instrument_ids: vec![],
                config_version: Some("phase0-ingestion".to_string()),
            })
            .expect("journal should return replay events");
        let config = probability_basis_config();
        let decisions = match_from_market_events(&replay_events, &config);

        assert_eq!(
            decisions,
            vec![MatchDecision::Rejected {
                reason: cryptotehnolog_common::probability_basis::RejectionReason::MissingPolymarketQuote,
                deribit_instrument_id: Some("ETH-20260601-3000-C".to_string()),
                polymarket_market_slug: None,
            }]
        );
        let observations = observations_from_match_decisions(&decisions, &config);
        assert!(observations.is_empty());
    }

    #[test]
    fn strict_validator_returns_error_after_preserving_raw_event() {
        let mut client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(malformed_polymarket_batch())]);
        let mut journal = InMemoryEventJournal::new();

        let error = ingest_once_with_validator(
            &mut client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect_err("strict validator should return malformed payload error");

        assert_eq!(error.kind, IngestionErrorKind::MalformedPayload);
        assert!(error.message.contains("market-polymarket-malformed-1"));
        assert_eq!(journal.raw_polymarket_events().len(), 1);
        assert!(journal.market_events().is_empty());
    }

    #[test]
    fn phase0_validator_accepts_valid_batch_before_normalized_write() {
        let mut client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(polymarket_batch())]);
        let mut journal = InMemoryEventJournal::new();

        ingest_once_with_validator(
            &mut client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("valid Polymarket batch should pass validator");

        assert_eq!(journal.raw_polymarket_events().len(), 1);
        assert_eq!(journal.market_events().len(), 1);
    }

    #[test]
    fn ingestion_manifest_lists_current_orchestration_scenarios() {
        let manifest_path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("fixtures")
            .join("ingestion")
            .join("manifest.toml");

        let scenarios =
            load_ingestion_manifest(&manifest_path).expect("ingestion manifest should parse");

        assert_eq!(scenarios.len(), 2);
        assert_eq!(scenarios[0].name, "happy_path_batches");
        assert_eq!(scenarios[0].expected_observations, 1);
        assert_eq!(scenarios[0].expected_raw_events, 2);
        assert_eq!(scenarios[0].expected_normalized_events, 2);
        assert_eq!(scenarios[0].expected_validation_errors, 0);
        assert_eq!(scenarios[1].name, "malformed_polymarket_quote");
        assert_eq!(scenarios[1].expected_observations, 0);
        assert_eq!(scenarios[1].expected_raw_events, 2);
        assert_eq!(scenarios[1].expected_normalized_events, 1);
        assert_eq!(scenarios[1].expected_validation_errors, 1);
    }

    #[test]
    fn ingestion_manifest_rejects_duplicate_names_and_fixtures() {
        let duplicate_name = r#"
[[scenario]]
name = "same"
fixture = "fixtures/ingestion/a.psv"
expected_observations = 1
expected_raw_events = 1
expected_normalized_events = 1
expected_validation_errors = 0

[[scenario]]
name = "same"
fixture = "fixtures/ingestion/b.psv"
expected_observations = 0
expected_raw_events = 1
expected_normalized_events = 0
expected_validation_errors = 1
"#;
        assert!(
            parse_ingestion_manifest(duplicate_name)
                .unwrap_err()
                .contains("duplicate ingestion scenario name")
        );

        let duplicate_fixture = r#"
[[scenario]]
name = "a"
fixture = "fixtures/ingestion/same.psv"
expected_observations = 1
expected_raw_events = 1
expected_normalized_events = 1
expected_validation_errors = 0

[[scenario]]
name = "b"
fixture = "fixtures/ingestion/same.psv"
expected_observations = 0
expected_raw_events = 1
expected_normalized_events = 0
expected_validation_errors = 1
"#;
        assert!(
            parse_ingestion_manifest(duplicate_fixture)
                .unwrap_err()
                .contains("duplicate ingestion scenario fixture")
        );
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
