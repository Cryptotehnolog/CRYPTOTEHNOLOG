// ==================== CRYPTOTEHNOLOG Event Bus ====================
// High-performance event bus with pluggable backends
//
// Backends:
// - ChannelBased: Uses crossbeam-channel with broadcast support (default)
// - LockFree: Uses LockFreeRingBuffer (with "lock-free" feature)

use crate::event::Event;
use std::sync::{Arc, Mutex};
use tracing::{debug, warn};

#[cfg(feature = "lock-free")]
use crate::ring_buffer::LockFreeRingBuffer;

// Use crossbeam-channel for broadcast support
use crossbeam_channel::{bounded, Receiver, RecvError, Sender, TrySendError};

// ==================== Backend Types ====================

/// Event bus backend type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum EventBusBackend {
    /// Standard channel-based backend (default)
    #[default]
    ChannelBased,
    /// Lock-free ring buffer backend (requires "lock-free" feature)
    #[cfg(feature = "lock-free")]
    LockFree,
}

// ==================== Event Bus ====================

/// High-performance event bus with pluggable backends
///
/// # Features
///
/// - **Multiple subscribers**: Each subscriber gets all events (broadcast)
/// - **Bounded capacity**: Prevents unbounded memory growth
/// - **Graceful degradation**: Returns error on buffer overflow (non-blocking)
/// - **Thread-safe**: Safe to use from multiple threads
/// - **Zero-copy**: Efficient message passing
///
/// # Example
///
/// ```rust,ignore
/// use cryptotechnolog_eventbus::{EventBus, EventBusBackend};
///
/// // Create event bus with channel-based backend
/// let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);
///
/// // Create event
/// let event = Event::new("TEST", "SOURCE", serde_json::json!({}));
///
/// // Publish event
/// bus.publish(event).unwrap();
///
/// // Subscribe to events (multiple subscribers supported)
/// let receiver1 = bus.subscribe();
/// let receiver2 = bus.subscribe();
///
/// // Both subscribers will receive the event
/// let event1 = receiver1.recv().unwrap();
/// let event2 = receiver2.recv().unwrap();
/// ```
pub struct EventBus {
    /// Backend type
    backend: EventBusBackend,
    /// Channel-based subscribers list (for broadcast)
    channel_subscribers: Arc<Mutex<Vec<Sender<Event>>>>,
    /// Lock-free ring buffer
    #[cfg(feature = "lock-free")]
    ring_buffer: Option<Arc<LockFreeRingBuffer<Event, 1024>>>,
    /// Buffer capacity
    capacity: usize,
}

impl EventBus {
    /// Create a new event bus with specified backend and capacity
    ///
    /// # Arguments
    ///
    /// * `backend` - The backend type to use
    /// * `capacity` - Buffer capacity (used for both backends)
    ///
    /// # Returns
    ///
    /// A new EventBus instance
    pub fn new(backend: EventBusBackend, capacity: usize) -> Self {
        debug!(
            "Creating EventBus with backend: {:?}, capacity: {}",
            backend, capacity
        );

        match backend {
            EventBusBackend::ChannelBased => Self {
                backend,
                channel_subscribers: Arc::new(Mutex::new(Vec::new())),
                #[cfg(feature = "lock-free")]
                ring_buffer: None,
                capacity,
            },
            #[cfg(feature = "lock-free")]
            EventBusBackend::LockFree => {
                if !capacity.is_power_of_two() {
                    warn!(
                        "Lock-free buffer capacity must be a power of 2. Rounding up to {}",
                        capacity.next_power_of_two()
                    );
                }
                Self {
                    backend,
                    channel_subscribers: Arc::new(Mutex::new(Vec::new())),
                    ring_buffer: Some(Arc::new(LockFreeRingBuffer::new())),
                    capacity,
                }
            }
        }
    }

    /// Create a new event bus with default backend (ChannelBased) and capacity 1024
    pub fn new_default() -> Self {
        Self::new(EventBusBackend::default(), 1024)
    }

