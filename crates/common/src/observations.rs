use crate::events::ProbabilityBasisFeature;
use crate::probability_basis::{MatchDecision, ProbabilityBasisConfig};

#[derive(Debug, Clone, PartialEq)]
pub struct BasisObservation {
    pub event_id: String,
    pub observed_at_ts_ms: i64,
    pub deribit_instrument_id: String,
    pub polymarket_market_slug: String,
    pub model_probability: f64,
    pub polymarket_mid_probability: f64,
    pub gross_edge_probability: f64,
    pub estimated_cost_probability: f64,
    pub net_edge_probability: f64,
    pub survives_costs: bool,
    pub schema_version: u16,
    pub config_version: String,
}

impl BasisObservation {
    pub fn from_feature(feature: &ProbabilityBasisFeature, min_net_edge_probability: f64) -> Self {
        Self {
            event_id: feature.meta.event_id.clone(),
            observed_at_ts_ms: feature.meta.exchange_ts_ms,
            deribit_instrument_id: feature.deribit_instrument_id.clone(),
            polymarket_market_slug: feature.polymarket_market_slug.clone(),
            model_probability: feature.model_probability,
            polymarket_mid_probability: feature.polymarket_mid_probability,
            gross_edge_probability: feature.gross_edge_probability,
            estimated_cost_probability: feature.estimated_cost_probability,
            net_edge_probability: feature.net_edge_probability(),
            survives_costs: feature.survives_costs(min_net_edge_probability),
            schema_version: feature.meta.schema_version,
            config_version: feature.meta.config_version.clone(),
        }
    }
}

pub fn observations_from_match_decisions(
    decisions: &[MatchDecision],
    config: &ProbabilityBasisConfig,
) -> Vec<BasisObservation> {
    decisions
        .iter()
        .filter_map(|decision| match decision {
            MatchDecision::Matched { feature, .. } => Some(BasisObservation::from_feature(
                feature,
                config.min_net_edge_probability,
            )),
            MatchDecision::Rejected { .. } => None,
        })
        .collect()
}

pub const BASIS_OBSERVATIONS_TABLE: &str = "basis_observations";

pub const BASIS_OBSERVATIONS_COLUMNS: [&str; 12] = [
    "event_id",
    "observed_at",
    "deribit_instrument_id",
    "polymarket_market_slug",
    "model_probability",
    "polymarket_mid_probability",
    "gross_edge_probability",
    "estimated_cost_probability",
    "net_edge_probability",
    "survives_costs",
    "schema_version",
    "config_version",
];

#[derive(Debug, Clone, PartialEq)]
pub struct BasisObservationRow {
    pub event_id: String,
    pub observed_at_ts_ms: i64,
    pub deribit_instrument_id: String,
    pub polymarket_market_slug: String,
    pub model_probability: f64,
    pub polymarket_mid_probability: f64,
    pub gross_edge_probability: f64,
    pub estimated_cost_probability: f64,
    pub net_edge_probability: f64,
    pub survives_costs: bool,
    pub schema_version: u16,
    pub config_version: String,
}

impl BasisObservationRow {
    pub fn from_observation(observation: &BasisObservation) -> Self {
        Self {
            event_id: observation.event_id.clone(),
            observed_at_ts_ms: observation.observed_at_ts_ms,
            deribit_instrument_id: observation.deribit_instrument_id.clone(),
            polymarket_market_slug: observation.polymarket_market_slug.clone(),
            model_probability: observation.model_probability,
            polymarket_mid_probability: observation.polymarket_mid_probability,
            gross_edge_probability: observation.gross_edge_probability,
            estimated_cost_probability: observation.estimated_cost_probability,
            net_edge_probability: observation.net_edge_probability,
            survives_costs: observation.survives_costs,
            schema_version: observation.schema_version,
            config_version: observation.config_version.clone(),
        }
    }

    pub fn columns() -> &'static [&'static str; 12] {
        &BASIS_OBSERVATIONS_COLUMNS
    }

    pub fn values(&self) -> [BasisObservationRowValue; 12] {
        [
            BasisObservationRowValue::Text(self.event_id.clone()),
            BasisObservationRowValue::TimestampMillis(self.observed_at_ts_ms),
            BasisObservationRowValue::Text(self.deribit_instrument_id.clone()),
            BasisObservationRowValue::Text(self.polymarket_market_slug.clone()),
            BasisObservationRowValue::Numeric(self.model_probability),
            BasisObservationRowValue::Numeric(self.polymarket_mid_probability),
            BasisObservationRowValue::Numeric(self.gross_edge_probability),
            BasisObservationRowValue::Numeric(self.estimated_cost_probability),
            BasisObservationRowValue::Numeric(self.net_edge_probability),
            BasisObservationRowValue::Bool(self.survives_costs),
            BasisObservationRowValue::Integer(self.schema_version as i64),
            BasisObservationRowValue::Text(self.config_version.clone()),
        ]
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum BasisObservationRowValue {
    Text(String),
    TimestampMillis(i64),
    Integer(i64),
    Numeric(f64),
    Bool(bool),
}

pub trait BasisObservationRowWriter {
    fn append_basis_observation_row(
        &mut self,
        row: BasisObservationRow,
    ) -> Result<(), ObservationWriteError>;
}

pub fn write_basis_observation_rows<W>(
    observations: &[BasisObservation],
    writer: &mut W,
) -> Result<(), ObservationWriteError>
where
    W: BasisObservationRowWriter,
{
    for observation in observations {
        writer.append_basis_observation_row(BasisObservationRow::from_observation(observation))?;
    }

    Ok(())
}

#[derive(Debug, Default, Clone, PartialEq)]
pub struct InMemoryBasisObservationRowWriter {
    rows: Vec<BasisObservationRow>,
}

impl InMemoryBasisObservationRowWriter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn rows(&self) -> &[BasisObservationRow] {
        &self.rows
    }

    fn contains_event_id(&self, event_id: &str) -> bool {
        self.rows.iter().any(|row| row.event_id == event_id)
    }
}

