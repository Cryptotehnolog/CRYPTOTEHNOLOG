use crate::events::{
    DeribitOptionQuote, EventMeta, MarketEvent, OptionKind, PolymarketOutcomeQuote,
    ProbabilityBasisFeature,
};

pub const PRICING_MODEL_VERSION: &str = "black_scholes_single_strike_v1";

#[derive(Debug, Clone, PartialEq)]
pub struct ProbabilityBasisConfig {
    pub min_net_edge_probability: f64,
    pub max_expiry_mismatch_ms: i64,
    pub max_quote_time_skew_ms: i64,
    pub min_polymarket_liquidity_usd: f64,
    pub estimated_cost_probability: f64,
    pub risk_free_rate: f64,
    pub dividend_yield: f64,
    pub milliseconds_per_year: f64,
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
    StalePair,
    InvalidQuote,
    ExpiredOption,
    InvalidModelInput,
    MidEdgeFalsePositive,
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
        (deribit_quote.expiry_ts_ms - polymarket_quote.target_expiry_ts_ms).abs();
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

    let quote_time_skew_ms =
        (deribit_quote.meta.exchange_ts_ms - polymarket_quote.meta.exchange_ts_ms).abs();
    if quote_time_skew_ms > config.max_quote_time_skew_ms {
        return reject_pair(RejectionReason::StalePair, deribit_quote, polymarket_quote);
    }

