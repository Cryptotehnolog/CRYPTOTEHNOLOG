use std::fs;
use std::path::Path;

use cryptotehnolog_common::events::{
    DeribitOptionQuote, EventMeta, MarketEvent, OptionKind, PolymarketOutcomeQuote,
};
use cryptotehnolog_common::observations::{
    BasisObservation, BasisObservationWriter, InMemoryBasisObservationWriter,
    observations_from_match_decisions,
};
use cryptotehnolog_common::probability_basis::{
    MatchDecision, PRICING_MODEL_VERSION, ProbabilityBasisConfig, match_from_market_events,
};

pub const DEFAULT_FIXTURE_PATH: &str = "fixtures/probability_basis/golden_events.psv";

#[derive(Debug, Clone, PartialEq)]
pub struct ProbabilityBasisReplayOutput {
    pub decisions: Vec<MatchDecision>,
    pub observations: Vec<BasisObservation>,
}

impl ProbabilityBasisReplayOutput {
    pub fn replay_report(&self) -> ReplayReport {
        ReplayReport::from_decisions(&self.decisions)
    }

    pub fn report_lines(&self) -> Vec<String> {
        self.replay_report().to_text_lines()
    }

    pub fn report_json(&self) -> String {
        self.replay_report().to_json()
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct ReplayReport {
    pub schema_version: u16,
    pub pricing_model_version: String,
    pub entries: Vec<ReplayReportEntry>,
}

impl ReplayReport {
    pub fn from_decisions(decisions: &[MatchDecision]) -> Self {
        Self {
            schema_version: 1,
            pricing_model_version: PRICING_MODEL_VERSION.to_string(),
            entries: decisions.iter().map(ReplayReportEntry::from).collect(),
        }
    }

    pub fn to_text_lines(&self) -> Vec<String> {
        let mut lines = vec![format!(
            "metadata|pricing_model_version={}",
            self.pricing_model_version
        )];
        lines.extend(self.entries.iter().map(ReplayReportEntry::to_text_line));
        lines
    }

    pub fn to_json(&self) -> String {
        let mut json = String::new();
        json.push_str("{\n");
        json.push_str(&format!("  \"schema_version\": {},\n", self.schema_version));
        json.push_str(&format!(
            "  \"pricing_model_version\": \"{}\",\n",
            json_escape(&self.pricing_model_version)
        ));
        json.push_str("  \"entries\": [\n");

        for (index, entry) in self.entries.iter().enumerate() {
            json.push_str(&entry.to_json(4));
            if index + 1 != self.entries.len() {
                json.push(',');
            }
            json.push('\n');
        }

        json.push_str("  ]\n");
        json.push_str("}\n");
        json
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum ReplayReportEntry {
    Matched {
        deribit_instrument_id: String,
        polymarket_market_slug: String,
        net_edge_probability: f64,
        survives_costs: bool,
    },
    Rejected {
        reason: String,
        deribit_instrument_id: Option<String>,
        polymarket_market_slug: Option<String>,
    },
}

impl ReplayReportEntry {
    fn to_text_line(&self) -> String {
        match self {
            ReplayReportEntry::Matched {
                deribit_instrument_id,
                polymarket_market_slug,
                net_edge_probability,
                survives_costs,
            } => format!(
                "matched|{}|{}|net_edge={:.6}|survives={}",
                deribit_instrument_id, polymarket_market_slug, net_edge_probability, survives_costs
            ),
            ReplayReportEntry::Rejected {
                reason,
                deribit_instrument_id,
                polymarket_market_slug,
            } => format!(
                "rejected|{}|{}|{}",
                reason,
                deribit_instrument_id.as_deref().unwrap_or("none"),
                polymarket_market_slug.as_deref().unwrap_or("none")
            ),
        }
    }

    fn to_json(&self, indent: usize) -> String {
        let spaces = " ".repeat(indent);
        let inner_spaces = " ".repeat(indent + 2);

        match self {
            ReplayReportEntry::Matched {
                deribit_instrument_id,
                polymarket_market_slug,
                net_edge_probability,
                survives_costs,
            } => format!(
                "{spaces}{{\n{inner_spaces}\"type\": \"matched\",\n{inner_spaces}\"deribit_instrument_id\": \"{}\",\n{inner_spaces}\"polymarket_market_slug\": \"{}\",\n{inner_spaces}\"net_edge_probability\": {:.6},\n{inner_spaces}\"survives_costs\": {}\n{spaces}}}",
                json_escape(deribit_instrument_id),
                json_escape(polymarket_market_slug),
                net_edge_probability,
                survives_costs
            ),
            ReplayReportEntry::Rejected {
                reason,
                deribit_instrument_id,
                polymarket_market_slug,
            } => format!(
                "{spaces}{{\n{inner_spaces}\"type\": \"rejected\",\n{inner_spaces}\"reason\": \"{}\",\n{inner_spaces}\"deribit_instrument_id\": {},\n{inner_spaces}\"polymarket_market_slug\": {}\n{spaces}}}",
                json_escape(reason),
                json_option(deribit_instrument_id.as_deref()),
                json_option(polymarket_market_slug.as_deref())
            ),
        }
    }
}

impl From<&MatchDecision> for ReplayReportEntry {
    fn from(decision: &MatchDecision) -> Self {
        match decision {
            MatchDecision::Matched {
                feature,
                net_edge_probability,
                survives_costs,
            } => ReplayReportEntry::Matched {
                deribit_instrument_id: feature.deribit_instrument_id.clone(),
                polymarket_market_slug: feature.polymarket_market_slug.clone(),
                net_edge_probability: *net_edge_probability,
                survives_costs: *survives_costs,
            },
            MatchDecision::Rejected {
                reason,
                deribit_instrument_id,
                polymarket_market_slug,
            } => ReplayReportEntry::Rejected {
                reason: format!("{reason:?}"),
                deribit_instrument_id: deribit_instrument_id.clone(),
                polymarket_market_slug: polymarket_market_slug.clone(),
            },
        }
    }
}

pub fn run_probability_basis_replay(
    fixture_path: &Path,
) -> Result<ProbabilityBasisReplayOutput, String> {
    let events = load_market_events(fixture_path)?;
    let config = default_probability_basis_config();
    let decisions = match_from_market_events(&events, &config);
    let observations = write_observations(&decisions, &config)?;

    Ok(ProbabilityBasisReplayOutput {
        decisions,
        observations,
    })
}

pub fn run_probability_basis_replay_report(fixture_path: &Path) -> Result<Vec<String>, String> {
    Ok(run_probability_basis_replay(fixture_path)?.report_lines())
}

pub fn run_probability_basis_replay_report_json(fixture_path: &Path) -> Result<String, String> {
    Ok(run_probability_basis_replay(fixture_path)?.report_json())
}

pub fn default_probability_basis_config() -> ProbabilityBasisConfig {
    ProbabilityBasisConfig {
        min_net_edge_probability: 0.025,
        max_expiry_mismatch_ms: 86_400_000,
        min_polymarket_liquidity_usd: 1000.0,
        estimated_cost_probability: 0.010,
    }
}

pub fn load_market_events(path: &Path) -> Result<Vec<MarketEvent>, String> {
    let content = fs::read_to_string(path)
        .map_err(|error| format!("cannot read fixture {}: {error}", path.display()))?;
    parse_market_events(&content)
}

pub fn parse_market_events(content: &str) -> Result<Vec<MarketEvent>, String> {
    let mut events = Vec::new();

    for (index, line) in content.lines().enumerate() {
        let line_number = index + 1;
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }

        let fields: Vec<&str> = trimmed.split('|').collect();
        if fields.len() != 20 {
            return Err(format!(
                "line {line_number}: expected 20 pipe-separated fields, got {}",
                fields.len()
            ));
        }

        events.push(parse_market_event(line_number, &fields)?);
    }

    if events.is_empty() {
        return Err("fixture contains no market events".to_string());
    }

    Ok(events)
}

fn write_observations(
    decisions: &[MatchDecision],
    config: &ProbabilityBasisConfig,
) -> Result<Vec<BasisObservation>, String> {
    let mut observation_writer = InMemoryBasisObservationWriter::new();
    for observation in observations_from_match_decisions(decisions, config) {
        observation_writer
            .append_basis_observation(observation)
            .map_err(|error| error.message)?;
    }

    Ok(observation_writer.observations().to_vec())
}

fn parse_market_event(line_number: usize, fields: &[&str]) -> Result<MarketEvent, String> {
    let event_type = fields[0];
    let meta = EventMeta {
        event_id: required_string(line_number, fields[1], "event_id")?,
        source: "golden-replay-fixture".to_string(),
        exchange_ts_ms: parse_i64(line_number, fields[3], "exchange_ts_ms")?,
        received_ts_ms: parse_i64(line_number, fields[4], "received_ts_ms")?,
        instrument_id: required_string(line_number, fields[2], "instrument_id")?,
        schema_version: 1,
        config_version: required_string(line_number, fields[5], "config_version")?,
    };

    match event_type {
        "deribit_option_quote" => Ok(MarketEvent::DeribitOptionQuote(DeribitOptionQuote {
            meta,
            underlying: required_string(line_number, fields[6], "underlying")?,
            expiry_ts_ms: parse_i64(line_number, fields[7], "expiry_ts_ms")?,
            strike: parse_f64(line_number, fields[8], "strike")?,
            option_kind: parse_option_kind(line_number, fields[9])?,
            underlying_price: parse_f64(line_number, fields[10], "underlying_price")?,
            bid: parse_f64(line_number, fields[11], "bid")?,
            ask: parse_f64(line_number, fields[12], "ask")?,
            mark_iv: parse_f64(line_number, fields[13], "mark_iv")?,
        })),
        "polymarket_outcome_quote" => Ok(MarketEvent::PolymarketOutcomeQuote(
            PolymarketOutcomeQuote {
                meta,
                event_slug: required_string(line_number, fields[14], "event_slug")?,
                market_slug: required_string(line_number, fields[15], "market_slug")?,
                outcome: required_string(line_number, fields[16], "outcome")?,
                bid_probability: parse_f64(line_number, fields[17], "bid_probability")?,
                ask_probability: parse_f64(line_number, fields[18], "ask_probability")?,
                liquidity_usd: parse_f64(line_number, fields[19], "liquidity_usd")?,
            },
        )),
        other => Err(format!(
            "line {line_number}: unsupported event_type `{other}`"
        )),
    }
}

fn required_string(line_number: usize, raw: &str, field_name: &str) -> Result<String, String> {
    let value = raw.trim();
    if value.is_empty() {
        return Err(format!("line {line_number}: `{field_name}` is required"));
    }
    Ok(value.to_string())
}

fn parse_i64(line_number: usize, raw: &str, field_name: &str) -> Result<i64, String> {
    raw.trim()
        .parse::<i64>()
        .map_err(|error| format!("line {line_number}: invalid `{field_name}`: {error}"))
}

fn parse_f64(line_number: usize, raw: &str, field_name: &str) -> Result<f64, String> {
    raw.trim()
        .parse::<f64>()
        .map_err(|error| format!("line {line_number}: invalid `{field_name}`: {error}"))
}

fn parse_option_kind(line_number: usize, raw: &str) -> Result<OptionKind, String> {
    match raw.trim() {
        "call" => Ok(OptionKind::Call),
        "put" => Ok(OptionKind::Put),
        other => Err(format!(
            "line {line_number}: unsupported `option_kind` `{other}`"
        )),
    }
}

fn json_option(value: Option<&str>) -> String {
    match value {
        Some(value) => format!("\"{}\"", json_escape(value)),
        None => "null".to_string(),
    }
}

fn json_escape(value: &str) -> String {
    let mut escaped = String::new();
    for character in value.chars() {
        match character {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            other => escaped.push(other),
        }
    }
    escaped
}

#[cfg(test)]
mod tests {
    use super::*;

    fn workspace_fixture_path(file_name: &str) -> std::path::PathBuf {
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("fixtures")
            .join("probability_basis")
            .join(file_name)
    }

    #[test]
    fn replay_semantics_are_stable_on_golden_fixture() {
        let output = run_probability_basis_replay(&workspace_fixture_path("golden_events.psv"))
            .expect("fixture replay should succeed");

        assert_eq!(output.decisions.len(), 2);
        assert_eq!(output.observations.len(), 1);
        let report = output.replay_report();
        assert_eq!(report.schema_version, 1);
        assert_eq!(report.pricing_model_version, PRICING_MODEL_VERSION);
        assert_eq!(report.entries.len(), 2);
        assert_eq!(
            output.observations[0].deribit_instrument_id,
            "ETH-20260601-3000-C"
        );
        assert_eq!(
            output.observations[0].polymarket_market_slug,
            "eth-above-3000-june-1"
        );
        assert!((output.observations[0].net_edge_probability - 0.081338).abs() < 1e-6);
        assert!(output.observations[0].survives_costs);
    }

    #[test]
    fn probability_basis_text_report_matches_current_golden_file() {
        let output = run_probability_basis_replay(&workspace_fixture_path("golden_events.psv"))
            .expect("fixture replay should succeed");
        let expected = fs::read_to_string(workspace_fixture_path("golden_report.txt"))
            .expect("expected report should be readable");
        let expected_lines: Vec<String> = expected.lines().map(str::to_string).collect();

        assert_eq!(output.report_lines(), expected_lines);
    }

    #[test]
    fn probability_basis_json_report_matches_current_golden_file() {
        let output = run_probability_basis_replay(&workspace_fixture_path("golden_events.psv"))
            .expect("fixture replay should succeed");
        let expected = fs::read_to_string(workspace_fixture_path("golden_report.json"))
            .expect("expected JSON report should be readable");

        assert_eq!(output.report_json(), expected);
    }

    #[test]
    fn fixture_parser_rejects_unknown_event_type() {
        let error = parse_market_events("unknown|id|instrument|1|2|cfg||||||||||||||")
            .expect_err("unknown event type should fail");

        assert!(error.contains("unsupported event_type"));
    }
}
