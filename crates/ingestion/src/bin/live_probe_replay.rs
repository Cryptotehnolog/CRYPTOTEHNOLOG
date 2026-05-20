#[cfg(feature = "network-integration")]
use std::process;

#[cfg(feature = "network-integration")]
use std::time::{Instant, SystemTime, UNIX_EPOCH};

#[cfg(feature = "network-integration")]
use cryptotehnolog_common::events::{
    EventMeta, MarketEvent, PolymarketApiLayer, RawDeribitEvent, RawPolymarketEvent,
    ReplayEventFilter,
};
#[cfg(feature = "network-integration")]
use cryptotehnolog_common::journal::{EventJournal, InMemoryEventJournal};
#[cfg(feature = "network-integration")]
use cryptotehnolog_common::observations::observations_from_match_decisions;
#[cfg(feature = "network-integration")]
use cryptotehnolog_common::probability_basis::{
    MatchDecision, PRICING_MODEL_VERSION, ProbabilityBasisConfig, match_from_market_events,
};
#[cfg(feature = "network-integration")]
use cryptotehnolog_ingestion::{
    DeribitLiveIngestionClient, IngestionBatch, IngestionConfig, IngestionError, IngestionOutcome,
    IngestionReport, IngestionSource, LiveHttpTransport, LiveIngestionProbeReport,
    MockIngestionClient, MockIngestionStep, Phase0NormalizedBatchValidator,
    PolymarketLiveIngestionClient, ReqwestHttpTransport, ingest_once_with_report,
};

#[cfg(feature = "network-integration")]
const CONFIG_VERSION: &str = "phase0-ingestion";

#[cfg(feature = "network-integration")]
fn main() {
    match run() {
        Ok(report) => {
            println!("{report}");
        }
        Err(error) => {
            println!("{}", error.report_json);
            eprintln!("{}", error.message);
            process::exit(1);
        }
    }
}

#[cfg(feature = "network-integration")]
fn run() -> Result<String, LiveProbeReplayFailure> {
    let transport = ReqwestHttpTransport::new(5_000).map_err(|error| {
        LiveProbeReplayFailure::from_early_error("transport", error, Vec::new())
    })?;
    let deribit_client =
        DeribitLiveIngestionClient::new("https://www.deribit.com", "ETH-20260601-3000-C");
    let polymarket_client = PolymarketLiveIngestionClient::new(
        "https://gamma-api.polymarket.com",
        "eth-above-3000-june-1",
        "Yes",
    );
    let deribit_config = IngestionConfig::phase0_deribit("https://www.deribit.com");
    let polymarket_config = IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com");

    let mut probe_reports = Vec::new();
    let mut errors = Vec::new();
    let mut batches = Vec::new();
    let mut journal = InMemoryEventJournal::new();

    fetch_deribit_batch(
        &deribit_client,
        &transport,
        &deribit_config,
        &mut journal,
        &mut probe_reports,
        &mut errors,
        &mut batches,
    );
    fetch_polymarket_batch(
        &polymarket_client,
        &transport,
        &polymarket_config,
        &mut journal,
        &mut probe_reports,
        &mut errors,
        &mut batches,
    );

    let outcomes = ingest_batches(&mut journal, batches, &mut errors);
    let ingestion_report = IngestionReport::from_outcomes(&outcomes);
    let replay_events = journal
        .read_events_for_replay(ReplayEventFilter {
            start_ts_ms: 0,
            end_ts_ms: i64::MAX,
            event_types: vec![],
            instrument_ids: vec![],
            config_version: Some(CONFIG_VERSION.to_string()),
        })
        .map_err(|error| {
            errors.push(DiagnosticError::new(
                "journal",
                "InMemoryEventJournal",
                "Storage",
                format!("{:?}: {}", error.kind, error.message),
            ));
            LiveProbeReplayFailure::from_report(
                "failed to read replay events",
                render_report(
                    &probe_reports,
                    &ingestion_report,
                    &ReplayPipelineSummary::empty(),
                    &errors,
                ),
            )
        })?;

    let replay_summary = run_matcher(&replay_events);
    let report = render_report(&probe_reports, &ingestion_report, &replay_summary, &errors);

    if errors.is_empty()
        && probe_reports.iter().all(LiveIngestionProbeReport::is_ok)
        && ingestion_report.total_normalized_events_accepted >= 2
        && replay_summary.decisions > 0
    {
        Ok(report)
    } else {
        Err(LiveProbeReplayFailure::from_report(
            "live probe replay did not complete cleanly",
            report,
        ))
    }
}

