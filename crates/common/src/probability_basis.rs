use crate::events::{
    DeribitOptionQuote, EventMeta, MarketEvent, OptionKind, PolymarketOutcomeQuote,
    ProbabilityBasisFeature,
};

#[derive(Debug, Clone, PartialEq)]
pub struct ProbabilityBasisConfig {
    pub min_net_edge_probability: f64,
    pub max_expiry_mismatch_ms: i64,
    pub min_polymarket_liquidity_usd: f64,
    pub estimated_cost_probability: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum MatchDecision {
    Matched {
        feature: ProbabilityBasisFeature,
        net_edge_probability: f64,
        survives_costs: bool,
    },
    Rejected {
        reason: RejectionReason,
        deribit_instrument_id: Option<String>,
        polymarket_market_slug: Option<String>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RejectionReason {
    MissingDeribitQuote,
    MissingPolymarketQuote,
    UnsupportedUnderlying,
    UnsupportedOptionKind,
    ExpiryMismatch,
    InsufficientLiquidity,
    InvalidQuote,
    EdgeBelowThreshold,
}

pub fn match_probability_basis(
    deribit_quote: Option<&DeribitOptionQuote>,
    polymarket_quote: Option<&PolymarketOutcomeQuote>,
    config: &ProbabilityBasisConfig,
) -> MatchDecision {
    let Some(deribit_quote) = deribit_quote else {
        return MatchDecision::Rejected {
            reason: RejectionReason::MissingDeribitQuote,
            deribit_instrument_id: None,
            polymarket_market_slug: polymarket_quote.map(|quote| quote.market_slug.clone()),
        };
    };

    let Some(polymarket_quote) = polymarket_quote else {
        return MatchDecision::Rejected {
            reason: RejectionReason::MissingPolymarketQuote,
            deribit_instrument_id: Some(deribit_quote.meta.instrument_id.clone()),
            polymarket_market_slug: None,
        };
    };

    if deribit_quote.underlying != "ETH" {
        return reject_pair(
            RejectionReason::UnsupportedUnderlying,
            deribit_quote,
            polymarket_quote,
        );
    }

    if deribit_quote.option_kind != OptionKind::Call {
        return reject_pair(
            RejectionReason::UnsupportedOptionKind,
            deribit_quote,
            polymarket_quote,
        );
    }

    let expiry_mismatch_ms =
        (deribit_quote.expiry_ts_ms - polymarket_quote.meta.exchange_ts_ms).abs();
    if expiry_mismatch_ms > config.max_expiry_mismatch_ms {
        return reject_pair(
            RejectionReason::ExpiryMismatch,
            deribit_quote,
            polymarket_quote,
        );
    }

    if polymarket_quote.liquidity_usd < config.min_polymarket_liquidity_usd {
        return reject_pair(
            RejectionReason::InsufficientLiquidity,
            deribit_quote,
            polymarket_quote,
        );
    }

    if !is_valid_probability_quote(
        polymarket_quote.bid_probability,
        polymarket_quote.ask_probability,
    ) || !is_valid_deribit_quote(deribit_quote)
    {
        return reject_pair(
            RejectionReason::InvalidQuote,
            deribit_quote,
            polymarket_quote,
        );
    }

    let model_probability = mock_model_probability_from_mark_iv(deribit_quote.mark_iv);
    let polymarket_mid_probability =
        (polymarket_quote.bid_probability + polymarket_quote.ask_probability) / 2.0;
    let gross_edge_probability = model_probability - polymarket_mid_probability;

    let feature = ProbabilityBasisFeature {
        meta: feature_meta(deribit_quote, polymarket_quote),
        deribit_instrument_id: deribit_quote.meta.instrument_id.clone(),
        polymarket_market_slug: polymarket_quote.market_slug.clone(),
        model_probability,
        polymarket_mid_probability,
        gross_edge_probability,
        estimated_cost_probability: config.estimated_cost_probability,
    };

    let net_edge_probability = feature.net_edge_probability();
    let survives_costs = feature.survives_costs(config.min_net_edge_probability);

    if !survives_costs {
        return reject_pair(
            RejectionReason::EdgeBelowThreshold,
            deribit_quote,
            polymarket_quote,
        );
    }

    MatchDecision::Matched {
        feature,
        net_edge_probability,
        survives_costs,
    }
}

pub fn match_from_market_events(
    events: &[MarketEvent],
    config: &ProbabilityBasisConfig,
) -> Vec<MatchDecision> {
    let deribit_quotes: Vec<&DeribitOptionQuote> = events
        .iter()
        .filter_map(|event| match event {
            MarketEvent::DeribitOptionQuote(quote) => Some(quote),
            MarketEvent::PolymarketOutcomeQuote(_) => None,
        })
        .collect();
    let polymarket_quotes: Vec<&PolymarketOutcomeQuote> = events
        .iter()
        .filter_map(|event| match event {
            MarketEvent::DeribitOptionQuote(_) => None,
            MarketEvent::PolymarketOutcomeQuote(quote) => Some(quote),
        })
        .collect();

    if deribit_quotes.is_empty() {
        return polymarket_quotes
            .into_iter()
            .map(|quote| match_probability_basis(None, Some(quote), config))
            .collect();
    }

    if polymarket_quotes.is_empty() {
        return deribit_quotes
            .into_iter()
            .map(|quote| match_probability_basis(Some(quote), None, config))
            .collect();
    }

    let mut decisions = Vec::new();
    for deribit_quote in deribit_quotes {
        for polymarket_quote in &polymarket_quotes {
            decisions.push(match_probability_basis(
                Some(deribit_quote),
                Some(polymarket_quote),
                config,
            ));
        }
    }

    decisions
}

fn reject_pair(
    reason: RejectionReason,
    deribit_quote: &DeribitOptionQuote,
    polymarket_quote: &PolymarketOutcomeQuote,
) -> MatchDecision {
    MatchDecision::Rejected {
        reason,
        deribit_instrument_id: Some(deribit_quote.meta.instrument_id.clone()),
        polymarket_market_slug: Some(polymarket_quote.market_slug.clone()),
    }
}

fn is_valid_probability_quote(bid: f64, ask: f64) -> bool {
    bid.is_finite() && ask.is_finite() && bid >= 0.0 && ask <= 1.0 && bid <= ask
}

fn is_valid_deribit_quote(quote: &DeribitOptionQuote) -> bool {
    quote.bid.is_finite()
        && quote.ask.is_finite()
        && quote.mark_iv.is_finite()
        && quote.bid >= 0.0
        && quote.bid <= quote.ask
        && quote.mark_iv > 0.0
}

fn mock_model_probability_from_mark_iv(mark_iv: f64) -> f64 {
    mark_iv.clamp(0.0, 1.0)
}

fn feature_meta(
    deribit_quote: &DeribitOptionQuote,
    polymarket_quote: &PolymarketOutcomeQuote,
) -> EventMeta {
    EventMeta {
        event_id: format!(
            "probability-basis:{}:{}",
            deribit_quote.meta.event_id, polymarket_quote.meta.event_id
        ),
        source: "probability_basis_matcher".to_string(),
        exchange_ts_ms: deribit_quote
            .meta
            .exchange_ts_ms
            .max(polymarket_quote.meta.exchange_ts_ms),
        received_ts_ms: deribit_quote
            .meta
            .received_ts_ms
            .max(polymarket_quote.meta.received_ts_ms),
        instrument_id: format!(
            "{}|{}",
            deribit_quote.meta.instrument_id, polymarket_quote.market_slug
        ),
        schema_version: deribit_quote
            .meta
            .schema_version
            .max(polymarket_quote.meta.schema_version),
        config_version: deribit_quote.meta.config_version.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::events::{EventMeta, OptionKind};

    fn meta(event_id: &str, instrument_id: &str, exchange_ts_ms: i64) -> EventMeta {
        EventMeta {
            event_id: event_id.to_string(),
            source: "golden-fixture".to_string(),
            exchange_ts_ms,
            received_ts_ms: exchange_ts_ms + 100,
            instrument_id: instrument_id.to_string(),
            schema_version: 1,
            config_version: "golden".to_string(),
        }
    }

    fn deribit_quote(mark_iv: f64, expiry_ts_ms: i64) -> DeribitOptionQuote {
        DeribitOptionQuote {
            meta: meta("deribit-quote-1", "ETH-20260601-3000-C", 1_779_200_000_000),
            underlying: "ETH".to_string(),
            expiry_ts_ms,
            strike: 3000.0,
            option_kind: OptionKind::Call,
            bid: 0.12,
            ask: 0.13,
            mark_iv,
        }
    }

    fn polymarket_quote(
        bid_probability: f64,
        ask_probability: f64,
        liquidity_usd: f64,
        event_ts_ms: i64,
    ) -> PolymarketOutcomeQuote {
        PolymarketOutcomeQuote {
            meta: meta("polymarket-quote-1", "eth-above-3000-june-1", event_ts_ms),
            event_slug: "eth-above-3000".to_string(),
            market_slug: "eth-above-3000-june-1".to_string(),
            outcome: "Yes".to_string(),
            bid_probability,
            ask_probability,
            liquidity_usd,
        }
    }

    fn config() -> ProbabilityBasisConfig {
        ProbabilityBasisConfig {
            min_net_edge_probability: 0.025,
            max_expiry_mismatch_ms: 86_400_000,
            min_polymarket_liquidity_usd: 1000.0,
            estimated_cost_probability: 0.010,
        }
    }

    #[test]
    fn matches_pair_when_net_edge_survives_costs() {
        let deribit = deribit_quote(0.62, 1_780_000_000_000);
        let polymarket = polymarket_quote(0.51, 0.53, 10_000.0, 1_780_000_000_000);

        let decision = match_probability_basis(Some(&deribit), Some(&polymarket), &config());

        match decision {
            MatchDecision::Matched {
                feature,
                net_edge_probability,
                survives_costs,
            } => {
                assert_eq!(feature.deribit_instrument_id, "ETH-20260601-3000-C");
                assert_eq!(feature.polymarket_market_slug, "eth-above-3000-june-1");
                assert!((feature.gross_edge_probability - 0.10).abs() < 1e-12);
                assert!((net_edge_probability - 0.09).abs() < 1e-12);
                assert!(survives_costs);
            }
            MatchDecision::Rejected { reason, .. } => {
                panic!("expected match, got rejection: {reason:?}");
            }
        }
    }

    #[test]
    fn rejects_low_liquidity_pair() {
        let deribit = deribit_quote(0.62, 1_780_000_000_000);
        let polymarket = polymarket_quote(0.51, 0.53, 999.0, 1_780_000_000_000);

        let decision = match_probability_basis(Some(&deribit), Some(&polymarket), &config());

        assert_eq!(
            decision,
            MatchDecision::Rejected {
                reason: RejectionReason::InsufficientLiquidity,
                deribit_instrument_id: Some("ETH-20260601-3000-C".to_string()),
                polymarket_market_slug: Some("eth-above-3000-june-1".to_string()),
            }
        );
    }

    #[test]
    fn rejects_edge_below_threshold() {
        let deribit = deribit_quote(0.54, 1_780_000_000_000);
        let polymarket = polymarket_quote(0.51, 0.53, 10_000.0, 1_780_000_000_000);

        let decision = match_probability_basis(Some(&deribit), Some(&polymarket), &config());

        assert_eq!(
            decision,
            MatchDecision::Rejected {
                reason: RejectionReason::EdgeBelowThreshold,
                deribit_instrument_id: Some("ETH-20260601-3000-C".to_string()),
                polymarket_market_slug: Some("eth-above-3000-june-1".to_string()),
            }
        );
    }

    #[test]
    fn golden_replay_fixture_produces_stable_report() {
        let deribit = MarketEvent::DeribitOptionQuote(deribit_quote(0.62, 1_780_000_000_000));
        let matched_polymarket = MarketEvent::PolymarketOutcomeQuote(polymarket_quote(
            0.51,
            0.53,
            10_000.0,
            1_780_000_000_000,
        ));
        let low_liquidity_polymarket =
            MarketEvent::PolymarketOutcomeQuote(PolymarketOutcomeQuote {
                meta: meta(
                    "polymarket-quote-2",
                    "eth-above-3000-low-liquidity",
                    1_780_000_000_000,
                ),
                event_slug: "eth-above-3000-low-liquidity".to_string(),
                market_slug: "eth-above-3000-low-liquidity".to_string(),
                outcome: "Yes".to_string(),
                bid_probability: 0.51,
                ask_probability: 0.53,
                liquidity_usd: 500.0,
            });

        let decisions = match_from_market_events(
            &[deribit, matched_polymarket, low_liquidity_polymarket],
            &config(),
        );

        let report = render_match_report(&decisions);

        assert_eq!(
            report,
            [
                "matched|ETH-20260601-3000-C|eth-above-3000-june-1|net_edge=0.090000|survives=true",
                "rejected|InsufficientLiquidity|ETH-20260601-3000-C|eth-above-3000-low-liquidity",
            ]
        );
    }

    fn render_match_report(decisions: &[MatchDecision]) -> Vec<String> {
        decisions
            .iter()
            .map(|decision| match decision {
                MatchDecision::Matched {
                    feature,
                    net_edge_probability,
                    survives_costs,
                } => format!(
                    "matched|{}|{}|net_edge={:.6}|survives={}",
                    feature.deribit_instrument_id,
                    feature.polymarket_market_slug,
                    net_edge_probability,
                    survives_costs
                ),
                MatchDecision::Rejected {
                    reason,
                    deribit_instrument_id,
                    polymarket_market_slug,
                } => format!(
                    "rejected|{:?}|{}|{}",
                    reason,
                    deribit_instrument_id.as_deref().unwrap_or("none"),
                    polymarket_market_slug.as_deref().unwrap_or("none")
                ),
            })
            .collect()
    }
}
