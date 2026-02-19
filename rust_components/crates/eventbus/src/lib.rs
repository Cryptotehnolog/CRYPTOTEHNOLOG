// ==================== CRYPTOTEHNOLOG Event Bus Crate ====================
// High-performance event bus for inter-component communication

pub mod event;

// ==================== Re-exports ====================
pub use event::Event;

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
        let event = Event::new("TEST_EVENT", "TEST_SOURCE", serde_json::json!({}))
            .with_metadata("meta_key", serde_json::json!("meta_value"));

        assert_eq!(event.metadata["meta_key"], "meta_value");
    }
}