#[cfg(feature = "network-integration")]
fn fetch_deribit_batch<T>(
    client: &DeribitLiveIngestionClient,
    transport: &T,
    config: &IngestionConfig,
    journal: &mut InMemoryEventJournal,
    probe_reports: &mut Vec<LiveIngestionProbeReport>,
    errors: &mut Vec<DiagnosticError>,
    batches: &mut Vec<IngestionBatch>,
) where
    T: LiveHttpTransport,
{
    let url = client.ticker_url();
    let received_ts_ms = now_ms();
    let started_at = Instant::now();
    match transport.get(&url) {
        Ok(payload) => {
            probe_reports.push(LiveIngestionProbeReport::ok(
                "Deribit",
                url,
                payload.len(),
                started_at.elapsed().as_millis(),
            ));
            match client.parse_ticker_payload(&payload, config, received_ts_ms) {
                Ok(batch) => batches.push(batch),
                Err(error) => {
                    preserve_deribit_raw_payload(
                        client,
                        config,
                        received_ts_ms,
                        payload,
                        journal,
                        errors,
                    );
                    errors.push(DiagnosticError::from_ingestion_error(
                        "parse", "Deribit", error,
                    ));
                }
            }
        }
        Err(error) => {
            probe_reports.push(LiveIngestionProbeReport::error(
                "Deribit",
                url,
                started_at.elapsed().as_millis(),
                error.clone(),
            ));
            errors.push(DiagnosticError::from_ingestion_error(
                "http", "Deribit", error,
            ));
        }
    }
}

#[cfg(feature = "network-integration")]
fn fetch_polymarket_batch<T>(
    client: &PolymarketLiveIngestionClient,
    transport: &T,
    config: &IngestionConfig,
    journal: &mut InMemoryEventJournal,
    probe_reports: &mut Vec<LiveIngestionProbeReport>,
    errors: &mut Vec<DiagnosticError>,
    batches: &mut Vec<IngestionBatch>,
) where
    T: LiveHttpTransport,
{
    let url = client.gamma_market_url();
    let received_ts_ms = now_ms();
    let started_at = Instant::now();
    match transport.get(&url) {
        Ok(payload) => {
            probe_reports.push(LiveIngestionProbeReport::ok(
                "Polymarket Gamma",
                url,
                payload.len(),
                started_at.elapsed().as_millis(),
            ));
            match client.parse_gamma_market_payload(&payload, config, received_ts_ms) {
                Ok(batch) => batches.push(batch),
                Err(error) => {
                    preserve_polymarket_raw_payload(
                        client,
                        config,
                        received_ts_ms,
                        payload,
                        journal,
                        errors,
                    );
                    errors.push(DiagnosticError::from_ingestion_error(
                        "parse",
                        "Polymarket Gamma",
                        error,
                    ));
                }
            }
        }
        Err(error) => {
            probe_reports.push(LiveIngestionProbeReport::error(
                "Polymarket Gamma",
                url,
                started_at.elapsed().as_millis(),
                error.clone(),
            ));
            errors.push(DiagnosticError::from_ingestion_error(
                "http",
                "Polymarket Gamma",
                error,
            ));
        }
    }
}

