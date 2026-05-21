use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use cryptotehnolog_common::events::{
    DeribitOptionQuote, EventMeta, MarketEvent, OptionKind, PolymarketApiLayer,
    PolymarketOutcomeQuote, RawDeribitEvent, RawPolymarketEvent,
};
use cryptotehnolog_common::journal::{
    EventJournal, EventJournalRow, EventJournalRowWriter, JournalError,
};
use cryptotehnolog_common::observations::{
    BasisObservationRow, BasisObservationRowWriter, InMemoryBasisObservationRowWriter,
    ObservationWriteError, ObservationWriteErrorKind, observations_from_match_decisions,
    write_basis_observation_rows,
};
use cryptotehnolog_common::probability_basis::{ProbabilityBasisConfig, match_from_market_events};
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const DERIBIT_INSTRUMENTS_PAYLOAD_SHAPE_VERSION: &str = "deribit_get_instruments_v1";
pub const DERIBIT_TICKER_PAYLOAD_SHAPE_VERSION: &str = "deribit_json_rpc_ticker_v1";
pub const POLYMARKET_GAMMA_MARKETS_PAYLOAD_SHAPE_VERSION: &str = "polymarket_gamma_markets_v1";
pub const POLYMARKET_GAMMA_MARKET_PAYLOAD_SHAPE_VERSION: &str = "polymarket_gamma_market_v1";
pub const POLYMARKET_CLOB_BOOK_PAYLOAD_SHAPE_VERSION: &str = "polymarket_clob_book_v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IngestionSource {
    Deribit,
    Polymarket,
}

impl IngestionSource {
    pub fn as_str(self) -> &'static str {
        match self {
            IngestionSource::Deribit => "Deribit",
            IngestionSource::Polymarket => "Polymarket",
        }
    }
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

pub trait LiveHttpTransport {
    fn get(&self, url: &str) -> Result<String, IngestionError>;
}

#[derive(Debug, Clone, Default)]
pub struct DisabledHttpTransport;

impl LiveHttpTransport for DisabledHttpTransport {
    fn get(&self, url: &str) -> Result<String, IngestionError> {
        Err(IngestionError::new(
            IngestionErrorKind::NotImplemented,
            None,
            format!("live HTTP transport is disabled in default path: {url}"),
        ))
    }
}

#[derive(Debug, Clone, Default)]
pub struct FixtureHttpTransport {
    responses_by_url: BTreeMap<String, String>,
}

impl FixtureHttpTransport {
    pub fn new() -> Self {
        Self {
            responses_by_url: BTreeMap::new(),
        }
    }

    pub fn with_response(
        mut self,
        url: impl Into<String>,
        payload_json: impl Into<String>,
    ) -> Self {
        self.responses_by_url
            .insert(url.into(), payload_json.into());
        self
    }
}

