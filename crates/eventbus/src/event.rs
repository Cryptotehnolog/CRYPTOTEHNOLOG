// ==================== CRYPTOTEHNOLOG Event Types ====================
// Core event types for the event bus

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::priority::Priority;

/// Core event type for the event bus
///
/// Events are the primary communication mechanism between components
/// in the CRYPTOTEHNOLOG trading platform.
///
/// # Examples
///
/// ```rust,ignore
/// use cryptotechnolog_eventbus::Event;
/// use cryptotechnolog_eventbus::priority::Priority;
/// use serde_json::json;
///
/// let event = Event::new(
///     "ORDER_SUBMITTED",
///     "RISK_ENGINE",
///     json!({"symbol": "BTCUSDT", "quantity": 0.1}),
/// );
///
/// // Событие с высоким приоритетом
/// let critical_event = Event::new(
///     "KILL_SWITCH_TRIGGERED",
///     "SYSTEM",
///     json!({"reason": "manual_trigger"}),
/// ).with_priority(Priority::Critical);
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    /// Unique event ID (UUID v4)
    pub id: Uuid,

    /// Event type (e.g., "ORDER_SUBMITTED", "POSITION_OPENED")
    pub event_type: String,

    /// Event source (e.g., "RISK_ENGINE", "EXECUTION_CORE")
    pub source: String,

    /// Event timestamp (UTC)
    pub timestamp: DateTime<Utc>,

    /// Event priority (Critical/High/Normal/Low)
    /// По умолчанию Normal
    pub priority: Priority,

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
    /// По умолчанию событие создается с приоритетом Normal
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
            priority: Priority::default(), // Normal
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

    /// Set priority for the event
    ///
    /// Позволяет создать копию события с указанным приоритетом
    ///
    /// # Arguments
    ///
    /// * `priority` - Приоритет события (Critical/High/Normal/Low)
    ///
    /// # Returns
    ///
    /// Self для цепочки вызовов
    pub fn with_priority(mut self, priority: Priority) -> Self {
        self.priority = priority;
        self
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

    /// Check if this event requires persistence
    ///
    /// # Returns
    ///
    /// true если событие должно быть сохранено в persistence layer
    pub fn requires_persistence(&self) -> bool {
        self.priority.requires_persistence()
    }

    /// Check if this event can be dropped
    ///
    /// # Returns
    ///
    /// true если событие может быть отброшено при backpressure
    pub fn is_droppable(&self) -> bool {
        self.priority.is_droppable()
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
        assert_eq!(event.priority, Priority::Normal); // По умолчанию Normal
    }

    #[test]
    fn test_event_with_priority() {
        let event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Critical);
        
        assert_eq!(event.priority, Priority::Critical);
        
        let high_event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::High);
        assert_eq!(high_event.priority, Priority::High);
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

    #[test]
    fn test_event_requires_persistence() {
        let critical_event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Critical);
        assert!(critical_event.requires_persistence());

        let high_event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::High);
        assert!(high_event.requires_persistence());

        let normal_event = Event::new("TEST", "SOURCE", serde_json::json!({}));
        assert!(!normal_event.requires_persistence());
    }

    #[test]
    fn test_event_is_droppable() {
        let critical_event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Critical);
        assert!(!critical_event.is_droppable());

        let low_event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Low);
        assert!(low_event.is_droppable());
    }
}