impl BasisObservationRowWriter for InMemoryBasisObservationRowWriter {
    fn append_basis_observation_row(
        &mut self,
        row: BasisObservationRow,
    ) -> Result<(), ObservationWriteError> {
        if self.contains_event_id(&row.event_id) {
            return Err(ObservationWriteError::duplicate_observation(&row.event_id));
        }

        self.rows.push(row);
        Ok(())
    }
}

pub struct PostgresBasisObservationAdapter;

impl PostgresBasisObservationAdapter {
    pub fn table_name() -> &'static str {
        BASIS_OBSERVATIONS_TABLE
    }

    pub fn columns() -> &'static [&'static str; 12] {
        &BASIS_OBSERVATIONS_COLUMNS
    }

    pub fn insert_sql() -> &'static str {
        "INSERT INTO basis_observations (event_id, observed_at, deribit_instrument_id, polymarket_market_slug, model_probability, polymarket_mid_probability, gross_edge_probability, estimated_cost_probability, net_edge_probability, survives_costs, schema_version, config_version) VALUES ($1, to_timestamp($2::double precision / 1000.0), $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)"
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ObservationWriteErrorKind {
    DuplicateObservation,
    Storage,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ObservationWriteError {
    pub kind: ObservationWriteErrorKind,
    pub message: String,
}

impl ObservationWriteError {
    pub fn new(kind: ObservationWriteErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }

    pub fn duplicate_observation(event_id: &str) -> Self {
        Self::new(
            ObservationWriteErrorKind::DuplicateObservation,
            format!("duplicate basis_observation event_id: {event_id}"),
        )
    }
}

pub trait BasisObservationWriter {
    fn append_basis_observation(
        &mut self,
        observation: BasisObservation,
    ) -> Result<(), ObservationWriteError>;
}

#[derive(Debug, Default, Clone)]
pub struct InMemoryBasisObservationWriter {
    observations: Vec<BasisObservation>,
}

impl InMemoryBasisObservationWriter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn observations(&self) -> &[BasisObservation] {
        &self.observations
    }

    fn contains_event_id(&self, event_id: &str) -> bool {
        self.observations
            .iter()
            .any(|observation| observation.event_id == event_id)
    }
}