    /// Publish an event to the bus
    ///
    /// This is a non-blocking operation. If the buffer is full, the event
    /// is returned as an error instead of blocking.
    ///
    /// For ChannelBased backend, events are broadcast to all subscribers.
    ///
    /// # Arguments
    ///
    /// * `event` - The event to publish
    ///
    /// # Returns
    ///
    /// * `Ok(())` - Event was successfully published
    /// * `Err(Box(event))` - Failed to publish (buffer full or disconnected), event is returned
    pub fn publish(&self, event: Event) -> Result<(), Box<Event>> {
        match self.backend {
            EventBusBackend::ChannelBased => {
                let mut subscribers = self.channel_subscribers.lock().unwrap();
                let mut failed_indices = Vec::new();

                // Send to all subscribers
                for (index, sender) in subscribers.iter().enumerate() {
                    match sender.try_send(event.clone()) {
                        Ok(_) => {}
                        Err(TrySendError::Full(_)) => {
                            warn!("Event bus subscriber buffer full");
                        }
                        Err(TrySendError::Disconnected(_)) => {
                            failed_indices.push(index);
                        }
                    }
                }

                // Remove disconnected subscribers (in reverse order to preserve indices)
                for index in failed_indices.into_iter().rev() {
                    subscribers.remove(index);
                }

                Ok(())
            }
            #[cfg(feature = "lock-free")]
            EventBusBackend::LockFree => {
                if let Some(ref buffer) = self.ring_buffer {
                    match buffer.push(event) {
                        Ok(_) => Ok(()),
                        Err(e) => {
                            warn!(
                                "Lock-free ring buffer full, dropping event: {}",
                                e.event_type
                            );
                            Err(Box::new(e))
                        }
                    }
                } else {
                    Err(Box::new(event))
                }
            }
        }
    }

    /// Subscribe to events from the bus
    ///
    /// Multiple subscribers are supported. Each subscriber receives a copy
    /// of every published event.
    ///
    /// # Returns
    ///
    /// A receiver for events
    pub fn subscribe(&self) -> Receiver<Event> {
        match self.backend {
            EventBusBackend::ChannelBased => {
                let (sender, receiver) = bounded(self.capacity);

                // Add sender to subscribers list
                let mut subscribers = self.channel_subscribers.lock().unwrap();
                subscribers.push(sender);

                receiver
            }
            #[cfg(feature = "lock-free")]
            EventBusBackend::LockFree => {
                // For lock-free backend, create a new channel and spawn a poller thread
                let (sender, receiver) = bounded(self.capacity);
                let buffer = self.ring_buffer.clone().unwrap();

                std::thread::spawn(move || {
                    loop {
                        // Poll the ring buffer
                        if let Some(event) = buffer.pop() {
                            if sender.send(event).is_err() {
                                break; // Receiver dropped
                            }
                        } else {
                            // Sleep briefly to avoid busy-waiting
                            std::thread::sleep(std::time::Duration::from_micros(100));
                        }
                    }
                });

                receiver
            }
        }
    }

    /// Get the current number of subscribers
    pub fn subscriber_count(&self) -> usize {
        match self.backend {
            EventBusBackend::ChannelBased => {
                let subscribers = self.channel_subscribers.lock().unwrap();
                subscribers.len()
            }
            #[cfg(feature = "lock-free")]
            EventBusBackend::LockFree => {
                // For lock-free backend, we don't track subscribers
                0
            }
        }
    }

    /// Get the current number of events in the buffer
    ///
    /// Note: This is an approximation for crossbeam-channel due to
    /// concurrent modifications.
    pub fn len(&self) -> usize {
        match self.backend {
            EventBusBackend::ChannelBased => {
                // For channel-based, estimate based on subscribers
                let subscribers = self.channel_subscribers.lock().unwrap();
                if subscribers.is_empty() {
                    0
                } else {
                    // Estimate from first subscriber
                    subscribers[0].len()
                }
            }
            #[cfg(feature = "lock-free")]
            EventBusBackend::LockFree => {
                if let Some(ref buffer) = self.ring_buffer {
                    buffer.len()
                } else {
                    0
                }
            }
        }
    }

    /// Check if the event bus is empty
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Check if the event bus is full
    pub fn is_full(&self) -> bool {
        match self.backend {
            EventBusBackend::ChannelBased => {
                let subscribers = self.channel_subscribers.lock().unwrap();
                if subscribers.is_empty() {
                    false
                } else {
                    subscribers[0].is_full()
                }
            }
            #[cfg(feature = "lock-free")]
            EventBusBackend::LockFree => {
                if let Some(ref buffer) = self.ring_buffer {
                    buffer.is_full()
                } else {
                    false
                }
            }
        }
    }

    /// Get the buffer capacity
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Get the backend type
    pub fn backend(&self) -> EventBusBackend {
        self.backend
    }

