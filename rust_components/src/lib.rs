// ==================== CRYPTOTEHNOLOG Rust Core Library ====================
// High-performance components for the trading platform
//
// This library provides:
// - Event Bus (Redis/ZeroMQ)
// - Risk Ledger (double-entry accounting)
// - Audit Chain (cryptographic audit trail)
// - Execution Core (low-latency order execution)

// ==================== Module Declarations ====================
pub mod error;
pub mod event;
pub mod utils;

// ==================== Re-exports ====================
// Re-export commonly used types for convenience
pub use error::{CryptoError, Result};
pub use event::Event;

// ==================== Public API ====================
// Utility functions
pub use utils::{clamp, compute_hash, percentage, round, validate_range};

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
        let hash = compute_hash(data);

        assert_eq!(hash.len(), 64); // SHA-256 produces 64 hex characters
        assert!(!hash.is_empty());
    }

    #[test]
    fn test_validate_range_success() {
        let result = validate_range(5, 1, 10);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_range_below_min() {
        let result = validate_range(0, 1, 10);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_range_above_max() {
        let result = validate_range(11, 1, 10);
        assert!(result.is_err());
    }

    #[test]
    fn test_clamp() {
        assert_eq!(clamp(5, 1, 10), 5);
        assert_eq!(clamp(0, 1, 10), 1);
        assert_eq!(clamp(11, 1, 10), 10);
    }
}