impl BasisObservationWriter for InMemoryBasisObservationWriter {
    fn append_basis_observation(
        &mut self,
        observation: BasisObservation,
    ) -> Result<(), ObservationWriteError> {
        if self.contains_event_id(&observation.event_id) {
            return Err(ObservationWriteError::duplicate_observation(
                &observation.event_id,
            ));
        }

        self.observations.push(observation);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::events::{EventMeta, ProbabilityBasisFeature};

    fn feature() -> ProbabilityBasisFeature {
        ProbabilityBasisFeature {
            meta: EventMeta {
                event_id: "probability-basis:d:p".to_string(),
                source: "probability_basis_matcher".to_string(),
                exchange_ts_ms: 1_780_000_000_000,
                received_ts_ms: 1_780_000_000_100,
                instrument_id: "ETH-20260601-3000-C|eth-above-3000-june-1".to_string(),
                schema_version: 1,
                config_version: "test".to_string(),
            },
            deribit_instrument_id: "ETH-20260601-3000-C".to_string(),
            polymarket_market_slug: "eth-above-3000-june-1".to_string(),
            model_probability: 0.611338,
            polymarket_mid_probability: 0.520000,
            gross_edge_probability: 0.091338,
            estimated_cost_probability: 0.010000,
        }
    }

    #[test]
    fn basis_observation_maps_feature_to_table_contract() {
        let observation = BasisObservation::from_feature(&feature(), 0.025);

        assert_eq!(observation.event_id, "probability-basis:d:p");
        assert_eq!(observation.observed_at_ts_ms, 1_780_000_000_000);
        assert_eq!(observation.deribit_instrument_id, "ETH-20260601-3000-C");
        assert_eq!(observation.polymarket_market_slug, "eth-above-3000-june-1");
        assert!((observation.net_edge_probability - 0.081338).abs() < 1e-6);
        assert!(observation.survives_costs);
    }

    #[test]
    fn basis_observation_row_serializes_in_postgres_column_order() {
        let observation = BasisObservation::from_feature(&feature(), 0.025);
        let row = BasisObservationRow::from_observation(&observation);

        assert_eq!(
            BasisObservationRow::columns(),
            &[
                "event_id",
                "observed_at",
                "deribit_instrument_id",
                "polymarket_market_slug",
                "model_probability",
                "polymarket_mid_probability",
                "gross_edge_probability",
                "estimated_cost_probability",
                "net_edge_probability",
                "survives_costs",
                "schema_version",
                "config_version",
            ]
        );
        let values = row.values();
        assert_eq!(
            values[0],
            BasisObservationRowValue::Text("probability-basis:d:p".to_string())
        );
        assert_eq!(
            values[1],
            BasisObservationRowValue::TimestampMillis(1_780_000_000_000)
        );
        assert_eq!(
            values[2],
            BasisObservationRowValue::Text("ETH-20260601-3000-C".to_string())
        );
        assert_eq!(
            values[3],
            BasisObservationRowValue::Text("eth-above-3000-june-1".to_string())
        );
        assert_numeric_value(&values[4], 0.611338);
        assert_numeric_value(&values[5], 0.520000);
        assert_numeric_value(&values[6], 0.091338);
        assert_numeric_value(&values[7], 0.010000);
        assert_numeric_value(&values[8], 0.081338);
        assert_eq!(values[9], BasisObservationRowValue::Bool(true));
        assert_eq!(values[10], BasisObservationRowValue::Integer(1));
        assert_eq!(
            values[11],
            BasisObservationRowValue::Text("test".to_string())
        );
    }

    #[test]
    fn postgres_adapter_skeleton_exposes_stable_insert_contract() {
        assert_eq!(
            PostgresBasisObservationAdapter::columns(),
            BasisObservationRow::columns()
        );
        assert_eq!(
            PostgresBasisObservationAdapter::insert_sql(),
            "INSERT INTO basis_observations (event_id, observed_at, deribit_instrument_id, polymarket_market_slug, model_probability, polymarket_mid_probability, gross_edge_probability, estimated_cost_probability, net_edge_probability, survives_costs, schema_version, config_version) VALUES ($1, to_timestamp($2::double precision / 1000.0), $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)"
        );
    }

    #[test]
    fn in_memory_writer_rejects_duplicate_observation_ids() {
        let observation = BasisObservation::from_feature(&feature(), 0.025);
        let mut writer = InMemoryBasisObservationWriter::new();

        writer
            .append_basis_observation(observation.clone())
            .expect("first observation should append");
        let error = writer.append_basis_observation(observation).unwrap_err();

        assert_eq!(error.kind, ObservationWriteErrorKind::DuplicateObservation);
    }

    #[test]
    fn basis_observation_row_writer_failure_is_returned_without_panic() {
        #[derive(Debug, Default)]
        struct FailingBasisObservationRowWriter {
            attempts: usize,
        }

        impl BasisObservationRowWriter for FailingBasisObservationRowWriter {
            fn append_basis_observation_row(
                &mut self,
                _row: BasisObservationRow,
            ) -> Result<(), ObservationWriteError> {
                self.attempts += 1;
                Err(ObservationWriteError::new(
                    ObservationWriteErrorKind::Storage,
                    "simulated basis observation row writer failure",
                ))
            }
        }

        let observation = BasisObservation::from_feature(&feature(), 0.025);
        let observations = vec![observation];
        let mut writer = FailingBasisObservationRowWriter::default();

        let error = write_basis_observation_rows(&observations, &mut writer)
            .expect_err("row writer storage failure should be returned");

        assert_eq!(error.kind, ObservationWriteErrorKind::Storage);
        assert!(error.message.contains("simulated basis observation"));
        assert_eq!(writer.attempts, 1);
    }

    #[test]
    fn in_memory_basis_observation_row_writer_preserves_rows_and_rejects_duplicates() {
        let observation = BasisObservation::from_feature(&feature(), 0.025);
        let row = BasisObservationRow::from_observation(&observation);
        let mut writer = InMemoryBasisObservationRowWriter::new();

        write_basis_observation_rows(std::slice::from_ref(&observation), &mut writer)
            .expect("first row should append");
        assert_eq!(writer.rows(), std::slice::from_ref(&row));

        let error = write_basis_observation_rows(&[observation], &mut writer)
            .expect_err("duplicate row should be rejected");
        assert_eq!(error.kind, ObservationWriteErrorKind::DuplicateObservation);
        assert_eq!(writer.rows().len(), 1);
    }

    fn assert_numeric_value(value: &BasisObservationRowValue, expected: f64) {
        let BasisObservationRowValue::Numeric(actual) = value else {
            panic!("expected numeric row value, got {value:?}");
        };
        assert!((actual - expected).abs() < 1e-12);
    }
}
