use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use cryptotehnolog_common::events::{
    DeribitOptionQuote, EventMeta, MarketEvent, OptionKind, PolymarketOutcomeQuote,
};
use cryptotehnolog_common::probability_basis::{
    ProbabilityBasisConfig, match_from_market_events, render_match_report,
};

const DEFAULT_FIXTURE_PATH: &str = "fixtures/probability_basis/golden_events.psv";

fn main() {
    let fixture_path = env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_FIXTURE_PATH));

    match run_probability_basis_replay_report(&fixture_path) {
        Ok(report) => {
            for line in report {
                println!("{line}");
            }
        }
        Err(error) => {
            eprintln!("replay failed: {error}");
            std::process::exit(1);
        }
    }
}

fn run_probability_basis_replay_report(fixture_path: &Path) -> Result<Vec<String>, String> {
    let events = load_market_events(fixture_path)?;
    let decisions = match_from_market_events(&events, &config());
    Ok(render_match_report(&decisions))
}

fn config() -> ProbabilityBasisConfig {
    ProbabilityBasisConfig {
        min_net_edge_probability: 0.025,
        max_expiry_mismatch_ms: 86_400_000,
        min_polymarket_liquidity_usd: 1000.0,
        estimated_cost_probability: 0.010,
    }
}

fn load_market_events(path: &Path) -> Result<Vec<MarketEvent>, String> {
    let content = fs::read_to_string(path)
        .map_err(|error| format!("cannot read fixture {}: {error}", path.display()))?;
    parse_market_events(&content)
}

fn parse_market_events(content: &str) -> Result<Vec<MarketEvent>, String> {
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

#[cfg(test)]
mod tests {
    use super::*;

    fn workspace_fixture_path(file_name: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("fixtures")
            .join("probability_basis")
            .join(file_name)
    }

    #[test]
    fn probability_basis_replay_report_is_stable() {
        let report =
            run_probability_basis_replay_report(&workspace_fixture_path("golden_events.psv"))
                .expect("fixture replay should succeed");
        let expected = fs::read_to_string(workspace_fixture_path("golden_report.txt"))
            .expect("expected report should be readable");
        let expected_lines: Vec<String> = expected.lines().map(str::to_string).collect();

        assert_eq!(report, expected_lines);
    }

    #[test]
    fn fixture_parser_rejects_unknown_event_type() {
        let error = parse_market_events("unknown|id|instrument|1|2|cfg||||||||||||||")
            .expect_err("unknown event type should fail");

        assert!(error.contains("unsupported event_type"));
    }
}