impl LiveHttpTransport for FixtureHttpTransport {
    fn get(&self, url: &str) -> Result<String, IngestionError> {
        self.responses_by_url.get(url).cloned().ok_or_else(|| {
            IngestionError::new(
                IngestionErrorKind::Api,
                None,
                format!("missing fixture HTTP response for URL: {url}"),
            )
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LiveIngestionProbeReport {
    pub endpoint: String,
    pub url: String,
    pub status: String,
    pub payload_bytes: usize,
    pub latency_ms: u128,
    pub error_kind: Option<IngestionErrorKind>,
    pub error_message: Option<String>,
}

impl LiveIngestionProbeReport {
    pub fn ok(
        endpoint: impl Into<String>,
        url: impl Into<String>,
        payload_bytes: usize,
        latency_ms: u128,
    ) -> Self {
        Self {
            endpoint: endpoint.into(),
            url: url.into(),
            status: "ok".to_string(),
            payload_bytes,
            latency_ms,
            error_kind: None,
            error_message: None,
        }
    }

    pub fn error(
        endpoint: impl Into<String>,
        url: impl Into<String>,
        latency_ms: u128,
        error: IngestionError,
    ) -> Self {
        Self {
            endpoint: endpoint.into(),
            url: url.into(),
            status: "error".to_string(),
            payload_bytes: 0,
            latency_ms,
            error_kind: Some(error.kind),
            error_message: Some(error.message),
        }
    }

    pub fn is_ok(&self) -> bool {
        self.status == "ok"
    }

    pub fn to_json(&self) -> String {
        let error_kind = self
            .error_kind
            .map(|kind| format!("\"{}\"", kind.as_str()))
            .unwrap_or_else(|| "null".to_string());
        let error_message = self
            .error_message
            .as_ref()
            .map(|message| format!("\"{}\"", json_escape(message)))
            .unwrap_or_else(|| "null".to_string());

        format!(
            "{{\"endpoint\":\"{}\",\"url\":\"{}\",\"status\":\"{}\",\"payload_bytes\":{},\"latency_ms\":{},\"error_kind\":{},\"error_message\":{}}}",
            json_escape(&self.endpoint),
            json_escape(&self.url),
            json_escape(&self.status),
            self.payload_bytes,
            self.latency_ms,
            error_kind,
            error_message
        )
    }
}

impl IngestionErrorKind {
    pub fn as_str(self) -> &'static str {
        match self {
            IngestionErrorKind::Api => "Api",
            IngestionErrorKind::ReconnectRequired => "ReconnectRequired",
            IngestionErrorKind::RateLimit => "RateLimit",
            IngestionErrorKind::MalformedPayload => "MalformedPayload",
            IngestionErrorKind::JournalWrite => "JournalWrite",
            IngestionErrorKind::Unsupported => "Unsupported",
            IngestionErrorKind::NotImplemented => "NotImplemented",
        }
    }
}

pub fn probe_live_http_endpoint<T>(
    endpoint: impl Into<String>,
    url: impl Into<String>,
    transport: &T,
) -> LiveIngestionProbeReport
where
    T: LiveHttpTransport,
{
    let endpoint = endpoint.into();
    let url = url.into();
    let started_at = std::time::Instant::now();
    match transport.get(&url) {
        Ok(payload) => LiveIngestionProbeReport::ok(
            endpoint,
            url,
            payload.len(),
            started_at.elapsed().as_millis(),
        ),
        Err(error) => {
            LiveIngestionProbeReport::error(endpoint, url, started_at.elapsed().as_millis(), error)
        }
    }
}

pub fn probe_reports_to_json(reports: &[LiveIngestionProbeReport]) -> String {
    let reports_json = reports
        .iter()
        .map(LiveIngestionProbeReport::to_json)
        .collect::<Vec<String>>()
        .join(",");
    format!("[{reports_json}]")
}

#[cfg(feature = "network-integration")]
#[derive(Debug, Clone)]
pub struct ReqwestHttpTransport {
    client: reqwest::blocking::Client,
}

#[cfg(feature = "network-integration")]
impl ReqwestHttpTransport {
    pub fn new(timeout_ms: u64) -> Result<Self, IngestionError> {
        let timeout = std::time::Duration::from_millis(timeout_ms);
        let client = reqwest::blocking::Client::builder()
            .timeout(timeout)
            .user_agent("CRYPTOTEHNOLOG/phase0-network-integration")
            .build()
            .map_err(|error| {
                IngestionError::new(
                    IngestionErrorKind::Api,
                    None,
                    format!("failed to build reqwest HTTP client: {error}"),
                )
            })?;

        Ok(Self { client })
    }
}

#[cfg(feature = "network-integration")]
impl LiveHttpTransport for ReqwestHttpTransport {
    fn get(&self, url: &str) -> Result<String, IngestionError> {
        let response = self.client.get(url).send().map_err(|error| {
            IngestionError::new(
                IngestionErrorKind::Api,
                None,
                format!("HTTP GET failed for {url}: {error}"),
            )
        })?;
        let status = response.status();
        if !status.is_success() {
            return Err(IngestionError::new(
                IngestionErrorKind::Api,
                None,
                format!("HTTP GET returned {status} for {url}"),
            ));
        }

        response.text().map_err(|error| {
            IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                None,
                format!("failed to read HTTP response body for {url}: {error}"),
            )
        })
    }
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IngestionSourceReport {
    pub source: IngestionSource,
    pub raw_events_received: usize,
    pub normalized_events_received: usize,
    pub normalized_events_accepted: usize,
    pub normalized_events_rejected: usize,
}

impl IngestionSourceReport {
    pub fn new(source: IngestionSource) -> Self {
        Self {
            source,
            raw_events_received: 0,
            normalized_events_received: 0,
            normalized_events_accepted: 0,
            normalized_events_rejected: 0,
        }
    }

    fn add_validation_report(&mut self, report: &ValidationReport) {
        self.raw_events_received += report.raw_events_received;
        self.normalized_events_received += report.normalized_events_received;
        self.normalized_events_accepted += report.normalized_events_accepted;
        self.normalized_events_rejected += report.normalized_events_rejected;
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IngestionRejectionSummary {
    pub message: String,
    pub count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IngestionReport {
    pub total_raw_events_received: usize,
    pub total_normalized_events_received: usize,
    pub total_normalized_events_accepted: usize,
    pub total_normalized_events_rejected: usize,
    pub by_source: Vec<IngestionSourceReport>,
    pub rejection_counts: Vec<IngestionRejectionSummary>,
}

impl IngestionReport {
    pub fn from_outcomes(outcomes: &[IngestionOutcome]) -> Self {
        let mut source_reports: Vec<IngestionSourceReport> = Vec::new();
        let mut rejection_counts: BTreeMap<String, usize> = BTreeMap::new();

        for outcome in outcomes {
            let source = outcome.batch.source;
            if let Some(report) = source_reports
                .iter_mut()
                .find(|candidate| candidate.source == source)
            {
                report.add_validation_report(&outcome.validation_report);
            } else {
                let mut report = IngestionSourceReport::new(source);
                report.add_validation_report(&outcome.validation_report);
                source_reports.push(report);
            }

            for rejection in &outcome.validation_report.rejections {
                *rejection_counts
                    .entry(rejection.message.clone())
                    .or_insert(0) += 1;
            }
        }

        source_reports.sort_by_key(|report| report.source.as_str());
        let rejection_counts = rejection_counts
            .into_iter()
            .map(|(message, count)| IngestionRejectionSummary { message, count })
            .collect();

        Self {
            total_raw_events_received: source_reports
                .iter()
                .map(|report| report.raw_events_received)
                .sum(),
            total_normalized_events_received: source_reports
                .iter()
                .map(|report| report.normalized_events_received)
                .sum(),
            total_normalized_events_accepted: source_reports
                .iter()
                .map(|report| report.normalized_events_accepted)
                .sum(),
            total_normalized_events_rejected: source_reports
                .iter()
                .map(|report| report.normalized_events_rejected)
                .sum(),
            by_source: source_reports,
            rejection_counts,
        }
    }

    pub fn to_json(&self) -> String {
        let by_source = self
            .by_source
            .iter()
            .map(|report| {
                format!(
                    "{{\"source\":\"{}\",\"raw_events_received\":{},\"normalized_events_received\":{},\"normalized_events_accepted\":{},\"normalized_events_rejected\":{}}}",
                    report.source.as_str(),
                    report.raw_events_received,
                    report.normalized_events_received,
                    report.normalized_events_accepted,
                    report.normalized_events_rejected
                )
            })
            .collect::<Vec<String>>()
            .join(",");
        let rejection_counts = self
            .rejection_counts
            .iter()
            .map(|summary| {
                format!(
                    "{{\"message\":\"{}\",\"count\":{}}}",
                    json_escape(&summary.message),
                    summary.count
                )
            })
            .collect::<Vec<String>>()
            .join(",");

        format!(
            "{{\"total_raw_events_received\":{},\"total_normalized_events_received\":{},\"total_normalized_events_accepted\":{},\"total_normalized_events_rejected\":{},\"by_source\":[{}],\"rejection_counts\":[{}]}}",
            self.total_raw_events_received,
            self.total_normalized_events_received,
            self.total_normalized_events_accepted,
            self.total_normalized_events_rejected,
            by_source,
            rejection_counts
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
pub struct Phase0PipelineReport {
    pub schema_version: u16,
    pub status: Phase0PipelineReportStatus,
    pub raw_events: usize,
    pub normalized_events: usize,
    pub journal_rows: usize,
    pub match_decisions: usize,
    pub observations: usize,
    pub observation_rows: usize,
    pub error_stage: Option<String>,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase0PipelineReportStatus {
    Ok,
    Error,
}

impl Phase0PipelineReport {
    pub fn from_counts(
        raw_events: usize,
        normalized_events: usize,
        journal_rows: usize,
        match_decisions: usize,
        observations: usize,
        observation_rows: usize,
    ) -> Self {
        Self {
            schema_version: 1,
            status: Phase0PipelineReportStatus::Ok,
            raw_events,
            normalized_events,
            journal_rows,
            match_decisions,
            observations,
            observation_rows,
            error_stage: None,
            error_message: None,
        }
    }

    pub fn from_failure(
        counts: Phase0PipelineCounts,
        error_stage: impl Into<String>,
        error_message: impl Into<String>,
    ) -> Self {
        Self {
            schema_version: 1,
            status: Phase0PipelineReportStatus::Error,
            raw_events: counts.raw_events,
            normalized_events: counts.normalized_events,
            journal_rows: counts.journal_rows,
            match_decisions: counts.match_decisions,
            observations: counts.observations,
            observation_rows: counts.observation_rows,
            error_stage: Some(error_stage.into()),
            error_message: Some(error_message.into()),
        }
    }

    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Phase0PipelineCounts {
    pub raw_events: usize,
    pub normalized_events: usize,
    pub journal_rows: usize,
    pub match_decisions: usize,
    pub observations: usize,
    pub observation_rows: usize,
}

pub fn phase0_pipeline_report_from_scenario_steps(
    steps: &[IngestionScenarioStep],
) -> Result<Phase0PipelineReport, String> {
    ensure_supported_phase0_pipeline_scenario(steps)?;
    phase0_pipeline_report_from_batches(
        phase0_batch_for_step(&steps[0])?,
        phase0_batch_for_step(&steps[1])?,
        phase0_pipeline_uses_failing_writer(steps),
    )
}

pub fn phase0_pipeline_report_from_happy_path() -> Result<Phase0PipelineReport, String> {
    phase0_pipeline_report_from_batches(phase0_deribit_batch(), phase0_polymarket_batch(), false)
}

fn phase0_pipeline_report_from_batches(
    deribit_batch: IngestionBatch,
    polymarket_batch: IngestionBatch,
    fail_observation_row_writer: bool,
) -> Result<Phase0PipelineReport, String> {
    let mut deribit_client =
        MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch)]);
    let mut polymarket_client =
        MockIngestionClient::new(vec![MockIngestionStep::Batch(polymarket_batch)]);
    let mut journal = cryptotehnolog_common::journal::InMemoryEventJournal::new();

    ingest_once_with_report(
        &mut deribit_client,
        &mut journal,
        &IngestionConfig::phase0_deribit("mock://deribit"),
        &Phase0NormalizedBatchValidator,
    )
    .map_err(format_ingestion_error)?;
    ingest_once_with_report(
        &mut polymarket_client,
        &mut journal,
        &IngestionConfig::phase0_polymarket("mock://polymarket"),
        &Phase0NormalizedBatchValidator,
    )
    .map_err(format_ingestion_error)?;

    let replay_events = journal
        .read_events_for_replay(phase0_replay_filter())
        .map_err(|error| format!("{:?}: {}", error.kind, error.message))?;
    let config = phase0_probability_basis_config();
    let decisions = match_from_market_events(&replay_events, &config);
    let observations = observations_from_match_decisions(&decisions, &config);
    let counts_before_observation_rows = Phase0PipelineCounts {
        raw_events: journal.raw_deribit_events().len() + journal.raw_polymarket_events().len(),
        normalized_events: journal.market_events().len(),
        journal_rows: journal.event_journal_rows().len(),
        match_decisions: decisions.len(),
        observations: observations.len(),
        observation_rows: 0,
    };

    let observation_rows = if fail_observation_row_writer {
        let mut observation_row_writer = FailingPhase0BasisObservationRowWriter;
        match write_basis_observation_rows(&observations, &mut observation_row_writer) {
            Ok(()) => 0,
            Err(error) => {
                return Ok(Phase0PipelineReport::from_failure(
                    counts_before_observation_rows,
                    "basis_observation_row_writer",
                    format!("{:?}: {}", error.kind, error.message),
                ));
            }
        }
    } else {
        let mut observation_row_writer = InMemoryBasisObservationRowWriter::new();
        write_basis_observation_rows(&observations, &mut observation_row_writer)
            .map_err(|error| format!("{:?}: {}", error.kind, error.message))?;
        observation_row_writer.rows().len()
    };

    Ok(Phase0PipelineReport::from_counts(
        counts_before_observation_rows.raw_events,
        counts_before_observation_rows.normalized_events,
        counts_before_observation_rows.journal_rows,
        counts_before_observation_rows.match_decisions,
        counts_before_observation_rows.observations,
        observation_rows,
    ))
}

fn ensure_supported_phase0_pipeline_scenario(
    steps: &[IngestionScenarioStep],
) -> Result<(), String> {
    if !(steps.len() == 2 || steps.len() == 3) {
        return Err(format!(
            "phase0 pipeline report currently supports 2 data steps and optional storage_writer_failure step, got {}",
            steps.len()
        ));
    }
    if steps[0].source != IngestionSource::Deribit
        || steps[0].outcome != IngestionScenarioOutcome::Batch
        || steps[1].source != IngestionSource::Polymarket
        || !matches!(
            steps[1].outcome,
            IngestionScenarioOutcome::Batch | IngestionScenarioOutcome::MalformedBatch
        )
    {
        return Err(
            "phase0 pipeline report currently supports Deribit batch followed by Polymarket batch or malformed_batch"
                .to_string(),
        );
    }
    if steps.len() == 3
        && (steps[2].source != IngestionSource::Polymarket
            || steps[2].outcome != IngestionScenarioOutcome::StorageWriterFailure)
    {
        return Err(
            "phase0 pipeline report optional third step must be Polymarket storage_writer_failure"
                .to_string(),
        );
    }

    Ok(())
}

fn phase0_pipeline_uses_failing_writer(steps: &[IngestionScenarioStep]) -> bool {
    steps
        .iter()
        .any(|step| step.outcome == IngestionScenarioOutcome::StorageWriterFailure)
}

fn phase0_batch_for_step(step: &IngestionScenarioStep) -> Result<IngestionBatch, String> {
    match (step.source, step.outcome) {
        (IngestionSource::Deribit, IngestionScenarioOutcome::Batch) => Ok(phase0_deribit_batch()),
        (IngestionSource::Polymarket, IngestionScenarioOutcome::Batch) => {
            Ok(phase0_polymarket_batch())
        }
        (IngestionSource::Polymarket, IngestionScenarioOutcome::MalformedBatch) => {
            Ok(phase0_malformed_polymarket_batch())
        }
        _ => Err(format!(
            "unsupported phase0 pipeline step {}: {:?}/{:?}",
            step.step, step.source, step.outcome
        )),
    }
}

fn phase0_meta(event_id: &str, instrument_id: &str) -> EventMeta {
    EventMeta {
        event_id: event_id.to_string(),
        source: "phase0-pipeline-report".to_string(),
        exchange_ts_ms: 1_779_200_000_000,
        received_ts_ms: 1_779_200_000_100,
        instrument_id: instrument_id.to_string(),
        schema_version: 1,
        config_version: "phase0-ingestion".to_string(),
    }
}

fn phase0_deribit_batch() -> IngestionBatch {
    IngestionBatch {
        source: IngestionSource::Deribit,
        raw_events: vec![RawIngestionEvent::Deribit(RawDeribitEvent {
            meta: phase0_meta("raw-deribit-1", "ETH-20260601-3000-C"),
            endpoint_or_channel: "public/ticker".to_string(),
            payload_json: "{\"instrument_name\":\"ETH-20260601-3000-C\"}".to_string(),
        })],
        market_events: vec![MarketEvent::DeribitOptionQuote(DeribitOptionQuote {
            meta: phase0_meta("market-deribit-1", "ETH-20260601-3000-C"),
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

fn phase0_polymarket_batch() -> IngestionBatch {
    IngestionBatch {
        source: IngestionSource::Polymarket,
        raw_events: vec![RawIngestionEvent::Polymarket(RawPolymarketEvent {
            meta: phase0_meta("raw-polymarket-1", "eth-above-3000-june-1"),
            api_layer: PolymarketApiLayer::Gamma,
            payload_json: "{\"market_slug\":\"eth-above-3000-june-1\"}".to_string(),
        })],
        market_events: vec![MarketEvent::PolymarketOutcomeQuote(
            PolymarketOutcomeQuote {
                meta: phase0_meta("market-polymarket-1", "eth-above-3000-june-1"),
                event_slug: "eth-above-3000".to_string(),
                market_slug: "eth-above-3000-june-1".to_string(),
                outcome: "Yes".to_string(),
                target_expiry_ts_ms: 1_780_000_000_000,
                bid_probability: 0.51,
                ask_probability: 0.53,
                liquidity_usd: 10_000.0,
            },
        )],
    }
}

fn phase0_malformed_polymarket_batch() -> IngestionBatch {
    IngestionBatch {
        source: IngestionSource::Polymarket,
        raw_events: vec![RawIngestionEvent::Polymarket(RawPolymarketEvent {
            meta: phase0_meta("raw-polymarket-invalid-1", "eth-above-3000-june-1"),
            api_layer: PolymarketApiLayer::Gamma,
            payload_json: "{\"market_slug\":\"eth-above-3000-june-1\",\"invalid_quote\":true}"
                .to_string(),
        })],
        market_events: vec![MarketEvent::PolymarketOutcomeQuote(
            PolymarketOutcomeQuote {
                meta: phase0_meta("market-polymarket-invalid-1", "eth-above-3000-june-1"),
                event_slug: "eth-above-3000".to_string(),
                market_slug: "eth-above-3000-june-1".to_string(),
                outcome: "Yes".to_string(),
                target_expiry_ts_ms: 1_780_000_000_000,
                bid_probability: 0.70,
                ask_probability: 0.60,
                liquidity_usd: 10_000.0,
            },
        )],
    }
}

struct FailingPhase0BasisObservationRowWriter;

impl BasisObservationRowWriter for FailingPhase0BasisObservationRowWriter {
    fn append_basis_observation_row(
        &mut self,
        row: BasisObservationRow,
    ) -> Result<(), ObservationWriteError> {
        Err(ObservationWriteError::new(
            ObservationWriteErrorKind::Storage,
            format!(
                "simulated basis_observation row writer failure for {}",
                row.event_id
            ),
        ))
    }
}

fn phase0_replay_filter() -> cryptotehnolog_common::events::ReplayEventFilter {
    cryptotehnolog_common::events::ReplayEventFilter {
        start_ts_ms: 0,
        end_ts_ms: 1_781_000_000_000,
        event_types: vec![],
        instrument_ids: vec![],
        config_version: Some("phase0-ingestion".to_string()),
    }
}

fn phase0_probability_basis_config() -> ProbabilityBasisConfig {
    ProbabilityBasisConfig {
        min_net_edge_probability: 0.025,
        max_expiry_mismatch_ms: 86_400_000,
        max_quote_time_skew_ms: 5_000,
        min_polymarket_liquidity_usd: 1000.0,
        estimated_cost_probability: 0.010,
        risk_free_rate: 0.0,
        dividend_yield: 0.0,
        milliseconds_per_year: 365.25 * 24.0 * 60.0 * 60.0 * 1000.0,
    }
}

fn format_ingestion_error(error: IngestionError) -> String {
    format!("{:?}: {}", error.kind, error.message)
}

fn json_escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
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
        validate_phase0_event_meta(event)?;

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
                if quote.target_expiry_ts_ms <= 0 {
                    return Err(validation_error(
                        event,
                        "invalid Polymarket target expiry timestamp",
                    ));
                }
            }
        }

        Ok(())
    }
}

const SUPPORTED_NORMALIZED_EVENT_SCHEMA_VERSION: u16 = 1;

fn validate_phase0_event_meta(event: &MarketEvent) -> Result<(), NormalizedBatchValidationError> {
    let meta = event.meta();

    if meta.schema_version != SUPPORTED_NORMALIZED_EVENT_SCHEMA_VERSION {
        return Err(validation_error(
            event,
            "unsupported normalized event schema_version",
        ));
    }

    if meta.received_ts_ms < meta.exchange_ts_ms {
        return Err(validation_error(
            event,
            "normalized event received_ts_ms is earlier than exchange_ts_ms",
        ));
    }

    Ok(())
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

#[derive(Debug, Clone, PartialEq)]
pub struct DeribitOptionDiscoveryCriteria {
    pub underlying: String,
    pub target_expiry_ts_ms: i64,
    pub target_strike: f64,
    pub option_kind: OptionKind,
    pub max_expiry_distance_ms: i64,
    pub max_strike_distance: f64,
}

impl DeribitOptionDiscoveryCriteria {
    pub fn phase0_eth_call_3000_june_2026() -> Self {
        Self {
            underlying: "ETH".to_string(),
            target_expiry_ts_ms: 1_780_272_000_000,
            target_strike: 3000.0,
            option_kind: OptionKind::Call,
            max_expiry_distance_ms: 7 * 86_400_000,
            max_strike_distance: 500.0,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct DeribitDiscoveredOption {
    pub instrument_name: String,
    pub underlying: String,
    pub expiry_ts_ms: i64,
    pub strike: f64,
    pub option_kind: OptionKind,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DeribitInstrumentName {
    raw: String,
    pub underlying: String,
    pub expiry_ts_ms: i64,
    pub strike: f64,
    pub option_kind: OptionKind,
}

impl DeribitInstrumentName {
    pub fn parse(raw: impl Into<String>) -> Result<Self, IngestionError> {
        let raw = raw.into();
        let parts: Vec<&str> = raw.split('-').collect();
        if parts.len() != 4 || parts[0].is_empty() {
            return Err(malformed_deribit_instrument(&raw));
        }

        let underlying = parts[0].to_string();
        let expiry_ts_ms = parse_deribit_expiry_part_ts_ms(parts[1])?;
        let strike = parts[2].parse::<f64>().map_err(|error| {
            IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Deribit),
                format!("invalid Deribit instrument strike: {error}"),
            )
        })?;
        if !strike.is_finite() || strike <= 0.0 {
            return Err(IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Deribit),
                format!("invalid Deribit instrument strike `{}`", parts[2]),
            ));
        }
        let option_kind = parse_deribit_option_kind_text(parts[3])
            .map_err(|_| malformed_deribit_instrument(&raw))?;

        Ok(Self {
            raw,
            underlying,
            expiry_ts_ms,
            strike,
            option_kind,
        })
    }

    pub fn raw(&self) -> &str {
        &self.raw
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeribitLiveIngestionClient {
    pub base_url: String,
    pub instrument_name: String,
}

impl DeribitLiveIngestionClient {
    pub fn new(base_url: impl Into<String>, instrument_name: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into(),
            instrument_name: instrument_name.into(),
        }
    }

    pub fn from_discovered(
        base_url: impl Into<String>,
        discovered: &DeribitDiscoveredOption,
    ) -> Self {
        Self::new(base_url, discovered.instrument_name.clone())
    }

    pub fn instruments_url(base_url: &str) -> String {
        format!(
            "{}/api/v2/public/get_instruments?currency=ETH&kind=option&expired=false",
            base_url.trim_end_matches('/')
        )
    }

    pub fn ticker_url(&self) -> String {
        format!(
            "{}/api/v2/public/ticker?instrument_name={}",
            self.base_url.trim_end_matches('/'),
            self.instrument_name
        )
    }

    pub fn discover_option_from_payload(
        payload_json: &str,
        criteria: &DeribitOptionDiscoveryCriteria,
    ) -> Result<DeribitDiscoveredOption, IngestionError> {
        let instruments = parse_deribit_instruments_payload(payload_json, criteria)?;
        select_deribit_option_candidate(instruments, criteria)
    }

    pub fn parse_ticker_payload(
        &self,
        payload_json: &str,
        config: &IngestionConfig,
        received_ts_ms: i64,
    ) -> Result<IngestionBatch, IngestionError> {
        if config.source != IngestionSource::Deribit {
            return Err(IngestionError::new(
                IngestionErrorKind::Unsupported,
                Some(config.source),
                "DeribitLiveIngestionClient requires Deribit ingestion config",
            ));
        }

        let parser = JsonPayloadParser::new(payload_json, IngestionSource::Deribit, "Deribit")?;
        let ticker = parser
            .object_at(&["result"])
            .unwrap_or_else(|| parser.root());
        let instrument_name = parser.string_from(ticker, "instrument_name")?;
        if instrument_name != self.instrument_name {
            return Err(IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Deribit),
                format!(
                    "Deribit ticker instrument mismatch: expected {}, got {}",
                    self.instrument_name, instrument_name
                ),
            ));
        }

        let timestamp_ms = parser.i64_from(ticker, "timestamp")?;
        let parsed_instrument = DeribitInstrumentName::parse(instrument_name.clone())?;
        let expiry_ts_ms = parsed_instrument.expiry_ts_ms;
        let strike = parsed_instrument.strike;
        let option_kind = parsed_instrument.option_kind;
        let underlying = parsed_instrument.underlying;
        let underlying_price = parser.f64_from(ticker, "underlying_price")?;
        let bid = parser.f64_from(ticker, "best_bid_price")?;
        let ask = parser.f64_from(ticker, "best_ask_price")?;
        let mark_iv = parser.f64_from(ticker, "mark_iv")?;

        let raw_meta = EventMeta {
            event_id: format!("raw-deribit-ticker:{instrument_name}:{timestamp_ms}"),
            source: "deribit_live_skeleton".to_string(),
            exchange_ts_ms: timestamp_ms,
            received_ts_ms,
            instrument_id: instrument_name.clone(),
            schema_version: 1,
            config_version: config.config_version.clone(),
        };
        let market_meta = EventMeta {
            event_id: format!("market-deribit-ticker:{instrument_name}:{timestamp_ms}"),
            ..raw_meta.clone()
        };

        Ok(IngestionBatch {
            source: IngestionSource::Deribit,
            raw_events: vec![RawIngestionEvent::Deribit(RawDeribitEvent {
                meta: raw_meta,
                endpoint_or_channel: "public/ticker".to_string(),
                payload_json: payload_json.to_string(),
            })],
            market_events: vec![MarketEvent::DeribitOptionQuote(DeribitOptionQuote {
                meta: market_meta,
                underlying,
                expiry_ts_ms,
                strike,
                option_kind,
                underlying_price,
                bid,
                ask,
                mark_iv,
            })],
        })
    }

    pub fn fetch_ticker_with_transport<T>(
        &self,
        transport: &T,
        config: &IngestionConfig,
        received_ts_ms: i64,
    ) -> Result<IngestionBatch, IngestionError>
    where
        T: LiveHttpTransport,
    {
        let payload_json = transport.get(&self.ticker_url()).map_err(|mut error| {
            if error.source.is_none() {
                error.source = Some(IngestionSource::Deribit);
            }
            error
        })?;

        self.parse_ticker_payload(&payload_json, config, received_ts_ms)
    }
}

impl IngestionClient for DeribitLiveIngestionClient {
    fn poll_once(&mut self, config: &IngestionConfig) -> Result<IngestionBatch, IngestionError> {
        Err(IngestionError::new(
            IngestionErrorKind::NotImplemented,
            Some(config.source),
            "Deribit live ingestion skeleton has no network calls in default path",
        ))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PolymarketLiveIngestionClient {
    pub base_url: String,
    pub market_slug: String,
    pub outcome: String,
    pub outcome_token_id: Option<String>,
    pub target_expiry_ts_ms: Option<i64>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PolymarketMarketDiscoveryCriteria {
    pub required_terms: Vec<String>,
    pub outcome: String,
    pub target_expiry_ts_ms: i64,
    pub min_liquidity_usd: f64,
}

impl PolymarketMarketDiscoveryCriteria {
    pub fn phase0_eth_above_3000_yes() -> Self {
        Self {
            required_terms: vec!["eth".to_string(), "3000".to_string()],
            outcome: "Yes".to_string(),
            target_expiry_ts_ms: 1_780_272_000_000,
            min_liquidity_usd: 1_000.0,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct PolymarketDiscoveredMarket {
    pub market_slug: String,
    pub event_slug: String,
    pub question: String,
    pub outcome: String,
    pub outcome_token_id: Option<String>,
    pub target_expiry_ts_ms: i64,
    pub liquidity_usd: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PolymarketClobBookQuote {
    pub token_id: String,
    pub market_id: Option<String>,
    pub bid_probability: f64,
    pub ask_probability: f64,
    pub bid_size: Option<f64>,
    pub ask_size: Option<f64>,
    pub timestamp_ms: Option<i64>,
}

impl PolymarketLiveIngestionClient {
    pub fn new(
        base_url: impl Into<String>,
        market_slug: impl Into<String>,
        outcome: impl Into<String>,
    ) -> Self {
        Self {
            base_url: base_url.into(),
            market_slug: market_slug.into(),
            outcome: outcome.into(),
            outcome_token_id: None,
            target_expiry_ts_ms: None,
        }
    }

    pub fn from_discovered(
        base_url: impl Into<String>,
        discovered: &PolymarketDiscoveredMarket,
    ) -> Self {
        Self::new(
            base_url,
            discovered.market_slug.clone(),
            discovered.outcome.clone(),
        )
        .with_outcome_token_id_option(discovered.outcome_token_id.clone())
        .with_target_expiry(discovered.target_expiry_ts_ms)
    }

    pub fn with_outcome_token_id(mut self, outcome_token_id: impl Into<String>) -> Self {
        self.outcome_token_id = Some(outcome_token_id.into());
        self
    }

    fn with_outcome_token_id_option(mut self, outcome_token_id: Option<String>) -> Self {
        self.outcome_token_id = outcome_token_id;
        self
    }

    pub fn with_target_expiry(mut self, target_expiry_ts_ms: i64) -> Self {
        self.target_expiry_ts_ms = Some(target_expiry_ts_ms);
        self
    }

    pub fn markets_url(base_url: &str) -> String {
        format!(
            "{}/markets?active=true&closed=false&limit=100",
            base_url.trim_end_matches('/')
        )
    }

    pub fn gamma_market_url(&self) -> String {
        format!(
            "{}/markets/slug/{}",
            self.base_url.trim_end_matches('/'),
            self.market_slug
        )
    }

    pub fn clob_book_url_for_token(base_url: &str, token_id: &str) -> String {
        format!(
            "{}/book?token_id={token_id}",
            base_url.trim_end_matches('/')
        )
    }

    pub fn clob_book_url(&self, base_url: &str) -> Result<String, IngestionError> {
        let Some(token_id) = &self.outcome_token_id else {
            return Err(IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Polymarket),
                format!(
                    "Polymarket CLOB book URL requires outcome token id for {} {}",
                    self.market_slug, self.outcome
                ),
            ));
        };

        Ok(Self::clob_book_url_for_token(base_url, token_id))
    }

    pub fn discover_market_from_payload(
        payload_json: &str,
        criteria: &PolymarketMarketDiscoveryCriteria,
    ) -> Result<PolymarketDiscoveredMarket, IngestionError> {
        let markets = parse_polymarket_markets_payload(payload_json, criteria)?;
        select_polymarket_market_candidate(markets, criteria)
    }

    pub fn parse_gamma_market_payload(
        &self,
        payload_json: &str,
        config: &IngestionConfig,
        received_ts_ms: i64,
    ) -> Result<IngestionBatch, IngestionError> {
        if config.source != IngestionSource::Polymarket {
            return Err(IngestionError::new(
                IngestionErrorKind::Unsupported,
                Some(config.source),
                "PolymarketLiveIngestionClient requires Polymarket ingestion config",
            ));
        }

        let parser =
            JsonPayloadParser::new(payload_json, IngestionSource::Polymarket, "Polymarket")?;
        let market_slug = parser
            .optional_string_any(&["market_slug", "slug"])?
            .ok_or_else(|| parser.missing_field("market_slug|slug"))?;
        if market_slug != self.market_slug {
            return Err(IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Polymarket),
                format!(
                    "Polymarket market mismatch: expected {}, got {}",
                    self.market_slug, market_slug
                ),
            ));
        }

        let event_slug = parser
            .optional_string_any(&["event_slug", "eventSlug"])?
            .or_else(|| {
                parser
                    .first_nested_string(&["events"], "slug")
                    .ok()
                    .flatten()
            })
            .unwrap_or_else(|| market_slug.clone());
        let outcome_index = parser.outcome_index(&self.outcome)?;
        let outcome = self.outcome.clone();
        let Some(outcome_index) = outcome_index else {
            return Err(IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Polymarket),
                format!("Polymarket outcome `{}` not found in payload", self.outcome),
            ));
        };

        let timestamp_ms = parser
            .optional_i64_any(&["timestamp", "updatedAtMillis"])?
            .unwrap_or(received_ts_ms);
        let target_expiry_ts_ms = self
            .target_expiry_ts_ms
            .or(parser.optional_i64_any(&["target_expiry_ts_ms", "targetExpiryTsMs"])?)
            .unwrap_or(timestamp_ms);
        let explicit_bid_probability = parser.optional_f64_any(&["bid_probability", "bestBid"])?;
        let explicit_ask_probability = parser.optional_f64_any(&["ask_probability", "bestAsk"])?;
        let fallback_outcome_price =
            if explicit_bid_probability.is_none() || explicit_ask_probability.is_none() {
                Some(parser.outcome_price(outcome_index)?)
            } else {
                None
            };
        let Some(bid_probability) = explicit_bid_probability.or(fallback_outcome_price) else {
            return Err(IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Polymarket),
                "Polymarket bid probability is missing",
            ));
        };
        let Some(ask_probability) = explicit_ask_probability.or(fallback_outcome_price) else {
            return Err(IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Polymarket),
                "Polymarket ask probability is missing",
            ));
        };
        let liquidity_usd = parser
            .optional_f64_any(&["liquidity_usd", "liquidityNum", "liquidity"])?
            .unwrap_or(0.0);

        let raw_meta = EventMeta {
            event_id: format!("raw-polymarket-gamma:{market_slug}:{outcome}:{timestamp_ms}"),
            source: "polymarket_live_skeleton".to_string(),
            exchange_ts_ms: timestamp_ms,
            received_ts_ms,
            instrument_id: market_slug.clone(),
            schema_version: 1,
            config_version: config.config_version.clone(),
        };
        let market_meta = EventMeta {
            event_id: format!("market-polymarket-gamma:{market_slug}:{outcome}:{timestamp_ms}"),
            ..raw_meta.clone()
        };

        Ok(IngestionBatch {
            source: IngestionSource::Polymarket,
            raw_events: vec![RawIngestionEvent::Polymarket(RawPolymarketEvent {
                meta: raw_meta,
                api_layer: PolymarketApiLayer::Gamma,
                payload_json: payload_json.to_string(),
            })],
            market_events: vec![MarketEvent::PolymarketOutcomeQuote(
                PolymarketOutcomeQuote {
                    meta: market_meta,
                    event_slug,
                    market_slug,
                    outcome,
                    target_expiry_ts_ms,
                    bid_probability,
                    ask_probability,
                    liquidity_usd,
                },
            )],
        })
    }

    pub fn parse_clob_book_payload(
        payload_json: &str,
    ) -> Result<PolymarketClobBookQuote, IngestionError> {
        parse_polymarket_clob_book_payload(payload_json)
    }

    pub fn parse_gamma_market_with_clob_book_payload(
        &self,
        gamma_payload_json: &str,
        clob_payload_json: &str,
        config: &IngestionConfig,
        received_ts_ms: i64,
    ) -> Result<IngestionBatch, IngestionError> {
        let mut batch =
            self.parse_gamma_market_payload(gamma_payload_json, config, received_ts_ms)?;
        let clob_quote = Self::parse_clob_book_payload(clob_payload_json)?;
        if let Some(expected_token_id) = &self.outcome_token_id {
            if &clob_quote.token_id != expected_token_id {
                return Err(IngestionError::new(
                    IngestionErrorKind::MalformedPayload,
                    Some(IngestionSource::Polymarket),
                    format!(
                        "Polymarket CLOB token mismatch: expected {}, got {}",
                        expected_token_id, clob_quote.token_id
                    ),
                ));
            }
        }

        let exchange_ts_ms = clob_quote.timestamp_ms.unwrap_or(received_ts_ms);
        let raw_meta = EventMeta {
            event_id: format!(
                "raw-polymarket-clob:{}:{}:{}",
                self.market_slug, clob_quote.token_id, exchange_ts_ms
            ),
            source: "polymarket_live_skeleton".to_string(),
            exchange_ts_ms,
            received_ts_ms,
            instrument_id: clob_quote.token_id.clone(),
            schema_version: 1,
            config_version: config.config_version.clone(),
        };
        batch
            .raw_events
            .push(RawIngestionEvent::Polymarket(RawPolymarketEvent {
                meta: raw_meta,
                api_layer: PolymarketApiLayer::Clob,
                payload_json: clob_payload_json.to_string(),
            }));

        let Some(MarketEvent::PolymarketOutcomeQuote(quote)) = batch.market_events.first_mut()
        else {
            return Err(IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Polymarket),
                "Polymarket Gamma batch did not produce outcome quote",
            ));
        };

        quote.meta.event_id = format!(
            "market-polymarket-clob:{}:{}:{}",
            self.market_slug, self.outcome, exchange_ts_ms
        );
        quote.meta.exchange_ts_ms = exchange_ts_ms;
        quote.bid_probability = clob_quote.bid_probability;
        quote.ask_probability = clob_quote.ask_probability;

        Ok(batch)
    }

    pub fn fetch_gamma_market_with_transport<T>(
        &self,
        transport: &T,
        config: &IngestionConfig,
        received_ts_ms: i64,
    ) -> Result<IngestionBatch, IngestionError>
    where
        T: LiveHttpTransport,
    {
        let payload_json = transport
            .get(&self.gamma_market_url())
            .map_err(|mut error| {
                if error.source.is_none() {
                    error.source = Some(IngestionSource::Polymarket);
                }
                error
            })?;

        self.parse_gamma_market_payload(&payload_json, config, received_ts_ms)
    }
}

impl IngestionClient for PolymarketLiveIngestionClient {
    fn poll_once(&mut self, config: &IngestionConfig) -> Result<IngestionBatch, IngestionError> {
        Err(IngestionError::new(
            IngestionErrorKind::NotImplemented,
            Some(config.source),
            "Polymarket live ingestion skeleton has no network calls in default path",
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

pub fn ingest_once_with_report_and_row_writer<C, J, V, W>(
    client: &mut C,
    journal: &mut J,
    row_writer: &mut W,
    config: &IngestionConfig,
    validator: &V,
) -> Result<IngestionOutcome, IngestionError>
where
    C: IngestionClient,
    J: EventJournal,
    V: NormalizedBatchValidator,
    W: EventJournalRowWriter,
{
    let batch = client.poll_once(config)?;

    write_raw_events(journal, &batch)?;
    write_raw_event_rows(row_writer, &batch)?;

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
    write_normalized_event_rows(row_writer, &batch, &accepted_events)?;

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

fn write_raw_event_rows<W>(writer: &mut W, batch: &IngestionBatch) -> Result<(), IngestionError>
where
    W: EventJournalRowWriter,
{
    for raw_event in &batch.raw_events {
        let row = match raw_event {
            RawIngestionEvent::Deribit(event) => EventJournalRow::from_raw_deribit_event(event),
            RawIngestionEvent::Polymarket(event) => {
                EventJournalRow::from_raw_polymarket_event(event)
            }
        };
        writer
            .append_event_journal_row(row)
            .map_err(|error| IngestionError::from_journal(raw_event.source(), error))?;
    }

    Ok(())
}

fn write_normalized_event_rows<W>(
    writer: &mut W,
    batch: &IngestionBatch,
    market_events: &[MarketEvent],
) -> Result<(), IngestionError>
where
    W: EventJournalRowWriter,
{
    for market_event in market_events {
        writer
            .append_event_journal_row(EventJournalRow::from_market_event(market_event))
            .map_err(|error| IngestionError::from_journal(batch.source, error))?;
    }

    Ok(())
}

#[derive(Debug, Clone)]
struct JsonPayloadParser {
    root: Value,
    source: IngestionSource,
    source_name: &'static str,
}

impl JsonPayloadParser {
    fn new(
        payload_json: &str,
        source: IngestionSource,
        source_name: &'static str,
    ) -> Result<Self, IngestionError> {
        let root = serde_json::from_str(payload_json).map_err(|error| {
            IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(source),
                format!("invalid {source_name} JSON payload: {error}"),
            )
        })?;

        Ok(Self {
            root,
            source,
            source_name,
        })
    }

    fn root(&self) -> &Value {
        &self.root
    }

    fn root_array(&self) -> Option<&Vec<Value>> {
        self.root.as_array()
    }

    fn object_at(&self, path: &[&str]) -> Option<&Value> {
        let mut current = &self.root;
        for key in path {
            current = current.get(*key)?;
        }
        current.as_object()?;
        Some(current)
    }

    fn array_at(&self, path: &[&str]) -> Option<&Vec<Value>> {
        let mut current = &self.root;
        for key in path {
            current = current.get(*key)?;
        }
        current.as_array()
    }

    fn string_from(&self, object: &Value, key: &str) -> Result<String, IngestionError> {
        let Some(value) = object.get(key) else {
            return Err(self.missing_field(key));
        };
        self.value_to_string(value, key)
    }

    fn optional_string_from(
        &self,
        object: &Value,
        key: &str,
    ) -> Result<Option<String>, IngestionError> {
        object
            .get(key)
            .map(|value| self.value_to_string(value, key))
            .transpose()
    }

    fn f64_from(&self, object: &Value, key: &str) -> Result<f64, IngestionError> {
        let Some(value) = object.get(key) else {
            return Err(self.missing_field(key));
        };
        self.value_to_f64(value, key)
    }

    fn optional_f64_from(&self, object: &Value, key: &str) -> Result<Option<f64>, IngestionError> {
        object
            .get(key)
            .map(|value| self.value_to_f64(value, key))
            .transpose()
    }

    fn i64_from(&self, object: &Value, key: &str) -> Result<i64, IngestionError> {
        let Some(value) = object.get(key) else {
            return Err(self.missing_field(key));
        };
        self.value_to_i64(value, key)
    }

    fn optional_i64_from(&self, object: &Value, key: &str) -> Result<Option<i64>, IngestionError> {
        object
            .get(key)
            .map(|value| self.value_to_i64(value, key))
            .transpose()
    }

    fn optional_bool_from(
        &self,
        object: &Value,
        key: &str,
    ) -> Result<Option<bool>, IngestionError> {
        object
            .get(key)
            .map(|value| self.value_to_bool(value, key))
            .transpose()
    }

    fn optional_string_any(&self, keys: &[&str]) -> Result<Option<String>, IngestionError> {
        for key in keys {
            if let Some(value) = self.root.get(*key) {
                return self.value_to_string(value, key).map(Some);
            }
        }
        Ok(None)
    }

    fn optional_f64_any(&self, keys: &[&str]) -> Result<Option<f64>, IngestionError> {
        for key in keys {
            if let Some(value) = self.root.get(*key) {
                return self.value_to_f64(value, key).map(Some);
            }
        }
        Ok(None)
    }

    fn optional_i64_any(&self, keys: &[&str]) -> Result<Option<i64>, IngestionError> {
        for key in keys {
            if let Some(value) = self.root.get(*key) {
                return self.value_to_i64(value, key).map(Some);
            }
        }
        Ok(None)
    }

    fn first_nested_string(
        &self,
        array_key_path: &[&str],
        key: &str,
    ) -> Result<Option<String>, IngestionError> {
        let mut current = &self.root;
        for path_key in array_key_path {
            let Some(next) = current.get(*path_key) else {
                return Ok(None);
            };
            current = next;
        }
        let Some(array) = current.as_array() else {
            return Ok(None);
        };
        let Some(first) = array.first() else {
            return Ok(None);
        };
        let Some(value) = first.get(key) else {
            return Ok(None);
        };
        self.value_to_string(value, key).map(Some)
    }

    fn outcome_index(&self, outcome: &str) -> Result<Option<usize>, IngestionError> {
        if let Some(single_outcome) = self.optional_string_any(&["outcome"])? {
            return Ok((single_outcome == outcome).then_some(0));
        }

        let Some(outcomes_value) = self.root.get("outcomes") else {
            return Ok(None);
        };
        let outcomes = self.string_array(outcomes_value, "outcomes")?;
        Ok(outcomes.iter().position(|candidate| candidate == outcome))
    }

    fn outcome_price(&self, outcome_index: usize) -> Result<f64, IngestionError> {
        let Some(prices_value) = self.root.get("outcomePrices") else {
            return Err(self.missing_field("outcomePrices"));
        };
        let prices = self.string_array(prices_value, "outcomePrices")?;
        let Some(raw_price) = prices.get(outcome_index) else {
            return Err(self.malformed_field("outcomePrices"));
        };
        raw_price.parse::<f64>().map_err(|error| {
            IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(self.source),
                format!("invalid {} outcome price: {error}", self.source_name),
            )
        })
    }

    fn string_array(&self, value: &Value, key: &str) -> Result<Vec<String>, IngestionError> {
        if let Some(array) = value.as_array() {
            return array
                .iter()
                .map(|entry| self.value_to_string(entry, key))
                .collect();
        }

        if let Some(encoded_array) = value.as_str() {
            let decoded: Value = serde_json::from_str(encoded_array).map_err(|error| {
                IngestionError::new(
                    IngestionErrorKind::MalformedPayload,
                    Some(self.source),
                    format!(
                        "invalid {} encoded array field {key}: {error}",
                        self.source_name
                    ),
                )
            })?;
            let Some(array) = decoded.as_array() else {
                return Err(self.malformed_field(key));
            };
            return array
                .iter()
                .map(|entry| self.value_to_string(entry, key))
                .collect();
        }

        Err(self.malformed_field(key))
    }

    fn string_array_from(
        &self,
        object: &Value,
        key: &str,
    ) -> Result<Option<Vec<String>>, IngestionError> {
        object
            .get(key)
            .map(|value| self.string_array(value, key))
            .transpose()
    }

    fn value_to_string(&self, value: &Value, key: &str) -> Result<String, IngestionError> {
        value
            .as_str()
            .map(ToString::to_string)
            .ok_or_else(|| self.malformed_field(key))
    }

    fn value_to_f64(&self, value: &Value, key: &str) -> Result<f64, IngestionError> {
        if let Some(number) = value.as_f64() {
            return Ok(number);
        }
        if let Some(text) = value.as_str() {
            return text.parse::<f64>().map_err(|error| {
                IngestionError::new(
                    IngestionErrorKind::MalformedPayload,
                    Some(self.source),
                    format!("invalid {} numeric field {key}: {error}", self.source_name),
                )
            });
        }

        Err(self.malformed_field(key))
    }

    fn value_to_i64(&self, value: &Value, key: &str) -> Result<i64, IngestionError> {
        if let Some(number) = value.as_i64() {
            return Ok(number);
        }
        if let Some(text) = value.as_str() {
            return text.parse::<i64>().map_err(|error| {
                IngestionError::new(
                    IngestionErrorKind::MalformedPayload,
                    Some(self.source),
                    format!("invalid {} integer field {key}: {error}", self.source_name),
                )
            });
        }

        Err(self.malformed_field(key))
    }

    fn value_to_bool(&self, value: &Value, key: &str) -> Result<bool, IngestionError> {
        if let Some(flag) = value.as_bool() {
            return Ok(flag);
        }
        if let Some(text) = value.as_str() {
            return text.parse::<bool>().map_err(|error| {
                IngestionError::new(
                    IngestionErrorKind::MalformedPayload,
                    Some(self.source),
                    format!("invalid {} boolean field {key}: {error}", self.source_name),
                )
            });
        }

        Err(self.malformed_field(key))
    }

    fn missing_field(&self, key: &str) -> IngestionError {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(self.source),
            format!("missing {} field `{key}`", self.source_name),
        )
    }

    fn malformed_field(&self, key: &str) -> IngestionError {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(self.source),
            format!("malformed {} field `{key}`", self.source_name),
        )
    }
}

fn parse_deribit_instruments_payload(
    payload_json: &str,
    _criteria: &DeribitOptionDiscoveryCriteria,
) -> Result<Vec<DeribitDiscoveredOption>, IngestionError> {
    let parser = JsonPayloadParser::new(payload_json, IngestionSource::Deribit, "Deribit")?;
    let instruments = parser.array_at(&["result"]).ok_or_else(|| {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Deribit),
            "missing Deribit instruments result array",
        )
    })?;

    let mut discovered = Vec::new();
    for instrument in instruments {
        let instrument_name = parser.string_from(instrument, "instrument_name")?;
        let parsed_instrument = DeribitInstrumentName::parse(instrument_name.clone())?;
        let underlying = parser
            .optional_string_from(instrument, "base_currency")?
            .unwrap_or_else(|| parsed_instrument.underlying.clone());
        let expiry_ts_ms = match parser.optional_i64_from(instrument, "expiration_timestamp")? {
            Some(value) => value,
            None => parsed_instrument.expiry_ts_ms,
        };
        let strike = match parser.optional_f64_from(instrument, "strike")? {
            Some(value) => value,
            None => parsed_instrument.strike,
        };
        let option_kind = match parser.optional_string_from(instrument, "option_type")? {
            Some(kind) => parse_deribit_option_kind_text(&kind)?,
            None => parsed_instrument.option_kind,
        };

        discovered.push(DeribitDiscoveredOption {
            instrument_name,
            underlying,
            expiry_ts_ms,
            strike,
            option_kind,
        });
    }

    Ok(discovered)
}

fn parse_polymarket_markets_payload(
    payload_json: &str,
    criteria: &PolymarketMarketDiscoveryCriteria,
) -> Result<Vec<PolymarketDiscoveredMarket>, IngestionError> {
    let parser = JsonPayloadParser::new(payload_json, IngestionSource::Polymarket, "Polymarket")?;
    let markets = parser
        .root_array()
        .or_else(|| parser.array_at(&["result"]))
        .or_else(|| parser.array_at(&["data"]))
        .ok_or_else(|| {
            IngestionError::new(
                IngestionErrorKind::MalformedPayload,
                Some(IngestionSource::Polymarket),
                "missing Polymarket markets array",
            )
        })?;

    let mut discovered = Vec::new();
    for market in markets {
        let market_slug = parser
            .optional_string_from(market, "slug")?
            .or_else(|| {
                parser
                    .optional_string_from(market, "market_slug")
                    .ok()
                    .flatten()
            })
            .ok_or_else(|| parser.missing_field("slug|market_slug"))?;
        let question = parser
            .optional_string_from(market, "question")?
            .unwrap_or_else(|| market_slug.clone());
        let event_slug = parser
            .optional_string_from(market, "event_slug")?
            .or_else(|| {
                parser
                    .optional_string_from(market, "eventSlug")
                    .ok()
                    .flatten()
            })
            .or_else(|| {
                first_nested_string_from_value(&parser, market, &["events"], "slug")
                    .ok()
                    .flatten()
            })
            .unwrap_or_else(|| market_slug.clone());
        let active = parser.optional_bool_from(market, "active")?.unwrap_or(true);
        let closed = parser
            .optional_bool_from(market, "closed")?
            .unwrap_or(false);
        if !active || closed {
            continue;
        }
        let liquidity_usd = parser
            .optional_f64_from(market, "liquidityNum")?
            .or_else(|| parser.optional_f64_from(market, "liquidity").ok().flatten())
            .or_else(|| {
                parser
                    .optional_f64_from(market, "liquidity_usd")
                    .ok()
                    .flatten()
            })
            .unwrap_or(0.0);
        let outcomes = parser
            .string_array_from(market, "outcomes")?
            .unwrap_or_default();
        let Some(outcome_index) = outcomes
            .iter()
            .position(|outcome| outcome == &criteria.outcome)
        else {
            continue;
        };
        let outcome_token_id =
            polymarket_outcome_token_id_from_object(&parser, market, outcome_index)?;

        discovered.push(PolymarketDiscoveredMarket {
            market_slug,
            event_slug,
            question,
            outcome: criteria.outcome.clone(),
            outcome_token_id,
            target_expiry_ts_ms: criteria.target_expiry_ts_ms,
            liquidity_usd,
        });
    }

    Ok(discovered)
}

fn select_deribit_option_candidate(
    instruments: Vec<DeribitDiscoveredOption>,
    criteria: &DeribitOptionDiscoveryCriteria,
) -> Result<DeribitDiscoveredOption, IngestionError> {
    let mut candidates: Vec<DeribitDiscoveredOption> = instruments
        .into_iter()
        .filter(|instrument| instrument.underlying == criteria.underlying)
        .filter(|instrument| instrument.option_kind == criteria.option_kind)
        .filter(|instrument| {
            (instrument.expiry_ts_ms - criteria.target_expiry_ts_ms).abs()
                <= criteria.max_expiry_distance_ms
        })
        .filter(|instrument| {
            (instrument.strike - criteria.target_strike).abs() <= criteria.max_strike_distance
        })
        .collect();

    candidates.sort_by(|left, right| {
        let left_expiry_distance = (left.expiry_ts_ms - criteria.target_expiry_ts_ms).abs();
        let right_expiry_distance = (right.expiry_ts_ms - criteria.target_expiry_ts_ms).abs();
        let left_strike_distance = (left.strike - criteria.target_strike).abs();
        let right_strike_distance = (right.strike - criteria.target_strike).abs();

        left_expiry_distance
            .cmp(&right_expiry_distance)
            .then_with(|| left_strike_distance.total_cmp(&right_strike_distance))
            .then_with(|| left.instrument_name.cmp(&right.instrument_name))
    });

    candidates.into_iter().next().ok_or_else(|| {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Deribit),
            format!(
                "no Deribit option candidate for {} {:?} strike {} expiry {}",
                criteria.underlying,
                criteria.option_kind,
                criteria.target_strike,
                criteria.target_expiry_ts_ms
            ),
        )
    })
}

fn select_polymarket_market_candidate(
    markets: Vec<PolymarketDiscoveredMarket>,
    criteria: &PolymarketMarketDiscoveryCriteria,
) -> Result<PolymarketDiscoveredMarket, IngestionError> {
    let required_terms: Vec<String> = criteria
        .required_terms
        .iter()
        .map(|term| term.to_ascii_lowercase())
        .collect();
    let mut candidates: Vec<PolymarketDiscoveredMarket> = markets
        .into_iter()
        .filter(|market| market.liquidity_usd >= criteria.min_liquidity_usd)
        .filter(|market| {
            let haystack =
                format!("{} {}", market.market_slug, market.question).to_ascii_lowercase();
            required_terms
                .iter()
                .all(|term| haystack.contains(term.as_str()))
        })
        .collect();

    candidates.sort_by(|left, right| {
        right
            .liquidity_usd
            .total_cmp(&left.liquidity_usd)
            .then_with(|| left.market_slug.cmp(&right.market_slug))
    });

    candidates.into_iter().next().ok_or_else(|| {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Polymarket),
            format!(
                "no Polymarket market candidate for terms {:?}, outcome {}, min liquidity {}",
                criteria.required_terms, criteria.outcome, criteria.min_liquidity_usd
            ),
        )
    })
}