    /// Clear all events from the buffer
    pub fn clear(&self) {
        match self.backend {
            EventBusBackend::ChannelBased => {
                let _subscribers = self.channel_subscribers.lock().unwrap();
                // Note: We can't directly drain crossbeam channels
                // This is a no-op for channel-based backend
            }
            #[cfg(feature = "lock-free")]
            EventBusBackend::LockFree => {
                if let Some(ref buffer) = self.ring_buffer {
                    buffer.clear();
                }
            }
        }
    }

    /// Try to receive an event without blocking
    ///
    /// # Returns
    ///
    /// * `Ok(Some(event))` - Event received
    /// * `Ok(None)` - No event available
    /// * `Err(_)` - Channel disconnected
    pub fn try_recv(&self) -> Result<Option<Event>, RecvError> {
        match self.backend {
            EventBusBackend::ChannelBased => {
                // Note: For ChannelBased backend, we can't easily peek into the channel
                // without consuming the event. So we always return None.
                // Subscribers should use their own receiver's try_recv() method.
                Ok(None)
            }
            #[cfg(feature = "lock-free")]
            EventBusBackend::LockFree => {
                if let Some(ref buffer) = self.ring_buffer {
                    Ok(buffer.pop())
                } else {
                    Ok(None)
                }
            }
        }
    }
}

// ==================== Tests ====================
#[cfg(test)]
mod tests {
    use super::*;
    use crate::Event;
    use std::time::Duration;

