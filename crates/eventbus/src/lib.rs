// ==================== CRYPTOTEHNOLOG Event Bus Crate ====================
// High-performance event bus for inter-component communication
//
// # Features
//
// - **Lock-free ring buffer backend** (with "lock-free" feature):
//   - Wait-free read operations
//   - Lock-free write operations
//   - Bounded capacity to prevent unbounded memory growth
//   - Optimal for high-throughput scenarios
//
// - **Standard channel-based backend** (default):
//   - Uses std::sync::mpsc channels
//   - Unbounded or bounded channels
//   - Zero-copy message passing
//   - Backpressure support
//
// - **Graceful degradation on buffer overflow**:
//   - Returns error when buffer is full (instead of blocking)
//   - Allows application to handle overflow scenarios
//   - Prevents deadlocks and priority inversion
//
// - **Multiple subscribers support**:
//   - Broadcast events to multiple consumers
//   - Each subscriber gets a copy of each event
//   - Independent consumer processing
//
// # Example
//
// ```rust,ignore
// use cryptotechnolog_eventbus::{EventBus, EventBusBackend, Event};
//
// // Create event bus with lock-free backend
// #[cfg(feature = "lock-free")]
// let bus = EventBus::new(EventBusBackend::LockFree, 1024);
//
// // Or use channel-based backend (default)
// #[cfg(not(feature = "lock-free"))]
// let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);
//
// // Create and publish event
// let event = Event::new("ORDER_FILLED", "EXECUTION", serde_json::json!({
//     "symbol": "BTC/USDT",
//     "price": 50000.0,
//     "quantity": 0.1
// }));
// bus.publish(event).unwrap();
//
// // Subscribe to events
// let receiver = bus.subscribe();
// while let Ok(event) = receiver.recv() {
//     println!("Received event: {:?}", event);
// }
// ```
//
// # Performance
//
// Based on benchmarks (ChannelBased vs LockFree):
//
// - **Single-threaded publish**: ~50-100 ns/event (both backends)
// - **Concurrent publish (4 threads)**: ~200-500 ns/event (LockFree 2-3x faster)
// - **Publish + receive**: ~500-1000 ns/event (LockFree 1.5-2x faster)
// - **Memory overhead**: LockFree ~2x lower (no channel buffers)
//
// # When to use LockFree backend
//
// - High-throughput scenarios (>10k events/sec)
// - Many concurrent publishers (>4 threads)
// - Low-latency requirements (<1ms end-to-end)
// - Bounded memory usage is critical
//
// # When to use ChannelBased backend
//
// - Simplicity and reliability are preferred
// - Low contention scenarios (<1k events/sec)
// - Backpressure handling is needed
// - Unbounded buffer is acceptable
//
// # Gradual Rollout
//
// The lock-free backend is disabled by default. To enable it:
//
// ```toml
// [dependencies.cryptotechnolog-eventbus]
// version = "0.1"
// features = ["lock-free"]
// ```
//
// Or run with:
// ```bash
// cargo run --features lock-free
// ```

pub mod event;
pub mod priority;
pub mod priority_queue;
pub mod backpressure;
pub mod persistence;
pub mod rate_limiter;

#[cfg(feature = "lock-free")]
pub mod ring_buffer;

pub mod bus;

// ==================== Re-exports ====================
pub use event::Event;
pub use priority::Priority;
pub use priority_queue::{PriorityQueue, PushResult, QueueCapacity};
pub use backpressure::{
    BackpressureHandler, BackpressureStrategy, HandleResult, DroppedStats, BackpressureMetrics,
};
pub use persistence::{
    PersistenceLayer, PersistenceConfig, PersistenceError, PersistenceMetrics, PersistResult,
    SyncPersistenceLayer,
};
pub use rate_limiter::{
    RateLimiter, RateLimiterConfig, RateLimitError, RateLimitResult, RateLimiterMetrics,
    SlidingWindow, SyncRateLimiter,
};

#[cfg(feature = "lock-free")]
pub use ring_buffer::LockFreeRingBuffer;

pub use bus::{EventBus, EventBusBackend};

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