fn parse_polymarket_clob_book_payload(
    payload_json: &str,
) -> Result<PolymarketClobBookQuote, IngestionError> {
    let parser =
        JsonPayloadParser::new(payload_json, IngestionSource::Polymarket, "Polymarket CLOB")?;
    let token_id = parser
        .optional_string_any(&["asset_id", "token_id", "tokenId"])?
        .ok_or_else(|| parser.missing_field("asset_id|token_id|tokenId"))?;
    let market_id = parser.optional_string_any(&["market", "condition_id", "conditionId"])?;
    let (bid_probability, bid_size) = polymarket_clob_best_level(&parser, "bids", "bid")?;
    let (ask_probability, ask_size) = polymarket_clob_best_level(&parser, "asks", "ask")?;
    if bid_probability > ask_probability {
        return Err(IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Polymarket),
            format!(
                "Polymarket CLOB bid/ask crossed: bid {} > ask {}",
                bid_probability, ask_probability
            ),
        ));
    }
    let timestamp_ms = parser.optional_i64_any(&["timestamp_ms", "timestampMillis"])?;

    Ok(PolymarketClobBookQuote {
        token_id,
        market_id,
        bid_probability,
        ask_probability,
        bid_size,
        ask_size,
        timestamp_ms,
    })
}

fn polymarket_clob_best_level(
    parser: &JsonPayloadParser,
    levels_key: &str,
    side_name: &str,
) -> Result<(f64, Option<f64>), IngestionError> {
    let levels = parser.array_at(&[levels_key]).ok_or_else(|| {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Polymarket),
            format!("missing Polymarket CLOB `{levels_key}` array"),
        )
    })?;
    let Some(best_level) = levels.first() else {
        return Err(IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Polymarket),
            format!("empty Polymarket CLOB `{levels_key}` array"),
        ));
    };
    let price = parser.f64_from(best_level, "price")?;
    if !(0.0..=1.0).contains(&price) {
        return Err(IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Polymarket),
            format!("invalid Polymarket CLOB {side_name} price: {price}"),
        ));
    }
    let size = parser.optional_f64_from(best_level, "size")?;
    Ok((price, size))
}

