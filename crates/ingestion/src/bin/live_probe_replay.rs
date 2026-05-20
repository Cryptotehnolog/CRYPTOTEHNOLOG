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
    DERIBIT_INSTRUMENTS_PAYLOAD_SHAPE_VERSION, DERIBIT_TICKER_PAYLOAD_SHAPE_VERSION,
    DeribitDiscoveredOption, DeribitLiveIngestionClient, DeribitOptionDiscoveryCriteria,
    IngestionBatch, IngestionConfig, IngestionError, IngestionOutcome, IngestionReport,
    IngestionSource, LiveHttpTransport, LiveIngestionProbeReport, MockIngestionClient,
    MockIngestionStep, POLYMARKET_GAMMA_MARKET_PAYLOAD_SHAPE_VERSION,
    POLYMARKET_GAMMA_MARKETS_PAYLOAD_SHAPE_VERSION, Phase0NormalizedBatchValidator,
    PolymarketDiscoveredMarket, PolymarketLiveIngestionClient, PolymarketMarketDiscoveryCriteria,
    ReqwestHttpTransport, ingest_once_with_report,
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
    let deribit_config = IngestionConfig::phase0_deribit("https://www.deribit.com");
    let polymarket_config = IngestionConfig::phase0_polymarket("https://gamma-api.polymarket.com");

    let mut probe_reports = Vec::new();
    let mut payload_shape_versions = Vec::new();
    let mut selection_report = SelectionReport::empty();
    let mut errors = Vec::new();
    let mut batches = Vec::new();
    let mut journal = InMemoryEventJournal::new();

    if let Some(deribit_client) = discover_deribit_option_client(
        &transport,
        &mut probe_reports,
        &mut payload_shape_versions,
        &mut selection_report,
        &mut errors,
    ) {
        fetch_deribit_batch(
            &deribit_client,
            &transport,
            &deribit_config,
            &mut journal,
            &mut probe_reports,
            &mut payload_shape_versions,
            &mut errors,
            &mut batches,
        );
    }
    if let Some(polymarket_client) = discover_polymarket_market_client(
        &transport,
        &mut probe_reports,
        &mut payload_shape_versions,
        &mut selection_report,
        &mut errors,
    ) {
        fetch_polymarket_batch(
            &polymarket_client,
            &transport,
            &polymarket_config,
            &mut journal,
            &mut probe_reports,
            &mut payload_shape_versions,
            &mut errors,
            &mut batches,
        );
    }

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
                    &payload_shape_versions,
                    &selection_report,
                    &ingestion_report,
                    &ReplayPipelineSummary::empty(),
                    &errors,
                ),
            )
        })?;

    let replay_summary = run_matcher(&replay_events);
    let report = render_report(
        &probe_reports,
        &payload_shape_versions,
        &selection_report,
        &ingestion_report,
        &replay_summary,
        &errors,
    );

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
fn discover_deribit_option_client<T>(
    transport: &T,
    probe_reports: &mut Vec<LiveIngestionProbeReport>,
    payload_shape_versions: &mut Vec<PayloadShapeVersion>,
    selection_report: &mut SelectionReport,
    errors: &mut Vec<DiagnosticError>,
) -> Option<DeribitLiveIngestionClient>
where
    T: LiveHttpTransport,
{
    let base_url = "https://www.deribit.com";
    let url = DeribitLiveIngestionClient::instruments_url(base_url);
    let started_at = Instant::now();
    match transport.get(&url) {
        Ok(payload) => {
            probe_reports.push(LiveIngestionProbeReport::ok(
                "Deribit instruments",
                url,
                payload.len(),
                started_at.elapsed().as_millis(),
            ));
            payload_shape_versions.push(PayloadShapeVersion::new(
                "Deribit instruments",
                DERIBIT_INSTRUMENTS_PAYLOAD_SHAPE_VERSION,
            ));
            let criteria = DeribitOptionDiscoveryCriteria::phase0_eth_call_3000_june_2026();
            match DeribitLiveIngestionClient::discover_option_from_payload(&payload, &criteria) {
                Ok(discovered) => {
                    selection_report.set_deribit(&criteria, &discovered);
                    Some(DeribitLiveIngestionClient::from_discovered(
                        base_url,
                        &discovered,
                    ))
                }
                Err(error) => {
                    errors.push(DiagnosticError::from_ingestion_error(
                        "discovery",
                        "Deribit instruments",
                        error,
                    ));
                    None
                }
            }
        }
        Err(error) => {
            probe_reports.push(LiveIngestionProbeReport::error(
                "Deribit instruments",
                url,
                started_at.elapsed().as_millis(),
                error.clone(),
            ));
            errors.push(DiagnosticError::from_ingestion_error(
                "http",
                "Deribit instruments",
                error,
            ));
            None
        }
    }
}