#[cfg(feature = "network-integration")]
fn ingest_batches(
    journal: &mut InMemoryEventJournal,
    batches: Vec<IngestionBatch>,
    errors: &mut Vec<DiagnosticError>,
) -> Vec<IngestionOutcome> {
    let mut outcomes = Vec::new();
    for batch in batches {
        let source = batch.source;
        let config = match source {
            IngestionSource::Deribit => IngestionConfig::phase0_deribit("https://www.deribit.com"),
            IngestionSource::Polymarket => {
                IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com")
            }
        };
        let mut client = MockIngestionClient::new(vec![MockIngestionStep::Batch(batch)]);
        match ingest_once_with_report(
            &mut client,
            journal,
            &config,
            &Phase0NormalizedBatchValidator,
        ) {
            Ok(outcome) => outcomes.push(outcome),
            Err(error) => errors.push(DiagnosticError::from_ingestion_error(
                "ingest",
                source.as_str(),
                error,
            )),
        }
    }

    outcomes
}

#[cfg(feature = "network-integration")]
fn run_matcher(events: &[MarketEvent]) -> ReplayPipelineSummary {
    let config = ProbabilityBasisConfig {
        min_net_edge_probability: 0.025,
        max_expiry_mismatch_ms: 86_400_000,
        min_polymarket_liquidity_usd: 1_000.0,
        estimated_cost_probability: 0.010,
    };
    let decisions = match_from_market_events(events, &config);
    let observations = observations_from_match_decisions(&decisions, &config);
    ReplayPipelineSummary::from_decisions(&decisions, observations.len())
}

#[cfg(feature = "network-integration")]
fn preserve_deribit_raw_payload(
    client: &DeribitLiveIngestionClient,
    config: &IngestionConfig,
    received_ts_ms: i64,
    payload_json: String,
    journal: &mut InMemoryEventJournal,
    errors: &mut Vec<DiagnosticError>,
) {
    let event = RawDeribitEvent {
        meta: EventMeta {
            event_id: format!(
                "raw-deribit-live-probe:{}:{received_ts_ms}",
                client.instrument_name
            ),
            source: "deribit_live_probe_replay".to_string(),
            exchange_ts_ms: received_ts_ms,
            received_ts_ms,
            instrument_id: client.instrument_name.clone(),
            schema_version: 1,
            config_version: config.config_version.clone(),
        },
        endpoint_or_channel: "public/ticker".to_string(),
        payload_json,
    };

    if let Err(error) = journal.append_raw_deribit_event(event) {
        errors.push(DiagnosticError::new(
            "journal",
            "Deribit",
            "JournalWrite",
            format!("{:?}: {}", error.kind, error.message),
        ));
    }
}

#[cfg(feature = "network-integration")]
fn preserve_polymarket_raw_payload(
    client: &PolymarketLiveIngestionClient,
    config: &IngestionConfig,
    received_ts_ms: i64,
    payload_json: String,
    journal: &mut InMemoryEventJournal,
    errors: &mut Vec<DiagnosticError>,
) {
    let event = RawPolymarketEvent {
        meta: EventMeta {
            event_id: format!(
                "raw-polymarket-live-probe:{}:{}:{received_ts_ms}",
                client.market_slug, client.outcome
            ),
            source: "polymarket_live_probe_replay".to_string(),
            exchange_ts_ms: received_ts_ms,
            received_ts_ms,
            instrument_id: client.market_slug.clone(),
            schema_version: 1,
            config_version: config.config_version.clone(),
        },
        api_layer: PolymarketApiLayer::Gamma,
        payload_json,
    };

    if let Err(error) = journal.append_raw_polymarket_event(event) {
        errors.push(DiagnosticError::new(
            "journal",
            "Polymarket Gamma",
            "JournalWrite",
            format!("{:?}: {}", error.kind, error.message),
        ));
    }
}

#[cfg(feature = "network-integration")]
#[derive(Debug, Clone, PartialEq, Eq)]
struct DiagnosticError {
    stage: String,
    endpoint: String,
    kind: String,
    message: String,
}

#[cfg(feature = "network-integration")]
impl DiagnosticError {
    fn new(
        stage: impl Into<String>,
        endpoint: impl Into<String>,
        kind: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self {
            stage: stage.into(),
            endpoint: endpoint.into(),
            kind: kind.into(),
            message: message.into(),
        }
    }

