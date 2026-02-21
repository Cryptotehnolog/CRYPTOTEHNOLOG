// ==================== CRYPTOTEHNOLOG EventBus Backend Benchmarks ====================
// Benchmark comparison between ChannelBased and LockFree backends

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use cryptotechnolog_eventbus::{Event, EventBus, EventBusBackend};
use std::sync::Arc;
use std::time::Duration;

/// Benchmark event publishing with ChannelBased backend
fn bench_eventbus_channel_publish(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_channel_publish");

    for event_count in [10, 100, 1000, 10000].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(event_count),
            event_count,
            |b, &count| {
                let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);

                b.iter(|| {
                    for i in 0..count {
                        let event = Event::new(
                            "TEST_EVENT",
                            "TEST_SOURCE",
                            serde_json::json!({"index": i}),
                        );
                        black_box(bus.publish(event));
                    }
                });
            },
        );
    }

    group.finish();
}

/// Benchmark event publishing with LockFree backend
#[cfg(feature = "lock-free")]
fn bench_eventbus_lockfree_publish(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_lockfree_publish");

    for event_count in [10, 100, 1000, 10000].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(event_count),
            event_count,
            |b, &count| {
                let bus = EventBus::new(EventBusBackend::LockFree, 1024);

                b.iter(|| {
                    for i in 0..count {
                        let event = Event::new(
                            "TEST_EVENT",
                            "TEST_SOURCE",
                            serde_json::json!({"index": i}),
                        );
                        black_box(bus.publish(event));
                    }
                });
            },
        );
    }

    group.finish();
}

/// Benchmark event publishing and receiving with ChannelBased backend
fn bench_eventbus_channel_publish_receive(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_channel_publish_receive");

    for event_count in [10, 100, 1000].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(event_count),
            event_count,
            |b, &count| {
                let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);
                let receiver = bus.subscribe();

                b.iter(|| {
                    // Publish events
                    for i in 0..count {
                        let event = Event::new(
                            "TEST_EVENT",
                            "TEST_SOURCE",
                            serde_json::json!({"index": i}),
                        );
                        bus.publish(event).ok();
                    }

                    // Receive events
                    for _ in 0..count {
                        black_box(receiver.recv_timeout(Duration::from_millis(100)).ok());
                    }
                });
            },
        );
    }

    group.finish();
}

/// Benchmark event publishing and receiving with LockFree backend
#[cfg(feature = "lock-free")]
fn bench_eventbus_lockfree_publish_receive(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_lockfree_publish_receive");

    for event_count in [10, 100, 1000].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(event_count),
            event_count,
            |b, &count| {
                let bus = EventBus::new(EventBusBackend::LockFree, 1024);
                let receiver = bus.subscribe();

                b.iter(|| {
                    // Publish events
                    for i in 0..count {
                        let event = Event::new(
                            "TEST_EVENT",
                            "TEST_SOURCE",
                            serde_json::json!({"index": i}),
                        );
                        bus.publish(event).ok();
                    }

                    // Receive events
                    for _ in 0..count {
                        black_box(receiver.recv_timeout(Duration::from_millis(500)).ok());
                    }
                });
            },
        );
    }

    group.finish();
}

/// Benchmark concurrent publishers with ChannelBased backend
fn bench_eventbus_channel_concurrent_publishers(c: &mut Criterion) {
    use std::thread;

    c.bench_function("eventbus_channel_concurrent_publishers_4_threads", |b| {
        b.iter(|| {
            let bus = Arc::new(EventBus::new(EventBusBackend::ChannelBased, 1024));
            let mut handles = vec![];

            for thread_id in 0..4 {
                let bus_clone = bus.clone();
                let handle = thread::spawn(move || {
                    for i in 0..1000 {
                        let event = Event::new(
                            "TEST_EVENT",
                            format!("THREAD_{}", thread_id),
                            serde_json::json!({"index": i}),
                        );
                        bus_clone.publish(event).ok();
                    }
                });
                handles.push(handle);
            }

            for handle in handles {
                handle.join().unwrap();
            }
        })
    });
}

