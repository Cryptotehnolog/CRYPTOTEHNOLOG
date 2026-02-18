// ==================== CRYPTOTEHNOLOG Rust Core Library ====================
// High-performance components for the trading platform
//
// This library provides:
// - Event Bus (Redis/ZeroMQ)
// - Risk Ledger (double-entry accounting)
// - Audit Chain (cryptographic audit trail)
// - Execution Core (low-latency order execution)

// ==================== Error Types ====================
pub mod error {
    use thiserror::Error;

    /// Main error type for CRYPTOTEHNOLOG Core
    #[derive(Error, Debug)]
    pub enum CryptoError {
        #[error("IO error: {0}")]
        Io(#[from] std::io::Error),

        #[error("Serialization error: {0}")]
        Serialization(#[from] serde_json::Error),

        #[error("Redis error: {0}")]
        Redis(String),

        #[error("Cryptography error: {0}")]
        Cryptography(String),

        #[error("Validation error: {0}")]
        Validation(String),

        #[error("Network error: {0}")]
        Network(String),

        #[error("Configuration error: {0}")]
        Configuration(String),

        #[error("Internal error: {0}")]
        Internal(String),
    }

    /// Result type alias
    pub type Result<T> = std::result::Result<T, CryptoError>;
}

// Re-export commonly used types
pub use error::{CryptoError, Result};

// ==================== Event Types ====================
pub mod event {
    use chrono::{DateTime, Utc};
    use serde::{Deserialize, Serialize};
    use uuid::Uuid;

    /// Core event type for the event bus
    #[derive(Debug, Clone, Serialize, Deserialize)]
    pub struct Event {
        /// Unique event ID
        pub id: Uuid,

        /// Event type (e.g., "ORDER_SUBMITTED", "POSITION_OPENED")
        pub event_type: String,

        /// Event source (e.g., "RISK_ENGINE", "EXECUTION_CORE")
        pub source: String,

        /// Event timestamp
        pub timestamp: DateTime<Utc>,

        /// Event payload (JSON)
        pub payload: serde_json::Value,

        /// Optional correlation ID for tracking
        pub correlation_id: Option<Uuid>,

        /// Event metadata
        pub metadata: serde_json::Value,
    }

    impl Event {
        /// Create a new event
        pub fn new(
            event_type: impl Into<String>,
            source: impl Into<String>,
            payload: serde_json::Value,
        ) -> Self {
            Self {
                id: Uuid::new_v4(),
                event_type: event_type.into(),
                source: source.into(),
                timestamp: Utc::now(),
                payload,
                correlation_id: None,
                metadata: serde_json::json!({}),
            }
        }

        /// Create a new event with correlation ID
        pub fn with_correlation_id(
            event_type: impl Into<String>,
            source: impl Into<String>,
            payload: serde_json::Value,
            correlation_id: Uuid,
        ) -> Self {
            let mut event = Self::new(event_type, source, payload);
            event.correlation_id = Some(correlation_id);
            event
        }

        /// Add metadata to the event
        pub fn with_metadata(mut self, key: &str, value: serde_json::Value) -> Self {
            self.metadata[key] = value;
            self
        }
    }
}

// Re-export Event
pub use event::Event;

// ==================== Utilities ====================
pub mod utils {
    use super::error::Result;
    use sha2::{Digest, Sha256};

    /// Compute SHA-256 hash of data
    pub fn compute_hash(data: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data);
        let result = hasher.finalize();
        hex::encode(result)
    }

    /// Validate that a value is within a range
    pub fn validate_range<T>(value: T, min: T, max: T) -> Result<()>
    where
        T: PartialOrd + std::fmt::Display,
    {
        if value < min {
            return Err(super::error::CryptoError::Validation(format!(
                "Value {} is below minimum {}",
                value, min
            )));
        }
        if value > max {
            return Err(super::error::CryptoError::Validation(format!(
                "Value {} is above maximum {}",
                value, max
            )));
        }
        Ok(())
    }

    /// Clamp a value to a range
    pub fn clamp<T>(value: T, min: T, max: T) -> T
    where
        T: PartialOrd + Ord,
    {
        if value < min {
            min
        } else if value > max {
            max
        } else {
            value
        }
    }
}

// ==================== Tests ====================
#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn test_event_creation() {
        let event = Event::new(
            "TEST_EVENT",
            "TEST_SOURCE",
            serde_json::json!({"key": "value"}),
        );

        assert_eq!(event.event_type, "TEST_EVENT");
        assert_eq!(event.source, "TEST_SOURCE");
        assert_eq!(event.payload["key"], "value");
        assert!(event.correlation_id.is_none());
    }

    #[test]
    fn test_event_with_correlation_id() {
        let correlation_id = Uuid::new_v4();
        let event = Event::with_correlation_id(
            "TEST_EVENT",
            "TEST_SOURCE",
            serde_json::json!({}),
            correlation_id,
        );

        assert_eq!(event.correlation_id, Some(correlation_id));
    }

    #[test]
    fn test_event_with_metadata() {
        let event = Event::new(
            "TEST_EVENT",
            "TEST_SOURCE",
            serde_json::json!({}),
        )
        .with_metadata("meta_key", serde_json::json!("meta_value"));

        assert_eq!(event.metadata["meta_key"], "meta_value");
    }

    #[test]
    fn test_compute_hash() {
        let data = b"test data";
        let hash = utils::compute_hash(data);

        assert_eq!(hash.len(), 64); // SHA-256 produces 64 hex characters
        assert!(!hash.is_empty());
    }

    #[test]
    fn test_validate_range_success() {
        let result = utils::validate_range(5, 1, 10);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_range_below_min() {
        let result = utils::validate_range(0, 1, 10);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_range_above_max() {
        let result = utils::validate_range(11, 1, 10);
        assert!(result.is_err());
    }

    #[test]
    fn test_clamp() {
        assert_eq!(utils::clamp(5, 1, 10), 5);
        assert_eq!(utils::clamp(0, 1, 10), 1);
        assert_eq!(utils::clamp(11, 1, 10), 10);
    }
}