fn polymarket_outcome_token_id_from_object(
    parser: &JsonPayloadParser,
    object: &Value,
    outcome_index: usize,
) -> Result<Option<String>, IngestionError> {
    for key in ["clobTokenIds", "clob_token_ids", "tokenIds"] {
        if let Some(token_ids) = parser.string_array_from(object, key)? {
            return Ok(token_ids.get(outcome_index).cloned());
        }
    }

    if let Some(token_id) = parser.optional_string_from(object, "token_id")? {
        return Ok(Some(token_id));
    }

    parser.optional_string_from(object, "tokenId")
}

fn first_nested_string_from_value(
    parser: &JsonPayloadParser,
    object: &Value,
    array_key_path: &[&str],
    key: &str,
) -> Result<Option<String>, IngestionError> {
    let mut current = object;
    for path_key in array_key_path {
        let Some(next) = current.get(*path_key) else {
            return Ok(None);
        };
        current = next;
    }
    let Some(array) = current.as_array() else {
        return Ok(None);
    };
    let Some(first) = array.first() else {
        return Ok(None);
    };
    let Some(value) = first.get(key) else {
        return Ok(None);
    };
    parser.value_to_string(value, key).map(Some)
}

fn parse_deribit_expiry_part_ts_ms(expiry: &str) -> Result<i64, IngestionError> {
    if expiry.len() == 8 && expiry.chars().all(|candidate| candidate.is_ascii_digit()) {
        let year = expiry[0..4]
            .parse::<i32>()
            .map_err(|_| malformed_deribit_expiry(expiry))?;
        let month = expiry[4..6]
            .parse::<u32>()
            .map_err(|_| malformed_deribit_expiry(expiry))?;
        let day = expiry[6..8]
            .parse::<u32>()
            .map_err(|_| malformed_deribit_expiry(expiry))?;
        return utc_midnight_ts_ms(year, month, day);
    }

    parse_deribit_short_expiry_ts_ms(expiry)
}