/// Benchmark concurrent publishers with LockFree backend
#[cfg(feature = "lock-free")]
fn bench_eventbus_lockfree_concurrent_publishers(c: &mut Criterion) {
    use std::thread;

    c.bench_function("eventbus_lockfree_concurrent_publishers_4_threads", |b| {
        b.iter(|| {
            let bus = Arc::new(EventBus::new(EventBusBackend::LockFree, 1024));
            let mut handles = vec![];

            for thread_id in 0..4 {
                let bus_clone = bus.clone();
                let handle = thread::spawn(move || {
                    for i in 0..1000 {
                        let event = Event::new(
                            "TEST_EVENT",
                            format!("THREAD_{}", thread_id),
                            serde_json::json!({"index": i}),
                        );
                        bus_clone.publish(event).ok();
                    }
                });
                handles.push(handle);
            }

            for handle in handles {
                handle.join().unwrap();
            }
        })
    });
}

/// Benchmark multiple subscribers with ChannelBased backend
fn bench_eventbus_channel_multiple_subscribers(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_channel_multiple_subscribers");

    for subscriber_count in [1, 2, 4, 8].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(subscriber_count),
            subscriber_count,
            |b, &count| {
                let bus = EventBus::new(EventBusBackend::ChannelBased, 1024);

                // Create subscribers
                let mut receivers = vec![];
                for _ in 0..count {
                    receivers.push(bus.subscribe());
                }

                b.iter(|| {
                    // Publish event
                    let event = Event::new(
                        "TEST_EVENT",
                        "TEST_SOURCE",
                        serde_json::json!({"value": 42}),
                    );
                    bus.publish(event).ok();

                    // Receive events (non-blocking)
                    for receiver in &receivers {
                        black_box(receiver.try_recv().ok());
                    }
                });
            },
        );
    }

    group.finish();
}

/// Benchmark multiple subscribers with LockFree backend
#[cfg(feature = "lock-free")]
fn bench_eventbus_lockfree_multiple_subscribers(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_lockfree_multiple_subscribers");

    for subscriber_count in [1, 2, 4, 8].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(subscriber_count),
            subscriber_count,
            |b, &count| {
                let bus = EventBus::new(EventBusBackend::LockFree, 1024);

                // Create subscribers
                let mut receivers = vec![];
                for _ in 0..count {
                    receivers.push(bus.subscribe());
                }

                b.iter(|| {
                    // Publish event
                    let event = Event::new(
                        "TEST_EVENT",
                        "TEST_SOURCE",
                        serde_json::json!({"value": 42}),
                    );
                    bus.publish(event).ok();

                    // Receive events (non-blocking)
                    for receiver in &receivers {
                        black_box(receiver.try_recv().ok());
                    }
                });
            },
        );
    }

    group.finish();
}

/// Benchmark event creation overhead
fn bench_event_creation(c: &mut Criterion) {
    c.bench_function("event_creation", |b| {
        b.iter(|| {
            black_box(Event::new(
                "TEST_EVENT",
                "TEST_SOURCE",
                serde_json::json!({"key": "value"}),
            ))
        });
    });
}

/// Benchmark event serialization
fn bench_event_serialization(c: &mut Criterion) {
    let event = Event::new("TEST_EVENT", "TEST_SOURCE", serde_json::json!({"key": "value"}));

    c.bench_function("event_serialization", |b| {
        b.iter(|| {
            black_box(serde_json::to_string(black_box(&event)))
        });
    });
}

/// Benchmark event deserialization
fn bench_event_deserialization(c: &mut Criterion) {
    let json = serde_json::to_string(&Event::new(
        "TEST_EVENT",
        "TEST_SOURCE",
        serde_json::json!({"key": "value"}),
    )).unwrap();

    c.bench_function("event_deserialization", |b| {
        b.iter(|| {
            black_box(serde_json::from_str::<Event>(black_box(&json)))
        });
    });
}

criterion_group!(
    benches,
    bench_eventbus_channel_publish,
    bench_eventbus_lockfree_publish,
    bench_eventbus_channel_publish_receive,
    bench_eventbus_lockfree_publish_receive,
    bench_eventbus_channel_concurrent_publishers,
    bench_eventbus_lockfree_concurrent_publishers,
    bench_eventbus_channel_multiple_subscribers,
    bench_eventbus_lockfree_multiple_subscribers,
    bench_event_creation,
    bench_event_serialization,
    bench_event_deserialization
);
criterion_main!(benches);