    if deribit_quote.expiry_ts_ms <= deribit_quote.meta.exchange_ts_ms {
        return reject_pair(
            RejectionReason::ExpiredOption,
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

    let Some(model_probability) = black_scholes_call_probability(deribit_quote, config) else {
        return reject_pair(
            RejectionReason::InvalidModelInput,
            deribit_quote,
            polymarket_quote,
        );
    };
    let polymarket_mid_probability =
        (polymarket_quote.bid_probability + polymarket_quote.ask_probability) / 2.0;
    let gross_mid_edge_probability = model_probability - polymarket_mid_probability;
    let polymarket_executable_probability =
        executable_polymarket_probability(model_probability, polymarket_quote);
    let gross_executable_edge_probability = model_probability - polymarket_executable_probability;

    let feature = ProbabilityBasisFeature {
        meta: feature_meta(deribit_quote, polymarket_quote),
        deribit_instrument_id: deribit_quote.meta.instrument_id.clone(),
        polymarket_market_slug: polymarket_quote.market_slug.clone(),
        model_probability,
        polymarket_mid_probability,
        polymarket_executable_probability,
        gross_mid_edge_probability,
        gross_executable_edge_probability,
        gross_edge_probability: gross_executable_edge_probability,
        estimated_cost_probability: config.estimated_cost_probability,
    };

    let net_edge_probability = feature.net_edge_probability();
    let survives_costs = feature.survives_costs(config.min_net_edge_probability);

    if !survives_costs {
        let midpoint_net_edge_probability =
            gross_mid_edge_probability.abs() - config.estimated_cost_probability;
        if midpoint_net_edge_probability >= config.min_net_edge_probability {
            return reject_pair(
                RejectionReason::MidEdgeFalsePositive,
                deribit_quote,
                polymarket_quote,
            );
        }

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

pub fn render_match_report(decisions: &[MatchDecision]) -> Vec<String> {
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
        && quote.underlying_price.is_finite()
        && quote.bid >= 0.0
        && quote.bid <= quote.ask
        && quote.strike > 0.0
        && quote.mark_iv > 0.0
        && quote.underlying_price > 0.0
}

fn executable_polymarket_probability(
    model_probability: f64,
    quote: &PolymarketOutcomeQuote,
) -> f64 {
    let mid_probability = (quote.bid_probability + quote.ask_probability) / 2.0;
    if model_probability >= mid_probability {
        quote.ask_probability
    } else {
        quote.bid_probability
    }
}

fn black_scholes_call_probability(
    quote: &DeribitOptionQuote,
    config: &ProbabilityBasisConfig,
) -> Option<f64> {
    if quote.expiry_ts_ms <= quote.meta.exchange_ts_ms {
        return None;
    }

    if !config.milliseconds_per_year.is_finite() || config.milliseconds_per_year <= 0.0 {
        return None;
    }

    let time_to_expiry_years =
        (quote.expiry_ts_ms - quote.meta.exchange_ts_ms) as f64 / config.milliseconds_per_year;
    if !time_to_expiry_years.is_finite() || time_to_expiry_years <= 0.0 {
        return None;
    }

    let sigma_sqrt_t = quote.mark_iv * time_to_expiry_years.sqrt();
    if !sigma_sqrt_t.is_finite() || sigma_sqrt_t <= 0.0 {
        return None;
    }

    let drift =
        (config.risk_free_rate - config.dividend_yield - 0.5 * quote.mark_iv * quote.mark_iv)
            * time_to_expiry_years;
    let d2 = ((quote.underlying_price / quote.strike).ln() + drift) / sigma_sqrt_t;

    Some(standard_normal_cdf(d2))
}

fn standard_normal_cdf(x: f64) -> f64 {
    0.5 * (1.0 + erf_approx(x / std::f64::consts::SQRT_2))
}

fn erf_approx(x: f64) -> f64 {
    let sign = if x < 0.0 { -1.0 } else { 1.0 };
    let x = x.abs();
    let t = 1.0 / (1.0 + 0.3275911 * x);
    let y = 1.0
        - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
            + 0.254829592)
            * t
            * (-x * x).exp();

    sign * y
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

    fn deribit_quote(mark_iv: f64, underlying_price: f64, expiry_ts_ms: i64) -> DeribitOptionQuote {
        DeribitOptionQuote {
            meta: meta("deribit-quote-1", "ETH-20260601-3000-C", 1_779_200_000_000),
            underlying: "ETH".to_string(),
            expiry_ts_ms,
            strike: 3000.0,
            option_kind: OptionKind::Call,
            underlying_price,
            bid: 0.12,
            ask: 0.13,
            mark_iv,
        }
    }

    fn polymarket_quote(
        bid_probability: f64,
        ask_probability: f64,
        liquidity_usd: f64,
        target_expiry_ts_ms: i64,
    ) -> PolymarketOutcomeQuote {
        PolymarketOutcomeQuote {
            meta: meta(
                "polymarket-quote-1",
                "eth-above-3000-june-1",
                1_779_200_000_000,
            ),
            event_slug: "eth-above-3000".to_string(),
            market_slug: "eth-above-3000-june-1".to_string(),
            outcome: "Yes".to_string(),
            target_expiry_ts_ms,
            bid_probability,
            ask_probability,
            liquidity_usd,
        }
    }

    fn config() -> ProbabilityBasisConfig {
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

    #[test]
    fn matches_pair_when_net_edge_survives_costs() {
        let deribit = deribit_quote(0.62, 3100.0, 1_780_000_000_000);
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
                assert!((feature.gross_mid_edge_probability - 0.091338).abs() < 1e-6);
                assert!((feature.gross_executable_edge_probability - 0.081338).abs() < 1e-6);
                assert!((feature.gross_edge_probability - 0.081338).abs() < 1e-6);
                assert!((net_edge_probability - 0.071338).abs() < 1e-6);
                assert!(survives_costs);
            }
            MatchDecision::Rejected { reason, .. } => {
                panic!("expected match, got rejection: {reason:?}");
            }
        }
    }

    #[test]
    fn rejects_low_liquidity_pair() {
        let deribit = deribit_quote(0.62, 3100.0, 1_780_000_000_000);
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
    fn rejects_stale_cross_source_pair() {
        let deribit = deribit_quote(0.62, 3100.0, 1_780_000_000_000);
        let mut polymarket = polymarket_quote(0.51, 0.53, 10_000.0, 1_780_000_000_000);
        polymarket.meta.exchange_ts_ms = deribit.meta.exchange_ts_ms + 10_000;
        let mut config = config();
        config.max_quote_time_skew_ms = 5_000;

        let decision = match_probability_basis(Some(&deribit), Some(&polymarket), &config);

        assert_eq!(
            decision,
            MatchDecision::Rejected {
                reason: RejectionReason::StalePair,
                deribit_instrument_id: Some("ETH-20260601-3000-C".to_string()),
                polymarket_market_slug: Some("eth-above-3000-june-1".to_string()),
            }
        );
    }

    #[test]
    fn rejects_edge_below_threshold() {
        let deribit = deribit_quote(0.62, 3030.0, 1_780_000_000_000);
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
        let deribit =
            MarketEvent::DeribitOptionQuote(deribit_quote(0.62, 3100.0, 1_780_000_000_000));
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
                target_expiry_ts_ms: 1_780_000_000_000,
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
                "matched|ETH-20260601-3000-C|eth-above-3000-june-1|net_edge=0.071338|survives=true",
                "rejected|InsufficientLiquidity|ETH-20260601-3000-C|eth-above-3000-low-liquidity",
            ]
        );
    }

    #[test]
    fn rejects_when_mid_edge_survives_but_executable_edge_does_not() {
        let deribit = deribit_quote(0.62, 3100.0, 1_780_000_000_000);
        let polymarket = polymarket_quote(0.54, 0.60, 10_000.0, 1_780_000_000_000);

        let decision = match_probability_basis(Some(&deribit), Some(&polymarket), &config());

        assert_eq!(
            decision,
            MatchDecision::Rejected {
                reason: RejectionReason::MidEdgeFalsePositive,
                deribit_instrument_id: Some("ETH-20260601-3000-C".to_string()),
                polymarket_market_slug: Some("eth-above-3000-june-1".to_string()),
            }
        );
    }

    #[test]
    fn rejects_zero_and_negative_iv() {
        for mark_iv in [0.0, -0.1] {
            let deribit = deribit_quote(mark_iv, 3600.0, 1_780_000_000_000);
            let polymarket = polymarket_quote(0.51, 0.53, 10_000.0, 1_780_000_000_000);

            let decision = match_probability_basis(Some(&deribit), Some(&polymarket), &config());

            assert_eq!(
                decision,
                MatchDecision::Rejected {
                    reason: RejectionReason::InvalidQuote,
                    deribit_instrument_id: Some("ETH-20260601-3000-C".to_string()),
                    polymarket_market_slug: Some("eth-above-3000-june-1".to_string()),
                }
            );
        }
    }

    #[test]
    fn rejects_expired_option() {
        let deribit = deribit_quote(0.62, 3600.0, 1_779_199_999_999);
        let polymarket = polymarket_quote(0.51, 0.53, 10_000.0, 1_779_199_999_999);

        let decision = match_probability_basis(Some(&deribit), Some(&polymarket), &config());

        assert_eq!(
            decision,
            MatchDecision::Rejected {
                reason: RejectionReason::ExpiredOption,
                deribit_instrument_id: Some("ETH-20260601-3000-C".to_string()),
                polymarket_market_slug: Some("eth-above-3000-june-1".to_string()),
            }
        );
    }

    #[test]
    fn black_scholes_deep_itm_and_otm_behaviour_is_ordered() {
        let expiry = 1_780_000_000_000;
        let deep_otm = deribit_quote(0.50, 1500.0, expiry);
        let at_the_money = deribit_quote(0.50, 3000.0, expiry);
        let deep_itm = deribit_quote(0.50, 6000.0, expiry);

        let config = config();
        let otm_probability = black_scholes_call_probability(&deep_otm, &config).unwrap();
        let atm_probability = black_scholes_call_probability(&at_the_money, &config).unwrap();
        let itm_probability = black_scholes_call_probability(&deep_itm, &config).unwrap();

        assert!(otm_probability < atm_probability);
        assert!(atm_probability < itm_probability);
        assert!(otm_probability < 0.05);
        assert!(itm_probability > 0.90);
    }

    #[test]
    fn standard_normal_cdf_is_deterministic_and_symmetric() {
        assert!((standard_normal_cdf(0.0) - 0.5).abs() < 1e-7);
        assert!((standard_normal_cdf(1.0) - 0.841344736).abs() < 1e-6);
        assert!((standard_normal_cdf(-1.0) - 0.158655264).abs() < 1e-6);
        assert!((standard_normal_cdf(1.0) + standard_normal_cdf(-1.0) - 1.0).abs() < 1e-6);
    }

    #[test]
    fn black_scholes_uses_configured_rate_assumptions() {
        let quote = deribit_quote(0.62, 3100.0, 1_780_000_000_000);
        let base = config();
        let mut higher_rate = base.clone();
        higher_rate.risk_free_rate = 0.05;

        let base_probability = black_scholes_call_probability(&quote, &base).unwrap();
        let higher_rate_probability = black_scholes_call_probability(&quote, &higher_rate).unwrap();

        assert!(higher_rate_probability > base_probability);
    }

    #[test]
    fn pricing_model_version_is_explicit() {
        assert_eq!(PRICING_MODEL_VERSION, "black_scholes_single_strike_v1");
    }
}