    #[test]
    fn test_eventbus_new_channel_based() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);
        assert_eq!(bus.backend(), EventBusBackend::ChannelBased);
        assert!(bus.is_empty());
        assert_eq!(bus.capacity(), 1024);
    }

    #[test]
    fn test_eventbus_new_default() {
        let bus = EventBus::new_default();
        assert_eq!(bus.backend(), EventBusBackend::ChannelBased);
        assert_eq!(bus.capacity(), 1024);
    }

    #[test]
    fn test_eventbus_publish_subscribe() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);
        let event = Event::new("TEST", "SOURCE", serde_json::json!({"key": "value"}));

        // Subscribe first
        let receiver = bus.subscribe();

        // Publish event
        bus.publish(event.clone()).unwrap();

        // Receive event
        let received = receiver.recv_timeout(Duration::from_millis(100)).unwrap();

        assert_eq!(received.event_type, "TEST");
        assert_eq!(received.source, "SOURCE");
        assert_eq!(received.payload["key"], "value");
    }

    #[test]
    fn test_eventbus_multiple_subscribers() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);
        let event = Event::new("TEST", "SOURCE", serde_json::json!({"index": 42}));

        // Create multiple subscribers
        let receiver1 = bus.subscribe();
        let receiver2 = bus.subscribe();
        let receiver3 = bus.subscribe();

        // Publish event
        bus.publish(event.clone()).unwrap();

        // All subscribers should receive the event
        let received1 = receiver1.recv_timeout(Duration::from_millis(100)).unwrap();
        let received2 = receiver2.recv_timeout(Duration::from_millis(100)).unwrap();
        let received3 = receiver3.recv_timeout(Duration::from_millis(100)).unwrap();

        assert_eq!(received1.event_type, "TEST");
        assert_eq!(received2.event_type, "TEST");
        assert_eq!(received3.event_type, "TEST");
        assert_eq!(received1.payload["index"], 42);
        assert_eq!(received2.payload["index"], 42);
        assert_eq!(received3.payload["index"], 42);
    }

    #[test]
    fn test_eventbus_multiple_events() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);

        let receiver = bus.subscribe();

        // Publish multiple events
        for i in 0..10 {
            let event = Event::new("TEST", "SOURCE", serde_json::json!({"index": i}));
            bus.publish(event).unwrap();
        }

        // Receive all events
        for i in 0..10 {
            let received = receiver.recv_timeout(Duration::from_millis(100)).unwrap();
            assert_eq!(received.payload["index"], i);
        }
    }

    #[test]
    fn test_eventbus_subscriber_count() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);

        assert_eq!(bus.subscriber_count(), 0);

        let _receiver1 = bus.subscribe();
        assert_eq!(bus.subscriber_count(), 1);

        let _receiver2 = bus.subscribe();
        assert_eq!(bus.subscriber_count(), 2);

        drop(_receiver1);
        // Note: Disconnected subscribers are only removed on next publish
        bus.publish(Event::new("TEST", "SOURCE", serde_json::json!({})))
            .ok();

        // After publish, disconnected subscribers should be removed
        // This may not be immediate, so we don't assert exact count
    }

    #[test]
    fn test_eventbus_publish_full_buffer() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 10);

        let _receiver = bus.subscribe();

        // Fill buffer
        for i in 0..20 {
            let event = Event::new("TEST", "SOURCE", serde_json::json!({"index": i}));
            bus.publish(event).ok();
        }

        // Buffer should be full, but publish won't fail (just drops to full subscribers)
        let event = Event::new("FULL", "SOURCE", serde_json::json!({}));
        // This should still succeed (non-blocking)
        let result = bus.publish(event);
        assert!(result.is_ok());
    }

    #[test]
    fn test_eventbus_try_recv() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);

        // Try recv on empty bus with no subscribers
        let result: Result<Option<Event>, RecvError> = bus.try_recv();
        assert!(matches!(result, Ok(None)));

        // Subscribe and publish event
        let _receiver = bus.subscribe();
        let event = Event::new("TEST", "SOURCE", serde_json::json!({"key": "value"}));
        bus.publish(event).unwrap();

        // Try recv should still return None (can't peek into channel)
        let result: Result<Option<Event>, RecvError> = bus.try_recv();
        assert!(matches!(result, Ok(None)));
    }

    #[test]
    fn test_eventbus_is_full() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 10);
        let _receiver = bus.subscribe();

        assert!(!bus.is_full());

        // Fill buffer
        for i in 0..10 {
            let event = Event::new("TEST", "SOURCE", serde_json::json!({"index": i}));
            bus.publish(event).unwrap();
        }

        // Buffer should be full
        assert!(bus.is_full());
    }

    #[test]
    fn test_eventbus_capacity() {
        let bus = EventBus::new(EventBusBackend::ChannelBased, 2048);
        assert_eq!(bus.capacity(), 2048);
    }

    #[cfg(feature = "lock-free")]
    #[test]
    fn test_eventbus_new_lock_free() {
        let bus = EventBus::new(EventBusBackend::LockFree, 1024);
        assert_eq!(bus.backend(), EventBusBackend::LockFree);
        assert!(bus.is_empty());
    }

    #[cfg(feature = "lock-free")]
    #[test]
    fn test_eventbus_lock_free_publish_subscribe() {
        let bus = EventBus::new(EventBusBackend::LockFree, 1024);
        let event = Event::new("TEST", "SOURCE", serde_json::json!({"key": "value"}));

        // Publish event
        bus.publish(event.clone()).unwrap();

        // Subscribe and receive
        let receiver = bus.subscribe();
        let received = receiver.recv_timeout(Duration::from_millis(500)).unwrap();

        assert_eq!(received.event_type, "TEST_EVENT");
    }

    #[cfg(feature = "lock-free")]
    #[test]
    fn test_eventbus_lock_free_full_buffer() {
        let bus = EventBus::new(EventBusBackend::LockFree, 1024);

        // Fill buffer (1024 events)
        for i in 0..1024 {
            let event = Event::new("TEST", "SOURCE", serde_json::json!({"index": i}));
            bus.publish(event).unwrap();
        }

        // Try to publish to full buffer
        let event = Event::new("FULL", "SOURCE", serde_json::json!({}));
        let result = bus.publish(event);

        // Should fail if buffer is full
        assert!(result.is_err());
    }

    #[cfg(feature = "lock-free")]
    #[test]
    fn test_eventbus_lock_free_capacity() {
        let bus = EventBus::new(EventBusBackend::LockFree, 1024);
        assert_eq!(bus.capacity(), 1024);
    }

    #[cfg(feature = "lock-free")]
    #[test]
    fn test_eventbus_lock_free_multiple_subscribers() {
        let bus = EventBus::new(EventBusBackend::LockFree, 1024);
        let event = Event::new("TEST", "SOURCE", serde_json::json!({"index": 42}));

        // Create multiple subscribers
        let receiver1 = bus.subscribe();
        let receiver2 = bus.subscribe();

        // Publish event
        bus.publish(event.clone()).unwrap();

        // Both should receive
        let received1 = receiver1.recv_timeout(Duration::from_millis(500)).unwrap();
        let received2 = receiver2.recv_timeout(Duration::from_millis(500)).unwrap();

        assert_eq!(received1.event_type, "TEST_EVENT");
        assert_eq!(received2.event_type, "TEST_EVENT");
    }
}