#[cfg(feature = "network-integration")]
fn discover_polymarket_market_client<T>(
    transport: &T,
    probe_reports: &mut Vec<LiveIngestionProbeReport>,
    payload_shape_versions: &mut Vec<PayloadShapeVersion>,
    selection_report: &mut SelectionReport,
    errors: &mut Vec<DiagnosticError>,
) -> Option<PolymarketLiveIngestionClient>
where
    T: LiveHttpTransport,
{
    let base_url = "https://gamma-api.polymarket.com";
    let url = PolymarketLiveIngestionClient::markets_url(base_url);
    let started_at = Instant::now();
    match transport.get(&url) {
        Ok(payload) => {
            probe_reports.push(LiveIngestionProbeReport::ok(
                "Polymarket Gamma markets",
                url,
                payload.len(),
                started_at.elapsed().as_millis(),
            ));
            payload_shape_versions.push(PayloadShapeVersion::new(
                "Polymarket Gamma markets",
                POLYMARKET_GAMMA_MARKETS_PAYLOAD_SHAPE_VERSION,
            ));
            let criteria = PolymarketMarketDiscoveryCriteria::phase0_eth_above_3000_yes();
            match PolymarketLiveIngestionClient::discover_market_from_payload(&payload, &criteria) {
                Ok(discovered) => {
                    selection_report.set_polymarket(&discovered);
                    Some(PolymarketLiveIngestionClient::from_discovered(
                        base_url,
                        &discovered,
                    ))
                }
                Err(error) => {
                    errors.push(DiagnosticError::from_ingestion_error(
                        "discovery",
                        "Polymarket Gamma markets",
                        error,
                    ));
                    None
                }
            }
        }
        Err(error) => {
            probe_reports.push(LiveIngestionProbeReport::error(
                "Polymarket Gamma markets",
                url,
                started_at.elapsed().as_millis(),
                error.clone(),
            ));
            errors.push(DiagnosticError::from_ingestion_error(
                "http",
                "Polymarket Gamma markets",
                error,
            ));
            None
        }
    }
}

