// ==================== CRYPTOTEHNOLOG Event Bus Benchmarks ====================
// Benchmark for Event and EventBus performance

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use cryptotechnolog_eventbus::{Event, EventBus, EventBusBackend};
use serde_json::json;
use std::sync::Arc;
use std::time::Duration;

// ==================== Event Benchmarks ====================

/// Benchmark event creation
fn bench_event_creation(c: &mut Criterion) {
    c.bench_function("event_creation", |b| {
        b.iter(|| {
            let _event = black_box(Event::new(
                "ORDER_FILLED",
                "EXECUTION",
                json!({
                    "symbol": "BTC/USDT",
                    "price": 50000.0,
                    "quantity": 0.1
                }),
            ));
        });
    });
}

/// Benchmark event serialization
fn bench_event_serialization(c: &mut Criterion) {
    let event = Event::new(
        "ORDER_FILLED",
        "EXECUTION",
        json!({
            "symbol": "BTC/USDT",
            "price": 50000.0,
            "quantity": 0.1,
            "timestamp": 1699999999
        }),
    );

    c.bench_function("event_serialization", |b| {
        b.iter(|| {
            let _serialized = black_box(serde_json::to_string(&event).unwrap());
        });
    });
}

/// Benchmark event deserialization
fn bench_event_deserialization(c: &mut Criterion) {
    let serialized = serde_json::to_string(&Event::new(
        "ORDER_FILLED",
        "EXECUTION",
        json!({
            "symbol": "BTC/USDT",
            "price": 50000.0,
            "quantity": 0.1
        }),
    ))
    .unwrap();

    c.bench_function("event_deserialization", |b| {
        b.iter(|| {
            let _event: Event = black_box(serde_json::from_str(&serialized).unwrap());
        });
    });
}

// ==================== EventBus Benchmarks ====================

/// Benchmark EventBus creation
fn bench_eventbus_creation(c: &mut Criterion) {
    c.bench_function("eventbus_creation", |b| {
        b.iter(|| {
            let _bus = black_box(EventBus::new(EventBusBackend::ChannelBased, 1024));
        });
    });
}

/// Benchmark event publish (single thread)
fn bench_eventbus_publish(c: &mut Criterion) {
    c.bench_function("eventbus_publish_single", |b| {
        let bus = Arc::new(EventBus::new(EventBusBackend::ChannelBased, 1024));
        let _receiver = bus.subscribe();

        b.iter(|| {
            let event = Event::new("TEST", "SOURCE", json!({"data": 42}));
            black_box(bus.publish(event)).ok();
        });
    });
}

/// Benchmark event publish + receive
fn bench_eventbus_publish_receive(c: &mut Criterion) {
    c.bench_function("eventbus_publish_receive", |b| {
        let bus = Arc::new(EventBus::new(EventBusBackend::ChannelBased, 1024));
        let receiver = bus.subscribe();

        b.iter(|| {
            let event = Event::new("TEST", "SOURCE", json!({"data": 42}));
            bus.publish(event).ok();
            black_box(receiver.recv_timeout(Duration::from_millis(10)).ok());
        });
    });
}

/// Benchmark multiple subscribers
fn bench_eventbus_multiple_subscribers(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_subscribers");

    for subscriber_count in [1, 2, 4, 8].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(subscriber_count),
            subscriber_count,
            |b, &count| {
                let bus = Arc::new(EventBus::new(EventBusBackend::ChannelBased, 1024));

                // Create subscribers
                let receivers: Vec<_> = (0..count).map(|_| bus.subscribe()).collect();

                b.iter(|| {
                    let event = Event::new("TEST", "SOURCE", json!({"index": 42}));
                    bus.publish(event).ok();

                    // All subscribers receive
                    for receiver in &receivers {
                        let _ = black_box(receiver.recv_timeout(Duration::from_millis(1)));
                    }
                });
            },
        );
    }
    group.finish();
}

/// Benchmark concurrent publish (multi-threaded)
fn bench_eventbus_concurrent_publish(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_concurrent_publish");

    for thread_count in [1, 2, 4, 8].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(thread_count),
            thread_count,
            |b, &count| {
                let bus = Arc::new(EventBus::new(EventBusBackend::ChannelBased, 1024));
                let _receiver = bus.subscribe();

                b.iter(|| {
                    let handles: Vec<_> = (0..count)
                        .map(|i| {
                            let bus_clone = bus.clone();
                            std::thread::spawn(move || {
                                let event = Event::new(
                                    "TEST",
                                    "SOURCE",
                                    json!({"thread": i, "data": 42}),
                                );
                                black_box(bus_clone.publish(event))
                            })
                        })
                        .collect();

                    for handle in handles {
                        handle.join().ok();
                    }
                });
            },
        );
    }
    group.finish();
}

/// Benchmark different payload sizes
fn bench_eventbus_payload_sizes(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_payload_sizes");

    for size in [10, 100, 1000, 10000].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(size), size, |b, &size| {
            let bus = Arc::new(EventBus::new(EventBusBackend::ChannelBased, 1024));
            let _receiver = bus.subscribe();

            // Create payload of specified size
            let data: serde_json::Value = json!({
                "fields": (0..size).map(|i| (format!("field_{}", i), i)).collect::<Vec<_>>()
            });

            b.iter(|| {
                let event = Event::new("TEST", "SOURCE", data.clone());
                black_box(bus.publish(event)).ok();
            });
        });
    }
    group.finish();
}

/// Benchmark buffer capacity impact
fn bench_eventbus_capacity(c: &mut Criterion) {
    let mut group = c.benchmark_group("eventbus_capacity");

    for capacity in [64, 256, 1024, 4096].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(capacity), capacity, |b, &cap| {
            let bus = Arc::new(EventBus::new(EventBusBackend::ChannelBased, cap));
            let _receiver = bus.subscribe();

            b.iter(|| {
                let event = Event::new("TEST", "SOURCE", json!({"data": 42}));
                black_box(bus.publish(event)).ok();
            });
        });
    }
    group.finish();
}

criterion_group!(
    benches,
    // Event benchmarks
    bench_event_creation,
    bench_event_serialization,
    bench_event_deserialization,
    // EventBus benchmarks
    bench_eventbus_creation,
    bench_eventbus_publish,
    bench_eventbus_publish_receive,
    bench_eventbus_multiple_subscribers,
    bench_eventbus_concurrent_publish,
    bench_eventbus_payload_sizes,
    bench_eventbus_capacity,
);
criterion_main!(benches);