    fn from_ingestion_error(
        stage: impl Into<String>,
        endpoint: impl Into<String>,
        error: IngestionError,
    ) -> Self {
        Self::new(stage, endpoint, error.kind.as_str(), error.message)
    }

    fn to_json(&self) -> String {
        format!(
            "{{\"stage\":\"{}\",\"endpoint\":\"{}\",\"kind\":\"{}\",\"message\":\"{}\"}}",
            json_escape(&self.stage),
            json_escape(&self.endpoint),
            json_escape(&self.kind),
            json_escape(&self.message)
        )
    }
}

#[cfg(feature = "network-integration")]
#[derive(Debug, Clone, PartialEq)]
struct ReplayPipelineSummary {
    decisions: usize,
    matched: usize,
    rejected: usize,
    observations: usize,
}

#[cfg(feature = "network-integration")]
impl ReplayPipelineSummary {
    fn empty() -> Self {
        Self {
            decisions: 0,
            matched: 0,
            rejected: 0,
            observations: 0,
        }
    }

    fn from_decisions(decisions: &[MatchDecision], observations: usize) -> Self {
        let matched = decisions
            .iter()
            .filter(|decision| matches!(decision, MatchDecision::Matched { .. }))
            .count();
        Self {
            decisions: decisions.len(),
            matched,
            rejected: decisions.len() - matched,
            observations,
        }
    }

    fn to_json(&self) -> String {
        format!(
            "{{\"decisions\":{},\"matched\":{},\"rejected\":{},\"observations\":{}}}",
            self.decisions, self.matched, self.rejected, self.observations
        )
    }
}

#[cfg(feature = "network-integration")]
#[derive(Debug, Clone, PartialEq, Eq)]
struct LiveProbeReplayFailure {
    message: String,
    report_json: String,
}

#[cfg(feature = "network-integration")]
impl LiveProbeReplayFailure {
    fn from_report(message: impl Into<String>, report_json: String) -> Self {
        Self {
            message: message.into(),
            report_json,
        }
    }

    fn from_early_error(
        endpoint: impl Into<String>,
        error: IngestionError,
        probe_reports: Vec<LiveIngestionProbeReport>,
    ) -> Self {
        let errors = vec![DiagnosticError::from_ingestion_error(
            "setup", endpoint, error,
        )];
        Self::from_report(
            "live probe replay failed before ingestion",
            render_report(
                &probe_reports,
                &IngestionReport::from_outcomes(&[]),
                &ReplayPipelineSummary::empty(),
                &errors,
            ),
        )
    }
}

#[cfg(feature = "network-integration")]
fn render_report(
    probe_reports: &[LiveIngestionProbeReport],
    ingestion_report: &IngestionReport,
    replay_summary: &ReplayPipelineSummary,
    errors: &[DiagnosticError],
) -> String {
    let probes = probe_reports
        .iter()
        .map(LiveIngestionProbeReport::to_json)
        .collect::<Vec<String>>()
        .join(",");
    let errors = errors
        .iter()
        .map(DiagnosticError::to_json)
        .collect::<Vec<String>>()
        .join(",");

    format!(
        "{{\"schema_version\":1,\"config_version\":\"{}\",\"pricing_model_version\":\"{}\",\"probe_reports\":[{}],\"ingestion_report\":{},\"replay_summary\":{},\"errors\":[{}]}}",
        CONFIG_VERSION,
        PRICING_MODEL_VERSION,
        probes,
        ingestion_report.to_json(),
        replay_summary.to_json(),
        errors
    )
}

#[cfg(feature = "network-integration")]
fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock should be after UNIX epoch")
        .as_millis() as i64
}

#[cfg(feature = "network-integration")]
fn json_escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
}

#[cfg(not(feature = "network-integration"))]
fn main() {
    eprintln!(
        "live_probe_replay requires: cargo run -p cryptotehnolog-ingestion --features network-integration --bin live_probe_replay"
    );
    std::process::exit(2);
}
