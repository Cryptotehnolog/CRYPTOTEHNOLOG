// ==================== CRYPTOTEHNOLOG Event Types ====================
// Core event types for the event bus

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Core event type for the event bus
///
/// Events are the primary communication mechanism between components
/// in the CRYPTOTEHNOLOG trading platform.
///
/// # Examples
///
/// ```rust,ignore
/// use cryptotechnolog_core::Event;
/// use serde_json::json;
///
/// let event = Event::new(
///     "ORDER_SUBMITTED",
///     "RISK_ENGINE",
///     json!({"symbol": "BTCUSDT", "quantity": 0.1}),
/// );
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    /// Unique event ID
    pub id: Uuid,

    /// Event type (e.g., "ORDER_SUBMITTED", "POSITION_OPENED")
    pub event_type: String,

    /// Event source (e.g., "RISK_ENGINE", "EXECUTION_CORE")
    pub source: String,

    /// Event timestamp (UTC)
    pub timestamp: DateTime<Utc>,

    /// Event payload (JSON data)
    pub payload: serde_json::Value,

    /// Optional correlation ID for tracking related events
    pub correlation_id: Option<Uuid>,

    /// Event metadata (additional context)
    pub metadata: serde_json::Value,
}

impl Event {
    /// Create a new event
    ///
    /// # Arguments
    ///
    /// * `event_type` - Type of the event (e.g., "ORDER_SUBMITTED")
    /// * `source` - Source of the event (e.g., "RISK_ENGINE")
    /// * `payload` - Event payload as JSON
    ///
    /// # Returns
    ///
    /// A new Event instance with generated ID and current timestamp
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
    ///
    /// Use this when creating events that are part of a larger workflow
    /// and need to be traced together.
    ///
    /// # Arguments
    ///
    /// * `event_type` - Type of the event
    /// * `source` - Source of the event
    /// * `payload` - Event payload
    /// * `correlation_id` - ID to correlate related events
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
    ///
    /// # Arguments
    ///
    /// * `key` - Metadata key
    /// * `value` - Metadata value
    ///
    /// # Returns
    ///
    /// Self for method chaining
    pub fn with_metadata(mut self, key: &str, value: serde_json::Value) -> Self {
        self.metadata[key] = value;
        self
    }

    /// Check if this event is correlated with another event
    ///
    /// # Arguments
    ///
    /// * `other` - Another event to check correlation with
    ///
    /// # Returns
    ///
    /// True if events share the same correlation ID
    pub fn is_correlated_with(&self, other: &Event) -> bool {
        match (&self.correlation_id, &other.correlation_id) {
            (Some(id1), Some(id2)) => id1 == id2,
            _ => false,
        }
    }

    /// Get event age in seconds
    ///
    /// # Returns
    ///
    /// Number of seconds since the event was created
    pub fn age_seconds(&self) -> i64 {
        (Utc::now() - self.timestamp).num_seconds()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
        let event = Event::new("TEST_EVENT", "TEST_SOURCE", serde_json::json!({}))
            .with_metadata("meta_key", serde_json::json!("meta_value"));

        assert_eq!(event.metadata["meta_key"], "meta_value");
    }

    #[test]
    fn test_event_correlation() {
        let correlation_id = Uuid::new_v4();
        let event1 =
            Event::with_correlation_id("EVENT1", "SOURCE1", serde_json::json!({}), correlation_id);
        let event2 =
            Event::with_correlation_id("EVENT2", "SOURCE2", serde_json::json!({}), correlation_id);
        let event3 = Event::new("EVENT3", "SOURCE3", serde_json::json!({}));

        assert!(event1.is_correlated_with(&event2));
        assert!(!event1.is_correlated_with(&event3));
    }

    #[test]
    fn test_event_age() {
        let event = Event::new("TEST", "SOURCE", serde_json::json!({}));
        let age = event.age_seconds();
        assert!(age >= 0);
        assert!(age < 1); // Should be very recent
    }
}