fn parse_deribit_option_kind_text(value: &str) -> Result<OptionKind, IngestionError> {
    match value.to_ascii_lowercase().as_str() {
        "c" | "call" => Ok(OptionKind::Call),
        "p" | "put" => Ok(OptionKind::Put),
        other => Err(IngestionError::new(
            IngestionErrorKind::Unsupported,
            Some(IngestionSource::Deribit),
            format!("unsupported Deribit option kind `{other}`"),
        )),
    }
}

fn malformed_deribit_instrument(instrument_name: &str) -> IngestionError {
    IngestionError::new(
        IngestionErrorKind::MalformedPayload,
        Some(IngestionSource::Deribit),
        format!("malformed Deribit instrument name `{instrument_name}`"),
    )
}

fn malformed_deribit_expiry(expiry: &str) -> IngestionError {
    IngestionError::new(
        IngestionErrorKind::MalformedPayload,
        Some(IngestionSource::Deribit),
        format!("malformed Deribit expiry `{expiry}`"),
    )
}

fn parse_deribit_short_expiry_ts_ms(expiry: &str) -> Result<i64, IngestionError> {
    let day_digits: String = expiry
        .chars()
        .take_while(|candidate| candidate.is_ascii_digit())
        .collect();
    let rest = &expiry[day_digits.len()..];
    if day_digits.is_empty() || rest.len() < 5 {
        return Err(IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Deribit),
            format!("malformed Deribit expiry `{expiry}`"),
        ));
    }

    let month_text = &rest[..3].to_ascii_uppercase();
    let year_text = &rest[3..];
    let day = day_digits.parse::<u32>().map_err(|error| {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Deribit),
            format!("invalid Deribit expiry day `{expiry}`: {error}"),
        )
    })?;
    let month = deribit_month_number(month_text).ok_or_else(|| {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Deribit),
            format!("invalid Deribit expiry month `{expiry}`"),
        )
    })?;
    let year_suffix = year_text.parse::<i32>().map_err(|error| {
        IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Deribit),
            format!("invalid Deribit expiry year `{expiry}`: {error}"),
        )
    })?;
    let year = if year_suffix < 100 {
        2000 + year_suffix
    } else {
        year_suffix
    };

    utc_midnight_ts_ms(year, month, day)
}

fn deribit_month_number(month_text: &str) -> Option<u32> {
    match month_text {
        "JAN" => Some(1),
        "FEB" => Some(2),
        "MAR" => Some(3),
        "APR" => Some(4),
        "MAY" => Some(5),
        "JUN" => Some(6),
        "JUL" => Some(7),
        "AUG" => Some(8),
        "SEP" => Some(9),
        "OCT" => Some(10),
        "NOV" => Some(11),
        "DEC" => Some(12),
        _ => None,
    }
}

fn utc_midnight_ts_ms(year: i32, month: u32, day: u32) -> Result<i64, IngestionError> {
    if !(1..=12).contains(&month) || !(1..=31).contains(&day) {
        return Err(IngestionError::new(
            IngestionErrorKind::MalformedPayload,
            Some(IngestionSource::Deribit),
            format!("invalid UTC date {year:04}-{month:02}-{day:02}"),
        ));
    }

    let days = days_from_civil(year, month, day);
    Ok(days * 86_400_000)
}

fn days_from_civil(year: i32, month: u32, day: u32) -> i64 {
    let year = year - i32::from(month <= 2);
    let era = if year >= 0 { year } else { year - 399 } / 400;
    let year_of_era = year - era * 400;
    let month = month as i32;
    let day = day as i32;
    let month_prime = month + if month > 2 { -3 } else { 9 };
    let day_of_year = (153 * month_prime + 2) / 5 + day - 1;
    let day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;
    (era * 146_097 + day_of_era - 719_468) as i64
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
    InvalidSchemaBatch,
    InvalidTimestampBatch,
    StorageWriterFailure,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IngestionManifestScenario {
    pub name: String,
    pub fixture: String,
    pub expected_report: String,
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
        "invalid_schema_batch" => Ok(IngestionScenarioOutcome::InvalidSchemaBatch),
        "invalid_timestamp_batch" => Ok(IngestionScenarioOutcome::InvalidTimestampBatch),
        "storage_writer_failure" => Ok(IngestionScenarioOutcome::StorageWriterFailure),
        other => Err(format!("line {line_number}: unsupported outcome `{other}`")),
    }
}

pub fn parse_ingestion_manifest(content: &str) -> Result<Vec<IngestionManifestScenario>, String> {
    let mut scenarios = Vec::new();
    let mut current_name: Option<String> = None;
    let mut current_fixture: Option<String> = None;
    let mut current_expected_report: Option<String> = None;
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
                &mut current_expected_report,
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
            "expected_report" => current_expected_report = Some(value.to_string()),
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
        &mut current_expected_report,
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
        if scenarios[..index]
            .iter()
            .any(|candidate| candidate.expected_report == scenario.expected_report)
        {
            return Err(format!(
                "duplicate ingestion scenario expected_report: {}",
                scenario.expected_report
            ));
        }
    }

    Ok(scenarios)
}

pub fn ingestion_report_from_scenario_steps(
    steps: &[IngestionScenarioStep],
) -> Result<IngestionReport, String> {
    let mut outcomes = Vec::new();

    for step in steps {
        let mut validation_report = match step.outcome {
            IngestionScenarioOutcome::Batch => {
                let mut report = ValidationReport::new(1, 1);
                report.normalized_events_accepted = 1;
                report
            }
            IngestionScenarioOutcome::MalformedBatch => {
                let mut report = ValidationReport::new(1, 1);
                report.normalized_events_rejected = 1;
                report.rejections.push(NormalizedBatchValidationError::new(
                    step.source.as_str(),
                    format!("scenario-step-{}", step.step),
                    malformed_fixture_rejection_message(step.source)?,
                ));
                report
            }
            IngestionScenarioOutcome::InvalidSchemaBatch => {
                let mut report = ValidationReport::new(1, 1);
                report.normalized_events_rejected = 1;
                report.rejections.push(NormalizedBatchValidationError::new(
                    step.source.as_str(),
                    format!("scenario-step-{}", step.step),
                    "unsupported normalized event schema_version",
                ));
                report
            }
            IngestionScenarioOutcome::InvalidTimestampBatch => {
                let mut report = ValidationReport::new(1, 1);
                report.normalized_events_rejected = 1;
                report.rejections.push(NormalizedBatchValidationError::new(
                    step.source.as_str(),
                    format!("scenario-step-{}", step.step),
                    "normalized event received_ts_ms is earlier than exchange_ts_ms",
                ));
                report
            }
            IngestionScenarioOutcome::ApiError
            | IngestionScenarioOutcome::Reconnect
            | IngestionScenarioOutcome::StorageWriterFailure => ValidationReport::new(0, 0),
        };
        validation_report.normalized_events_rejected = validation_report.rejections.len();

        outcomes.push(IngestionOutcome {
            batch: IngestionBatch::empty(step.source),
            validation_report,
        });
    }

    Ok(IngestionReport::from_outcomes(&outcomes))
}