#[cfg(feature = "network-integration")]
fn fetch_deribit_batch<T>(
    client: &DeribitLiveIngestionClient,
    transport: &T,
    config: &IngestionConfig,
    journal: &mut InMemoryEventJournal,
    probe_reports: &mut Vec<LiveIngestionProbeReport>,
    payload_shape_versions: &mut Vec<PayloadShapeVersion>,
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
            payload_shape_versions.push(PayloadShapeVersion::new(
                "Deribit",
                DERIBIT_TICKER_PAYLOAD_SHAPE_VERSION,
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
    payload_shape_versions: &mut Vec<PayloadShapeVersion>,
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
            payload_shape_versions.push(PayloadShapeVersion::new(
                "Polymarket Gamma",
                POLYMARKET_GAMMA_MARKET_PAYLOAD_SHAPE_VERSION,
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
struct PayloadShapeVersion {
    endpoint: String,
    version: String,
}

#[cfg(feature = "network-integration")]
impl PayloadShapeVersion {
    fn new(endpoint: impl Into<String>, version: impl Into<String>) -> Self {
        Self {
            endpoint: endpoint.into(),
            version: version.into(),
        }
    }

    fn to_json(&self) -> String {
        format!(
            "{{\"endpoint\":\"{}\",\"payload_shape_version\":\"{}\"}}",
            json_escape(&self.endpoint),
            json_escape(&self.version)
        )
    }
}

#[cfg(feature = "network-integration")]
#[derive(Debug, Clone, PartialEq)]
struct SelectionReport {
    selected_deribit_instrument: Option<String>,
    target_expiry_ts_ms: Option<i64>,
    target_expiry_date: Option<String>,
    selected_expiry_ts_ms: Option<i64>,
    selected_expiry_date: Option<String>,
    strike_distance: Option<f64>,
    selected_polymarket_market_slug: Option<String>,
    selected_polymarket_event_slug: Option<String>,
    selected_polymarket_liquidity_usd: Option<f64>,
}

#[cfg(feature = "network-integration")]
impl SelectionReport {
    fn empty() -> Self {
        Self {
            selected_deribit_instrument: None,
            target_expiry_ts_ms: None,
            target_expiry_date: None,
            selected_expiry_ts_ms: None,
            selected_expiry_date: None,
            strike_distance: None,
            selected_polymarket_market_slug: None,
            selected_polymarket_event_slug: None,
            selected_polymarket_liquidity_usd: None,
        }
    }

    fn set_deribit(
        &mut self,
        criteria: &DeribitOptionDiscoveryCriteria,
        discovered: &DeribitDiscoveredOption,
    ) {
        self.selected_deribit_instrument = Some(discovered.instrument_name.clone());
        self.target_expiry_ts_ms = Some(criteria.target_expiry_ts_ms);
        self.target_expiry_date = Some(utc_date_from_unix_ms(criteria.target_expiry_ts_ms));
        self.selected_expiry_ts_ms = Some(discovered.expiry_ts_ms);
        self.selected_expiry_date = Some(utc_date_from_unix_ms(discovered.expiry_ts_ms));
        self.strike_distance = Some((discovered.strike - criteria.target_strike).abs());
    }

    fn set_polymarket(&mut self, discovered: &PolymarketDiscoveredMarket) {
        self.selected_polymarket_market_slug = Some(discovered.market_slug.clone());
        self.selected_polymarket_event_slug = Some(discovered.event_slug.clone());
        self.selected_polymarket_liquidity_usd = Some(discovered.liquidity_usd);
    }

    fn strike_mismatch(&self) -> bool {
        self.strike_distance
            .map(|distance| distance > 0.0)
            .unwrap_or(false)
    }

    fn expiry_mismatch(&self) -> bool {
        match (self.target_expiry_ts_ms, self.selected_expiry_ts_ms) {
            (Some(target), Some(selected)) => target != selected,
            _ => false,
        }
    }

    fn selection_quality(&self) -> &'static str {
        if self.selected_deribit_instrument.is_none()
            || self.selected_polymarket_market_slug.is_none()
        {
            return "missing";
        }

        match (self.strike_mismatch(), self.expiry_mismatch()) {
            (false, false) => "exact",
            (true, true) => "mismatch",
            (true, false) | (false, true) => "nearby",
        }
    }

    fn to_json(&self) -> String {
        format!(
            "{{\"selection_quality\":\"{}\",\"selected_deribit_instrument\":{},\"target_expiry_ts_ms\":{},\"target_expiry_date\":{},\"selected_expiry_ts_ms\":{},\"selected_expiry_date\":{},\"strike_distance\":{},\"strike_mismatch\":{},\"expiry_mismatch\":{},\"selected_polymarket_market_slug\":{},\"selected_polymarket_event_slug\":{},\"selected_polymarket_liquidity_usd\":{}}}",
            self.selection_quality(),
            optional_string_json(&self.selected_deribit_instrument),
            optional_i64_json(self.target_expiry_ts_ms),
            optional_string_json(&self.target_expiry_date),
            optional_i64_json(self.selected_expiry_ts_ms),
            optional_string_json(&self.selected_expiry_date),
            optional_f64_json(self.strike_distance),
            self.strike_mismatch(),
            self.expiry_mismatch(),
            optional_string_json(&self.selected_polymarket_market_slug),
            optional_string_json(&self.selected_polymarket_event_slug),
            optional_f64_json(self.selected_polymarket_liquidity_usd)
        )
    }
}

#[cfg(feature = "network-integration")]
fn utc_date_from_unix_ms(timestamp_ms: i64) -> String {
    let days_since_unix_epoch = timestamp_ms.div_euclid(86_400_000);
    let (year, month, day) = civil_date_from_unix_days(days_since_unix_epoch);
    format!("{year:04}-{month:02}-{day:02}")
}

#[cfg(feature = "network-integration")]
fn civil_date_from_unix_days(days_since_unix_epoch: i64) -> (i64, i64, i64) {
    let shifted_days = days_since_unix_epoch + 719_468;
    let era = if shifted_days >= 0 {
        shifted_days
    } else {
        shifted_days - 146_096
    } / 146_097;
    let day_of_era = shifted_days - era * 146_097;
    let year_of_era =
        (day_of_era - day_of_era / 1_460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let mut year = year_of_era + era * 400;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_param = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * month_param + 2) / 5 + 1;
    let month = month_param + if month_param < 10 { 3 } else { -9 };
    if month <= 2 {
        year += 1;
    }

    (year, month, day)
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
                &[],
                &SelectionReport::empty(),
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
    payload_shape_versions: &[PayloadShapeVersion],
    selection_report: &SelectionReport,
    ingestion_report: &IngestionReport,
    replay_summary: &ReplayPipelineSummary,
    errors: &[DiagnosticError],
) -> String {
    let probes = probe_reports
        .iter()
        .map(LiveIngestionProbeReport::to_json)
        .collect::<Vec<String>>()
        .join(",");
    let payload_shapes = payload_shape_versions
        .iter()
        .map(PayloadShapeVersion::to_json)
        .collect::<Vec<String>>()
        .join(",");
    let errors = errors
        .iter()
        .map(DiagnosticError::to_json)
        .collect::<Vec<String>>()
        .join(",");

    format!(
        "{{\"schema_version\":1,\"config_version\":\"{}\",\"pricing_model_version\":\"{}\",\"payload_shape_versions\":[{}],\"selection_report\":{},\"probe_reports\":[{}],\"ingestion_report\":{},\"replay_summary\":{},\"errors\":[{}]}}",
        CONFIG_VERSION,
        PRICING_MODEL_VERSION,
        payload_shapes,
        selection_report.to_json(),
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

#[cfg(feature = "network-integration")]
fn optional_string_json(value: &Option<String>) -> String {
    value
        .as_ref()
        .map(|text| format!("\"{}\"", json_escape(text)))
        .unwrap_or_else(|| "null".to_string())
}

#[cfg(feature = "network-integration")]
fn optional_i64_json(value: Option<i64>) -> String {
    value
        .map(|number| number.to_string())
        .unwrap_or_else(|| "null".to_string())
}

#[cfg(feature = "network-integration")]
fn optional_f64_json(value: Option<f64>) -> String {
    value
        .map(|number| number.to_string())
        .unwrap_or_else(|| "null".to_string())
}

#[cfg(all(test, feature = "network-integration"))]
mod tests {
    use super::{SelectionReport, utc_date_from_unix_ms};
    use cryptotehnolog_common::events::OptionKind;
    use cryptotehnolog_ingestion::{DeribitDiscoveredOption, DeribitOptionDiscoveryCriteria};

    #[test]
    fn unix_ms_dates_are_rendered_as_utc_calendar_dates() {
        assert_eq!(utc_date_from_unix_ms(0), "1970-01-01");
        assert_eq!(utc_date_from_unix_ms(1_780_272_000_000), "2026-06-01");
        assert_eq!(utc_date_from_unix_ms(1_782_432_000_000), "2026-06-26");
    }

    #[test]
    fn selection_report_mismatch_flags_are_derived_from_selected_candidate() {
        let criteria = DeribitOptionDiscoveryCriteria::phase0_eth_call_3000_june_2026();
        let discovered = DeribitDiscoveredOption {
            instrument_name: "ETH-26JUN26-3100-C".to_string(),
            underlying: "ETH".to_string(),
            expiry_ts_ms: 1_782_432_000_000,
            strike: 3100.0,
            option_kind: OptionKind::Call,
        };
        let mut report = SelectionReport::empty();

        report.set_deribit(&criteria, &discovered);

        assert!(report.strike_mismatch());
        assert!(report.expiry_mismatch());
        assert_eq!(report.selection_quality(), "missing");
        assert!(report.to_json().contains("\"strike_mismatch\":true"));
        assert!(report.to_json().contains("\"expiry_mismatch\":true"));
        assert!(
            report
                .to_json()
                .contains("\"selection_quality\":\"missing\"")
        );
    }

    #[test]
    fn empty_selection_report_has_no_mismatch_flags() {
        let report = SelectionReport::empty();

        assert!(!report.strike_mismatch());
        assert!(!report.expiry_mismatch());
        assert_eq!(report.selection_quality(), "missing");
        assert!(report.to_json().contains("\"strike_mismatch\":false"));
        assert!(report.to_json().contains("\"expiry_mismatch\":false"));
        assert!(
            report
                .to_json()
                .contains("\"selection_quality\":\"missing\"")
        );
    }

    #[test]
    fn selection_quality_summarizes_complete_candidate_alignment() {
        let criteria = DeribitOptionDiscoveryCriteria::phase0_eth_call_3000_june_2026();
        let mut exact = SelectionReport::empty();
        exact.selected_polymarket_market_slug = Some("eth-above-3000-june-2026".to_string());
        exact.set_deribit(
            &criteria,
            &DeribitDiscoveredOption {
                instrument_name: "ETH-1JUN26-3000-C".to_string(),
                underlying: "ETH".to_string(),
                expiry_ts_ms: criteria.target_expiry_ts_ms,
                strike: criteria.target_strike,
                option_kind: OptionKind::Call,
            },
        );
        assert_eq!(exact.selection_quality(), "exact");

        let mut nearby = exact.clone();
        nearby.strike_distance = Some(100.0);
        assert_eq!(nearby.selection_quality(), "nearby");

        let mut mismatch = nearby.clone();
        mismatch.selected_expiry_ts_ms = Some(1_782_432_000_000);
        assert_eq!(mismatch.selection_quality(), "mismatch");
    }
}

#[cfg(not(feature = "network-integration"))]
fn main() {
    eprintln!(
        "live_probe_replay requires: cargo run -p cryptotehnolog-ingestion --features network-integration --bin live_probe_replay"
    );
    std::process::exit(2);
}