fn malformed_fixture_rejection_message(source: IngestionSource) -> Result<&'static str, String> {
    match source {
        IngestionSource::Deribit => Ok("invalid Deribit normalized quote values"),
        IngestionSource::Polymarket => Ok("invalid Polymarket normalized quote values"),
    }
}

fn push_manifest_scenario(
    scenarios: &mut Vec<IngestionManifestScenario>,
    current_name: &mut Option<String>,
    current_fixture: &mut Option<String>,
    current_expected_report: &mut Option<String>,
    current_expected_observations: &mut Option<usize>,
    current_expected_raw_events: &mut Option<usize>,
    current_expected_normalized_events: &mut Option<usize>,
    current_expected_validation_errors: &mut Option<usize>,
    line_number: usize,
) -> Result<(), String> {
    if current_name.is_none()
        && current_fixture.is_none()
        && current_expected_report.is_none()
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
    let expected_report = current_expected_report
        .take()
        .ok_or_else(|| format!("line {line_number}: manifest scenario missing expected_report"))?;
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
        expected_report,
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
    use cryptotehnolog_common::journal::{
        EventJournalRow, EventJournalRowWriter, InMemoryEventJournal,
        InMemoryEventJournalRowWriter, JournalError, JournalErrorKind,
    };
    use cryptotehnolog_common::observations::{
        BasisObservationWriter, InMemoryBasisObservationRowWriter, InMemoryBasisObservationWriter,
        observations_from_match_decisions, write_basis_observation_rows,
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
            exchange_ts_ms: 1_779_200_000_000,
            received_ts_ms: 1_779_200_000_100,
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
                    target_expiry_ts_ms: 1_780_000_000_000,
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
                    target_expiry_ts_ms: 1_780_000_000_000,
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
            max_quote_time_skew_ms: 5_000,
            min_polymarket_liquidity_usd: 1_000.0,
            estimated_cost_probability: 0.010,
            risk_free_rate: 0.0,
            dividend_yield: 0.0,
            milliseconds_per_year: 365.25 * 24.0 * 60.0 * 60.0 * 1000.0,
        }
    }

    #[derive(Debug, Default)]
    struct FailingEventJournalRowWriter {
        attempts: usize,
    }

    impl EventJournalRowWriter for FailingEventJournalRowWriter {
        fn append_event_journal_row(&mut self, _row: EventJournalRow) -> Result<(), JournalError> {
            self.attempts += 1;
            Err(JournalError::new(
                JournalErrorKind::Storage,
                "simulated row writer failure",
            ))
        }
    }

    fn fixture_path(file_name: &str) -> std::path::PathBuf {
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("fixtures")
            .join("ingestion")
            .join(file_name)
    }

    fn normalize_json_fixture(value: &str) -> String {
        value.replace("\r\n", "\n").trim().to_string()
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
        let fixture_path = fixture_path("happy_path_batches.psv");
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
                assert!((*net_edge_probability - 0.071338).abs() < 1e-6);
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
        assert!((observation.net_edge_probability - 0.071338).abs() < 1e-6);
    }

    #[test]
    fn malformed_polymarket_batch_preserves_raw_event_without_basis_observation() {
        let fixture_path = fixture_path("malformed_polymarket_quote.psv");
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
    fn phase0_validator_rejects_unsupported_schema_after_preserving_raw_event() {
        let mut batch = deribit_batch();
        match &mut batch.market_events[0] {
            MarketEvent::DeribitOptionQuote(quote) => {
                quote.meta.schema_version = SUPPORTED_NORMALIZED_EVENT_SCHEMA_VERSION + 1;
            }
            MarketEvent::PolymarketOutcomeQuote(_) => panic!("expected Deribit quote"),
        }
        let mut client = MockIngestionClient::new(vec![MockIngestionStep::Batch(batch)]);
        let mut journal = InMemoryEventJournal::new();

        let outcome = ingest_once_with_report(
            &mut client,
            &mut journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("raw event should be preserved and validation report returned");

        assert_eq!(journal.raw_deribit_events().len(), 1);
        assert!(journal.market_events().is_empty());
        assert_eq!(outcome.validation_report.normalized_events_accepted, 0);
        assert_eq!(outcome.validation_report.normalized_events_rejected, 1);
        assert_eq!(
            outcome.validation_report.rejections[0].message,
            "unsupported normalized event schema_version"
        );
    }

    #[test]
    fn phase0_validator_rejects_received_timestamp_before_exchange_timestamp() {
        let mut batch = polymarket_batch();
        match &mut batch.market_events[0] {
            MarketEvent::PolymarketOutcomeQuote(quote) => {
                quote.meta.received_ts_ms = quote.meta.exchange_ts_ms - 1;
            }
            MarketEvent::DeribitOptionQuote(_) => panic!("expected Polymarket quote"),
        }
        let mut client = MockIngestionClient::new(vec![MockIngestionStep::Batch(batch)]);
        let mut journal = InMemoryEventJournal::new();

        let outcome = ingest_once_with_report(
            &mut client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("raw event should be preserved and validation report returned");

        assert_eq!(journal.raw_polymarket_events().len(), 1);
        assert!(journal.market_events().is_empty());
        assert_eq!(outcome.validation_report.normalized_events_accepted, 0);
        assert_eq!(outcome.validation_report.normalized_events_rejected, 1);
        assert_eq!(
            outcome.validation_report.rejections[0].message,
            "normalized event received_ts_ms is earlier than exchange_ts_ms"
        );
    }

    #[test]
    fn ingestion_manifest_lists_current_orchestration_scenarios() {
        let manifest_path = fixture_path("manifest.toml");

        let scenarios =
            load_ingestion_manifest(&manifest_path).expect("ingestion manifest should parse");

        assert_eq!(scenarios.len(), 3);
        assert_eq!(scenarios[0].name, "happy_path_batches");
        assert_eq!(
            scenarios[0].expected_report,
            "fixtures/ingestion/happy_path_report.json"
        );
        assert_eq!(scenarios[0].expected_observations, 1);
        assert_eq!(scenarios[0].expected_raw_events, 2);
        assert_eq!(scenarios[0].expected_normalized_events, 2);
        assert_eq!(scenarios[0].expected_validation_errors, 0);
        assert_eq!(scenarios[1].name, "malformed_polymarket_quote");
        assert_eq!(
            scenarios[1].expected_report,
            "fixtures/ingestion/malformed_polymarket_quote_report.json"
        );
        assert_eq!(scenarios[1].expected_observations, 0);
        assert_eq!(scenarios[1].expected_raw_events, 2);
        assert_eq!(scenarios[1].expected_normalized_events, 1);
        assert_eq!(scenarios[1].expected_validation_errors, 1);
        assert_eq!(scenarios[2].name, "schema_timestamp_invalid_batches");
        assert_eq!(
            scenarios[2].expected_report,
            "fixtures/ingestion/schema_timestamp_invalid_report.json"
        );
        assert_eq!(scenarios[2].expected_observations, 0);
        assert_eq!(scenarios[2].expected_raw_events, 2);
        assert_eq!(scenarios[2].expected_normalized_events, 0);
        assert_eq!(scenarios[2].expected_validation_errors, 2);
    }

    #[test]
    fn ingestion_report_matches_semantic_golden_json() {
        let mut happy_deribit_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut happy_polymarket_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(polymarket_batch())]);
        let mut happy_journal = InMemoryEventJournal::new();
        let happy_deribit = ingest_once_with_report(
            &mut happy_deribit_client,
            &mut happy_journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("happy Deribit batch should ingest");
        let happy_polymarket = ingest_once_with_report(
            &mut happy_polymarket_client,
            &mut happy_journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("happy Polymarket batch should ingest");
        let happy_report = IngestionReport::from_outcomes(&[happy_deribit, happy_polymarket]);
        let expected_happy =
            std::fs::read_to_string(fixture_path("happy_path_report.json")).unwrap();
        assert_eq!(
            happy_report.to_json(),
            normalize_json_fixture(&expected_happy)
        );

        let mut malformed_deribit_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut malformed_polymarket_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(malformed_polymarket_batch())]);
        let mut malformed_journal = InMemoryEventJournal::new();
        let malformed_deribit = ingest_once_with_report(
            &mut malformed_deribit_client,
            &mut malformed_journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("malformed scenario Deribit batch should ingest");
        let malformed_polymarket = ingest_once_with_report(
            &mut malformed_polymarket_client,
            &mut malformed_journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("malformed scenario Polymarket batch should produce report");
        let malformed_report =
            IngestionReport::from_outcomes(&[malformed_deribit, malformed_polymarket]);
        let expected_malformed =
            std::fs::read_to_string(fixture_path("malformed_polymarket_quote_report.json"))
                .unwrap();
        assert_eq!(
            malformed_report.to_json(),
            normalize_json_fixture(&expected_malformed)
        );
    }

    #[test]
    fn deribit_live_skeleton_builds_ticker_url_without_network() {
        let client =
            DeribitLiveIngestionClient::new("https://www.deribit.com/", "ETH-20260601-3000-C");

        assert_eq!(
            client.ticker_url(),
            "https://www.deribit.com/api/v2/public/ticker?instrument_name=ETH-20260601-3000-C"
        );
    }

    #[test]
    fn deribit_instrument_name_parses_real_and_fixture_shapes() {
        let real = DeribitInstrumentName::parse("ETH-1JUN26-3000-C")
            .expect("real Deribit instrument name should parse");
        assert_eq!(real.raw(), "ETH-1JUN26-3000-C");
        assert_eq!(real.underlying, "ETH");
        assert_eq!(real.expiry_ts_ms, 1_780_272_000_000);
        assert_eq!(real.strike, 3000.0);
        assert_eq!(real.option_kind, OptionKind::Call);

        let fixture = DeribitInstrumentName::parse("ETH-20260601-3000-P")
            .expect("fixture-style Deribit instrument name should parse");
        assert_eq!(fixture.expiry_ts_ms, 1_780_272_000_000);
        assert_eq!(fixture.option_kind, OptionKind::Put);
    }

    #[test]
    fn deribit_instrument_name_rejects_malformed_boundary_values() {
        for raw in [
            "ETH-1JUN26-C",
            "ETH-1JUN26-0-C",
            "ETH-1JUN26--C",
            "ETH-1JUN26-3000-X",
            "ETH-99XYZ26-3000-C",
        ] {
            let error = DeribitInstrumentName::parse(raw)
                .expect_err("malformed Deribit instrument should fail");
            assert_eq!(error.kind, IngestionErrorKind::MalformedPayload);
        }
    }

    #[test]
    fn deribit_live_skeleton_parses_fixture_payload_without_network() {
        let client =
            DeribitLiveIngestionClient::new("https://www.deribit.com", "ETH-20260601-3000-C");
        let payload =
            std::fs::read_to_string(fixture_path("deribit_ticker_eth_3000_call.json")).unwrap();

        let batch = client
            .parse_ticker_payload(
                &payload,
                &IngestionConfig::phase0_deribit("https://www.deribit.com"),
                1_779_200_000_100,
            )
            .expect("fixture payload should parse");

        assert_eq!(batch.source, IngestionSource::Deribit);
        assert_eq!(batch.raw_events.len(), 1);
        assert_eq!(batch.market_events.len(), 1);
        assert_eq!(batch.raw_events[0].source(), IngestionSource::Deribit);
        let MarketEvent::DeribitOptionQuote(quote) = &batch.market_events[0] else {
            panic!("expected Deribit option quote");
        };
        assert_eq!(quote.meta.instrument_id, "ETH-20260601-3000-C");
        assert_eq!(quote.expiry_ts_ms, 1_780_272_000_000);
        assert_eq!(quote.strike, 3000.0);
        assert_eq!(quote.option_kind, OptionKind::Call);
        assert_eq!(quote.underlying_price, 3100.0);
        assert_eq!(quote.bid, 0.12);
        assert_eq!(quote.ask, 0.13);
        assert_eq!(quote.mark_iv, 0.62);
    }

    #[test]
    fn deribit_live_skeleton_parses_json_rpc_result_and_real_option_expiry() {
        let client =
            DeribitLiveIngestionClient::new("https://www.deribit.com", "ETH-1JUN26-3000-C");
        let payload = r#"{
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "instrument_name": "ETH-1JUN26-3000-C",
                "timestamp": 1779200000000,
                "underlying_price": 3100.0,
                "best_bid_price": 0.12,
                "best_ask_price": 0.13,
                "mark_iv": 0.62
            }
        }"#;

        let batch = client
            .parse_ticker_payload(
                payload,
                &IngestionConfig::phase0_deribit("https://www.deribit.com"),
                1_779_200_000_100,
            )
            .expect("real-shaped Deribit JSON-RPC payload should parse");

        let MarketEvent::DeribitOptionQuote(quote) = &batch.market_events[0] else {
            panic!("expected Deribit option quote");
        };
        assert_eq!(quote.meta.instrument_id, "ETH-1JUN26-3000-C");
        assert_eq!(quote.underlying, "ETH");
        assert_eq!(quote.expiry_ts_ms, 1_780_272_000_000);
        assert_eq!(quote.strike, 3000.0);
        assert_eq!(quote.option_kind, OptionKind::Call);
    }

    #[test]
    fn deribit_discovery_selects_nearest_option_candidate() {
        let payload = r#"{
            "jsonrpc": "2.0",
            "id": 1,
            "result": [
                {
                    "instrument_name": "ETH-29MAY26-3000-C",
                    "base_currency": "ETH",
                    "expiration_timestamp": 1779993600000,
                    "strike": 3000.0,
                    "option_type": "call"
                },
                {
                    "instrument_name": "ETH-1JUN26-3000-C",
                    "base_currency": "ETH",
                    "expiration_timestamp": 1780272000000,
                    "strike": 3000.0,
                    "option_type": "call"
                },
                {
                    "instrument_name": "ETH-1JUN26-3500-C",
                    "base_currency": "ETH",
                    "expiration_timestamp": 1780272000000,
                    "strike": 3500.0,
                    "option_type": "call"
                }
            ]
        }"#;

        let discovered = DeribitLiveIngestionClient::discover_option_from_payload(
            payload,
            &DeribitOptionDiscoveryCriteria::phase0_eth_call_3000_june_2026(),
        )
        .expect("discovery payload should produce a candidate");

        assert_eq!(discovered.instrument_name, "ETH-1JUN26-3000-C");
        assert_eq!(discovered.expiry_ts_ms, 1_780_272_000_000);
        assert_eq!(discovered.strike, 3000.0);
        assert_eq!(discovered.option_kind, OptionKind::Call);
    }

    #[test]
    fn deribit_discovery_falls_back_to_instrument_name_metadata() {
        let payload = r#"{
            "result": [
                { "instrument_name": "ETH-1JUN26-3000-C" }
            ]
        }"#;

        let discovered = DeribitLiveIngestionClient::discover_option_from_payload(
            payload,
            &DeribitOptionDiscoveryCriteria::phase0_eth_call_3000_june_2026(),
        )
        .expect("instrument_name should be enough for discovery fallback");

        assert_eq!(discovered.instrument_name, "ETH-1JUN26-3000-C");
        assert_eq!(discovered.underlying, "ETH");
        assert_eq!(discovered.expiry_ts_ms, 1_780_272_000_000);
    }

    #[test]
    fn deribit_live_skeleton_poll_once_does_not_perform_network_calls() {
        let mut client =
            DeribitLiveIngestionClient::new("https://www.deribit.com", "ETH-20260601-3000-C");

        let error = client
            .poll_once(&IngestionConfig::phase0_deribit("https://www.deribit.com"))
            .expect_err("skeleton must not perform network calls");

        assert_eq!(error.kind, IngestionErrorKind::NotImplemented);
    }

    #[test]
    fn polymarket_live_skeleton_builds_gamma_market_url_without_network() {
        let client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com/",
            "eth-above-3000-june-1",
            "Yes",
        );

        assert_eq!(
            client.gamma_market_url(),
            "https://gamma-api.polymarket.com/markets/slug/eth-above-3000-june-1"
        );
    }

    #[test]
    fn polymarket_live_skeleton_builds_clob_book_url_without_network() {
        let client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com",
            "eth-above-3000-june-1",
            "Yes",
        )
        .with_outcome_token_id("1234567890");

        assert_eq!(
            client
                .clob_book_url("https://clob.polymarket.com/")
                .expect("token id should build CLOB book URL"),
            "https://clob.polymarket.com/book?token_id=1234567890"
        );
    }

    #[test]
    fn polymarket_live_skeleton_parses_fixture_payload_without_network() {
        let client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com",
            "eth-above-3000-june-1",
            "Yes",
        );
        let payload =
            std::fs::read_to_string(fixture_path("polymarket_gamma_eth_above_3000.json")).unwrap();

        let batch = client
            .parse_gamma_market_payload(
                &payload,
                &IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com"),
                1_779_200_000_200,
            )
            .expect("fixture payload should parse");

        assert_eq!(batch.source, IngestionSource::Polymarket);
        assert_eq!(batch.raw_events.len(), 1);
        assert_eq!(batch.market_events.len(), 1);
        assert_eq!(batch.raw_events[0].source(), IngestionSource::Polymarket);
        let MarketEvent::PolymarketOutcomeQuote(quote) = &batch.market_events[0] else {
            panic!("expected Polymarket outcome quote");
        };
        assert_eq!(quote.meta.instrument_id, "eth-above-3000-june-1");
        assert_eq!(quote.event_slug, "eth-above-3000");
        assert_eq!(quote.market_slug, "eth-above-3000-june-1");
        assert_eq!(quote.outcome, "Yes");
        assert_eq!(quote.bid_probability, 0.51);
        assert_eq!(quote.ask_probability, 0.53);
        assert_eq!(quote.liquidity_usd, 10_000.0);
    }

    #[test]
    fn polymarket_live_skeleton_parses_real_gamma_market_shape() {
        let client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com",
            "eth-above-3000-june-1",
            "Yes",
        );
        let payload = r#"{
            "slug": "eth-above-3000-june-1",
            "outcomes": "[\"Yes\", \"No\"]",
            "outcomePrices": "[\"0.51\", \"0.49\"]",
            "liquidity": "10000.0",
            "events": [
                { "slug": "eth-above-3000" }
            ],
            "updatedAtMillis": "1779200000000"
        }"#;

        let batch = client
            .parse_gamma_market_payload(
                payload,
                &IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com"),
                1_779_200_000_200,
            )
            .expect("real-shaped Polymarket Gamma market payload should parse");

        let MarketEvent::PolymarketOutcomeQuote(quote) = &batch.market_events[0] else {
            panic!("expected Polymarket outcome quote");
        };
        assert_eq!(quote.event_slug, "eth-above-3000");
        assert_eq!(quote.market_slug, "eth-above-3000-june-1");
        assert_eq!(quote.outcome, "Yes");
        assert_eq!(quote.bid_probability, 0.51);
        assert_eq!(quote.ask_probability, 0.51);
        assert_eq!(quote.liquidity_usd, 10_000.0);
    }

    #[test]
    fn polymarket_live_skeleton_parses_gamma_plus_clob_book_fixture_without_network() {
        let client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com",
            "eth-above-3000-june-1",
            "Yes",
        )
        .with_outcome_token_id("1234567890");
        let gamma_payload = std::fs::read_to_string(fixture_path(
            "polymarket_gamma_eth_above_3000_with_clob_token.json",
        ))
        .expect("Gamma fixture should exist");
        let clob_payload =
            std::fs::read_to_string(fixture_path("polymarket_clob_book_eth_above_3000_yes.json"))
                .expect("CLOB fixture should exist");

        let batch = client
            .parse_gamma_market_with_clob_book_payload(
                &gamma_payload,
                &clob_payload,
                &IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com"),
                1_779_200_000_200,
            )
            .expect("Gamma + CLOB fixtures should parse");

        assert_eq!(batch.source, IngestionSource::Polymarket);
        assert_eq!(batch.raw_events.len(), 2);
        assert_eq!(batch.market_events.len(), 1);
        let RawIngestionEvent::Polymarket(clob_raw) = &batch.raw_events[1] else {
            panic!("expected Polymarket CLOB raw event");
        };
        assert_eq!(clob_raw.api_layer, PolymarketApiLayer::Clob);
        assert_eq!(clob_raw.meta.instrument_id, "1234567890");

        let MarketEvent::PolymarketOutcomeQuote(quote) = &batch.market_events[0] else {
            panic!("expected Polymarket outcome quote");
        };
        assert_eq!(quote.market_slug, "eth-above-3000-june-1");
        assert_eq!(quote.bid_probability, 0.49);
        assert_eq!(quote.ask_probability, 0.54);
        assert_eq!(quote.meta.exchange_ts_ms, 1_779_200_000_100);
    }

    #[test]
    fn polymarket_clob_book_parser_rejects_crossed_book_without_panic() {
        let payload = r#"{
            "asset_id": "1234567890",
            "bids": [{ "price": "0.56", "size": "100" }],
            "asks": [{ "price": "0.54", "size": "100" }]
        }"#;

        let error = PolymarketLiveIngestionClient::parse_clob_book_payload(payload)
            .expect_err("crossed CLOB book should return IngestionError");

        assert_eq!(error.kind, IngestionErrorKind::MalformedPayload);
        assert!(error.message.contains("bid/ask crossed"));
    }

    #[test]
    fn polymarket_live_skeleton_rejects_missing_outcomes_without_panic() {
        let client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com",
            "eth-above-3000-june-1",
            "Yes",
        );
        let payload = r#"{
            "slug": "eth-above-3000-june-1",
            "outcomePrices": "[\"0.51\", \"0.49\"]",
            "liquidity": "10000.0"
        }"#;

        let error = client
            .parse_gamma_market_payload(
                payload,
                &IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com"),
                1_779_200_000_200,
            )
            .expect_err("missing outcomes should return IngestionError");

        assert_eq!(error.kind, IngestionErrorKind::MalformedPayload);
        assert!(error.message.contains("outcome `Yes` not found"));
    }

    #[test]
    fn polymarket_live_skeleton_rejects_outcome_price_mismatch_without_panic() {
        let client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com",
            "eth-above-3000-june-1",
            "No",
        );
        let payload = r#"{
            "slug": "eth-above-3000-june-1",
            "outcomes": "[\"Yes\", \"No\"]",
            "outcomePrices": "[\"0.51\"]",
            "liquidity": "10000.0"
        }"#;

        let error = client
            .parse_gamma_market_payload(
                payload,
                &IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com"),
                1_779_200_000_200,
            )
            .expect_err("short outcomePrices should return IngestionError");

        assert_eq!(error.kind, IngestionErrorKind::MalformedPayload);
        assert!(
            error
                .message
                .contains("malformed Polymarket field `outcomePrices`")
        );
    }

    #[test]
    fn polymarket_discovery_selects_liquid_matching_market() {
        let payload = r#"[
            {
                "slug": "btc-above-3000-june-1",
                "question": "Will BTC be above $3000 on June 1?",
                "outcomes": "[\"Yes\", \"No\"]",
                "outcomePrices": "[\"0.99\", \"0.01\"]",
                "liquidity": "20000",
                "active": true,
                "closed": false
            },
            {
                "slug": "eth-above-3000-june-1-low-liquidity",
                "question": "Will ETH be above $3000 on June 1?",
                "outcomes": "[\"Yes\", \"No\"]",
                "outcomePrices": "[\"0.51\", \"0.49\"]",
                "liquidity": "100",
                "active": true,
                "closed": false
            },
            {
                "slug": "eth-above-3000-june-1",
                "question": "Will ETH be above $3000 on June 1?",
                "outcomes": "[\"Yes\", \"No\"]",
                "outcomePrices": "[\"0.51\", \"0.49\"]",
                "clobTokenIds": "[\"1234567890\", \"0987654321\"]",
                "liquidity": "10000",
                "active": true,
                "closed": false,
                "events": [{ "slug": "eth-above-3000" }]
            }
        ]"#;

        let discovered = PolymarketLiveIngestionClient::discover_market_from_payload(
            payload,
            &PolymarketMarketDiscoveryCriteria::phase0_eth_above_3000_yes(),
        )
        .expect("discovery payload should produce a Polymarket candidate");

        assert_eq!(discovered.market_slug, "eth-above-3000-june-1");
        assert_eq!(discovered.event_slug, "eth-above-3000");
        assert_eq!(discovered.outcome, "Yes");
        assert_eq!(discovered.outcome_token_id.as_deref(), Some("1234567890"));
        assert_eq!(discovered.liquidity_usd, 10_000.0);
    }

    #[test]
    fn polymarket_discovery_rejects_closed_or_missing_outcome_markets() {
        let payload = r#"[
            {
                "slug": "eth-above-3000-closed",
                "question": "Will ETH be above $3000?",
                "outcomes": "[\"Yes\", \"No\"]",
                "liquidity": "10000",
                "active": true,
                "closed": true
            },
            {
                "slug": "eth-above-3000-no-yes",
                "question": "Will ETH be above $3000?",
                "outcomes": "[\"Up\", \"Down\"]",
                "liquidity": "10000",
                "active": true,
                "closed": false
            }
        ]"#;

        let error = PolymarketLiveIngestionClient::discover_market_from_payload(
            payload,
            &PolymarketMarketDiscoveryCriteria::phase0_eth_above_3000_yes(),
        )
        .expect_err("closed or incompatible markets should not produce a candidate");

        assert_eq!(error.kind, IngestionErrorKind::MalformedPayload);
        assert!(error.message.contains("no Polymarket market candidate"));
    }

    #[test]
    fn polymarket_live_skeleton_poll_once_does_not_perform_network_calls() {
        let mut client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com",
            "eth-above-3000-june-1",
            "Yes",
        );

        let error = client
            .poll_once(&IngestionConfig::phase0_polymarket(
                "https://gamma-api.polymarket.com",
            ))
            .expect_err("skeleton must not perform network calls");

        assert_eq!(error.kind, IngestionErrorKind::NotImplemented);
    }

    #[test]
    fn disabled_http_transport_blocks_default_live_fetch() {
        let client =
            DeribitLiveIngestionClient::new("https://www.deribit.com", "ETH-20260601-3000-C");

        let error = client
            .fetch_ticker_with_transport(
                &DisabledHttpTransport,
                &IngestionConfig::phase0_deribit("https://www.deribit.com"),
                1_779_200_000_100,
            )
            .expect_err("disabled transport must not perform HTTP calls");

        assert_eq!(error.kind, IngestionErrorKind::NotImplemented);
        assert_eq!(error.source, Some(IngestionSource::Deribit));
    }

    #[test]
    fn fixture_http_transport_feeds_live_skeletons_without_network() {
        let deribit_client =
            DeribitLiveIngestionClient::new("https://www.deribit.com", "ETH-20260601-3000-C");
        let polymarket_client = PolymarketLiveIngestionClient::new(
            "https://gamma-api.polymarket.com",
            "eth-above-3000-june-1",
            "Yes",
        );
        let deribit_payload =
            std::fs::read_to_string(fixture_path("deribit_ticker_eth_3000_call.json")).unwrap();
        let polymarket_payload =
            std::fs::read_to_string(fixture_path("polymarket_gamma_eth_above_3000.json")).unwrap();
        let transport = FixtureHttpTransport::new()
            .with_response(deribit_client.ticker_url(), deribit_payload)
            .with_response(polymarket_client.gamma_market_url(), polymarket_payload);

        let deribit_batch = deribit_client
            .fetch_ticker_with_transport(
                &transport,
                &IngestionConfig::phase0_deribit("https://www.deribit.com"),
                1_779_200_000_100,
            )
            .expect("Deribit fixture response should produce a batch");
        let polymarket_batch = polymarket_client
            .fetch_gamma_market_with_transport(
                &transport,
                &IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com"),
                1_779_200_000_200,
            )
            .expect("Polymarket fixture response should produce a batch");

        assert_eq!(deribit_batch.raw_events.len(), 1);
        assert_eq!(deribit_batch.market_events.len(), 1);
        assert_eq!(polymarket_batch.raw_events.len(), 1);
        assert_eq!(polymarket_batch.market_events.len(), 1);

        let mut journal = InMemoryEventJournal::new();
        let mut deribit_ingestion_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch)]);
        let mut polymarket_ingestion_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(polymarket_batch)]);

        ingest_once_with_report(
            &mut deribit_ingestion_client,
            &mut journal,
            &IngestionConfig::phase0_deribit("https://www.deribit.com"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("Deribit fixture transport batch should ingest");
        ingest_once_with_report(
            &mut polymarket_ingestion_client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("Polymarket fixture transport batch should ingest");

        assert_eq!(journal.raw_deribit_events().len(), 1);
        assert_eq!(journal.raw_polymarket_events().len(), 1);
        assert_eq!(journal.market_events().len(), 2);

        let row_event_types: Vec<&str> = journal
            .event_journal_rows()
            .iter()
            .map(|row| row.event_type.as_str())
            .collect();
        assert_eq!(
            row_event_types,
            vec![
                "raw_deribit_event",
                "deribit_option_quote",
                "raw_polymarket_event",
                "polymarket_outcome_quote",
            ]
        );
        assert_eq!(
            journal.event_journal_rows()[0].instrument_id,
            "ETH-20260601-3000-C"
        );
        assert_eq!(
            journal.event_journal_rows()[3].instrument_id,
            "eth-above-3000-june-1"
        );

        let replay_events = journal
            .read_events_for_replay(ReplayEventFilter {
                start_ts_ms: 0,
                end_ts_ms: 1_781_000_000_000,
                event_types: vec![],
                instrument_ids: vec![],
                config_version: Some("phase0-ingestion".to_string()),
            })
            .expect("journal rows should still produce replay events");
        let config = probability_basis_config();
        let decisions = match_from_market_events(&replay_events, &config);
        let observations = observations_from_match_decisions(&decisions, &config);

        assert_eq!(decisions.len(), 1);
        assert_eq!(observations.len(), 1);
        assert_eq!(
            observations[0].event_id,
            "probability-basis:market-deribit-ticker:ETH-20260601-3000-C:1779200000000:market-polymarket-gamma:eth-above-3000-june-1:Yes:1779200000000"
        );
        assert!(observations[0].survives_costs);
    }

    #[test]
    fn ingestion_can_mirror_events_to_event_journal_row_writer() {
        let mut deribit_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut polymarket_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(polymarket_batch())]);
        let mut journal = InMemoryEventJournal::new();
        let mut row_writer = InMemoryEventJournalRowWriter::new();

        ingest_once_with_report_and_row_writer(
            &mut deribit_client,
            &mut journal,
            &mut row_writer,
            &IngestionConfig::phase0_deribit("mock://deribit"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("Deribit batch should ingest and mirror rows");
        ingest_once_with_report_and_row_writer(
            &mut polymarket_client,
            &mut journal,
            &mut row_writer,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("Polymarket batch should ingest and mirror rows");

        assert_eq!(journal.event_journal_rows(), row_writer.rows());
        assert_eq!(row_writer.rows().len(), 4);
        assert_eq!(row_writer.rows()[0].event_type, "raw_deribit_event");
        assert_eq!(row_writer.rows()[1].event_type, "deribit_option_quote");
        assert_eq!(row_writer.rows()[2].event_type, "raw_polymarket_event");
        assert_eq!(row_writer.rows()[3].event_type, "polymarket_outcome_quote");

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
        let observations = observations_from_match_decisions(&decisions, &config);

        assert_eq!(observations.len(), 1);
        assert!(observations[0].survives_costs);
    }

    #[test]
    fn ingestion_to_matcher_to_basis_observation_row_writer_flow_is_offline() {
        let mut deribit_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut polymarket_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(polymarket_batch())]);
        let mut journal = InMemoryEventJournal::new();

        ingest_once_with_report(
            &mut deribit_client,
            &mut journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("Deribit batch should ingest");
        ingest_once_with_report(
            &mut polymarket_client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("Polymarket batch should ingest");

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
        let observations = observations_from_match_decisions(&decisions, &config);
        let mut row_writer = InMemoryBasisObservationRowWriter::new();

        write_basis_observation_rows(&observations, &mut row_writer)
            .expect("basis observation rows should append");

        assert_eq!(observations.len(), 1);
        assert_eq!(row_writer.rows().len(), 1);
        assert_eq!(row_writer.rows()[0].event_id, observations[0].event_id);
        assert_eq!(
            row_writer.rows()[0].deribit_instrument_id,
            "ETH-20260601-3000-C"
        );
        assert_eq!(
            row_writer.rows()[0].polymarket_market_slug,
            "eth-above-3000-june-1"
        );
        assert!(row_writer.rows()[0].survives_costs);
    }

    #[test]
    fn phase0_pipeline_report_counts_offline_vertical_slice() {
        let mut deribit_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut polymarket_client =
            MockIngestionClient::new(vec![MockIngestionStep::Batch(polymarket_batch())]);
        let mut journal = InMemoryEventJournal::new();

        ingest_once_with_report(
            &mut deribit_client,
            &mut journal,
            &IngestionConfig::phase0_deribit("mock://deribit"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("Deribit batch should ingest");
        ingest_once_with_report(
            &mut polymarket_client,
            &mut journal,
            &IngestionConfig::phase0_polymarket("mock://polymarket"),
            &Phase0NormalizedBatchValidator,
        )
        .expect("Polymarket batch should ingest");

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
        let observations = observations_from_match_decisions(&decisions, &config);
        let mut observation_row_writer = InMemoryBasisObservationRowWriter::new();
        write_basis_observation_rows(&observations, &mut observation_row_writer)
            .expect("basis observation rows should append");

        let report = Phase0PipelineReport::from_counts(
            journal.raw_deribit_events().len() + journal.raw_polymarket_events().len(),
            journal.market_events().len(),
            journal.event_journal_rows().len(),
            decisions.len(),
            observations.len(),
            observation_row_writer.rows().len(),
        );

        assert_eq!(
            report,
            Phase0PipelineReport {
                schema_version: 1,
                status: Phase0PipelineReportStatus::Ok,
                raw_events: 2,
                normalized_events: 2,
                journal_rows: 4,
                match_decisions: 1,
                observations: 1,
                observation_rows: 1,
                error_stage: None,
                error_message: None,
            }
        );
        let json: serde_json::Value =
            serde_json::from_str(&report.to_json().expect("report should serialize"))
                .expect("report JSON should parse");
        assert_eq!(json["raw_events"], 2);
        assert_eq!(json["observation_rows"], 1);
    }

    #[test]
    fn phase0_pipeline_report_matches_semantic_golden_json() {
        let report = phase0_pipeline_report_from_happy_path()
            .expect("phase 0 pipeline happy path should produce report");
        let golden_path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../fixtures/phase0_pipeline/golden_report.json"
        );
        let golden_json =
            fs::read_to_string(golden_path).expect("phase 0 pipeline golden JSON should exist");
        let expected: Phase0PipelineReport =
            serde_json::from_str(&golden_json).expect("phase 0 pipeline golden JSON should parse");

        assert_eq!(report, expected);
    }

    #[test]
    fn phase0_pipeline_invalid_normalized_event_preserves_raw_without_observation() {
        let fixture_path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../fixtures/phase0_pipeline/invalid_normalized_event_preserves_raw_but_no_observation.psv"
        );
        let golden_path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../fixtures/phase0_pipeline/invalid_normalized_event_preserves_raw_but_no_observation_report.json"
        );
        let steps = load_ingestion_scenario(Path::new(fixture_path))
            .expect("phase 0 invalid normalized event fixture should parse");
        let report = phase0_pipeline_report_from_scenario_steps(&steps)
            .expect("phase 0 invalid normalized event fixture should produce report");
        let golden_json =
            fs::read_to_string(golden_path).expect("phase 0 invalid golden JSON should exist");
        let expected: Phase0PipelineReport =
            serde_json::from_str(&golden_json).expect("phase 0 invalid golden JSON should parse");

        assert_eq!(report, expected);
        assert_eq!(report.raw_events, 2);
        assert_eq!(report.status, Phase0PipelineReportStatus::Ok);
        assert_eq!(report.normalized_events, 1);
        assert_eq!(report.journal_rows, 3);
        assert_eq!(report.observations, 0);
        assert_eq!(report.observation_rows, 0);
    }

    #[test]
    fn phase0_pipeline_storage_writer_failure_preserves_reported_failure() {
        let fixture_path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../fixtures/phase0_pipeline/storage_writer_failure_preserves_reported_failure.psv"
        );
        let steps = load_ingestion_scenario(Path::new(fixture_path))
            .expect("phase 0 storage writer failure fixture should parse");
        let report = phase0_pipeline_report_from_scenario_steps(&steps)
            .expect("phase 0 storage writer failure fixture should produce report");

        assert_eq!(report.status, Phase0PipelineReportStatus::Error);
        assert_eq!(report.raw_events, 2);
        assert_eq!(report.normalized_events, 2);
        assert_eq!(report.journal_rows, 4);
        assert_eq!(report.match_decisions, 1);
        assert_eq!(report.observations, 1);
        assert_eq!(report.observation_rows, 0);
        assert_eq!(
            report.error_stage.as_deref(),
            Some("basis_observation_row_writer")
        );
        assert!(report.error_message.as_deref().is_some_and(|message| {
            message.contains("simulated basis_observation row writer failure")
        }));
    }

    #[test]
    fn row_writer_failure_returns_journal_write_error_without_panic() {
        let mut client = MockIngestionClient::new(vec![MockIngestionStep::Batch(deribit_batch())]);
        let mut journal = InMemoryEventJournal::new();
        let mut row_writer = FailingEventJournalRowWriter::default();

        let error = ingest_once_with_report_and_row_writer(
            &mut client,
            &mut journal,
            &mut row_writer,
            &IngestionConfig::phase0_deribit("mock://deribit"),
            &Phase0NormalizedBatchValidator,
        )
        .expect_err("row writer storage failure should be returned as IngestionError");

        assert_eq!(error.kind, IngestionErrorKind::JournalWrite);
        assert_eq!(error.source, Some(IngestionSource::Deribit));
        assert!(error.message.contains("simulated row writer failure"));
        assert_eq!(row_writer.attempts, 1);
        assert_eq!(journal.raw_deribit_events().len(), 1);
        assert!(journal.market_events().is_empty());
    }

    #[test]
    fn live_ingestion_probe_report_captures_success_without_network() {
        let transport =
            FixtureHttpTransport::new().with_response("https://example.test/ok", "{\"ok\":true}");

        let report = probe_live_http_endpoint("Example", "https://example.test/ok", &transport);

        assert!(report.is_ok());
        assert_eq!(report.endpoint, "Example");
        assert_eq!(report.url, "https://example.test/ok");
        assert_eq!(report.status, "ok");
        assert_eq!(report.payload_bytes, 11);
        assert_eq!(report.error_kind, None);
        assert_eq!(report.error_message, None);
        assert!(report.to_json().contains("\"status\":\"ok\""));
    }

    #[test]
    fn live_ingestion_probe_report_captures_error_without_network() {
        let report = probe_live_http_endpoint(
            "Disabled",
            "https://example.test/nope",
            &DisabledHttpTransport,
        );

        assert!(!report.is_ok());
        assert_eq!(report.status, "error");
        assert_eq!(report.payload_bytes, 0);
        assert_eq!(report.error_kind, Some(IngestionErrorKind::NotImplemented));
        assert!(report.error_message.as_ref().unwrap().contains("disabled"));
        assert!(probe_reports_to_json(&[report]).contains("\"error_kind\":\"NotImplemented\""));
    }

    #[cfg(feature = "network-integration")]
    #[test]
    fn reqwest_http_transport_can_be_constructed_when_feature_enabled() {
        let transport = ReqwestHttpTransport::new(1_000)
            .expect("feature-gated reqwest transport should construct without network calls");

        let _ = transport;
    }

    #[test]
    fn ingestion_manifest_rejects_duplicate_names_and_fixtures() {
        let duplicate_name = r#"
[[scenario]]
name = "same"
fixture = "fixtures/ingestion/a.psv"
expected_report = "fixtures/ingestion/a_report.json"
expected_observations = 1
expected_raw_events = 1
expected_normalized_events = 1
expected_validation_errors = 0

[[scenario]]
name = "same"
fixture = "fixtures/ingestion/b.psv"
expected_report = "fixtures/ingestion/b_report.json"
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
expected_report = "fixtures/ingestion/a_report.json"
expected_observations = 1
expected_raw_events = 1
expected_normalized_events = 1
expected_validation_errors = 0

[[scenario]]
name = "b"
fixture = "fixtures/ingestion/same.psv"
expected_report = "fixtures/ingestion/b_report.json"
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

        let duplicate_report = r#"
[[scenario]]
name = "a"
fixture = "fixtures/ingestion/a.psv"
expected_report = "fixtures/ingestion/same_report.json"
expected_observations = 1
expected_raw_events = 1
expected_normalized_events = 1
expected_validation_errors = 0

[[scenario]]
name = "b"
fixture = "fixtures/ingestion/b.psv"
expected_report = "fixtures/ingestion/same_report.json"
expected_observations = 0
expected_raw_events = 1
expected_normalized_events = 0
expected_validation_errors = 1
"#;
        assert!(
            parse_ingestion_manifest(duplicate_report)
                .unwrap_err()
                .contains("duplicate ingestion scenario expected_report")
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
