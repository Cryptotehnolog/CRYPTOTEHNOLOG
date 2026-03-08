// ==================== CRYPTOTEHNOLOG Enhanced Event Bus Benchmarks ====================
// Benchmark for EnhancedEventBus performance (priority queues, rate limiting, backpressure)

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use cryptotechnolog_eventbus::{
    EnhancedEventBus, Event, Priority, BackpressureStrategy,
};
use serde_json::json;
use std::sync::Arc;
use std::time::Duration;

// ==================== EnhancedEventBus Creation Benchmarks ====================

/// Benchmark EnhancedEventBus creation
fn bench_enhanced_eventbus_creation(c: &mut Criterion) {
    c.bench_function("enhanced_eventbus_creation", |b| {
        b.iter(|| {
            let _bus = black_box(EnhancedEventBus::new());
        });
    });
}

// ==================== Event Creation Benchmarks ====================

/// Benchmark event creation
fn bench_event_creation(c: &mut Criterion) {
    c.bench_function("enhanced_event_creation", |b| {
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

/// Benchmark event creation with priority
fn bench_event_creation_with_priority(c: &mut Criterion) {
    c.bench_function("enhanced_event_creation_with_priority", |b| {
        b.iter(|| {
            let mut event = Event::new("TEST", "SOURCE", json!({"data": 42}));
            event.priority = Priority::High;
            black_box(event);
        });
    });
}

// ==================== Priority Queue Benchmarks ====================

/// Benchmark priority queue push
fn bench_priority_queue_push(c: &mut Criterion) {
    c.bench_function("priority_queue_push", |b| {
        let bus = EnhancedEventBus::new();

        b.iter(|| {
            let event = Event::new("TEST", "SOURCE", json!({"i": 1}));
            let _ = bus.publish(event);
        });
    });
}

/// Benchmark priority queue push with different priorities
fn bench_priority_queue_priority(c: &mut Criterion) {
    let priorities = [Priority::Critical, Priority::High, Priority::Normal, Priority::Low];
    
    c.bench_function("priority_queue_priority", |b| {
        let bus = EnhancedEventBus::new();
        
        b.iter(|| {
            for (i, &priority) in priorities.iter().enumerate() {
                let event = Event::new("TEST", "SOURCE", json!({"i": i}))
                    .with_priority(priority);
                let _ = bus.publish(event);
            }
        });
    });
}

// ==================== Publish/Subscribe Benchmarks ====================

/// Benchmark event publish (no subscribers)
fn bench_enhanced_publish_no_subscribers(c: &mut Criterion) {
    c.bench_function("enhanced_publish_no_subscribers", |b| {
        let bus = Arc::new(EnhancedEventBus::new());

        b.iter(|| {
            let event = Event::new("TEST", "SOURCE", json!({"data": 42}));
            black_box(bus.publish(event));
        });
    });
}

/// Benchmark event publish with subscriber
fn bench_enhanced_publish_with_subscriber(c: &mut Criterion) {
    c.bench_function("enhanced_publish_with_subscriber", |b| {
        let bus = Arc::new(EnhancedEventBus::new());
        let _receiver = bus.subscribe();

        b.iter(|| {
            let event = Event::new("TEST", "SOURCE", json!({"data": 42}));
            black_box(bus.publish(event));
        });
    });
}

/// Benchmark event publish with multiple subscribers
fn bench_enhanced_publish_multiple_subscribers(c: &mut Criterion) {
    let mut group = c.benchmark_group("enhanced_subscribers");

    for subscriber_count in [1, 2, 4, 8].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(subscriber_count),
            subscriber_count,
            |b, &count| {
                let bus = Arc::new(EnhancedEventBus::new());

                // Create subscribers
                let _receivers: Vec<_> = (0..count).map(|_| bus.subscribe()).collect();

                b.iter(|| {
                    let event = Event::new("TEST", "SOURCE", json!({"index": 42}));
                    black_box(bus.publish(event));
                });
            },
        );
    }
    group.finish();
}

/// Benchmark publish + receive
fn bench_enhanced_publish_receive(c: &mut Criterion) {
    c.bench_function("enhanced_publish_receive", |b| {
        let bus = Arc::new(EnhancedEventBus::new());
        let receiver = bus.subscribe();

        b.iter(|| {
            let event = Event::new("TEST", "SOURCE", json!({"data": 42}));
            let _ = bus.publish(event);
            black_box(receiver.recv_timeout(Duration::from_millis(10)).ok());
        });
    });
}

// ==================== Rate Limiter Benchmarks ====================

/// Benchmark rate limiter check
fn bench_rate_limiter_check(c: &mut Criterion) {
    c.bench_function("rate_limiter_check", |b| {
        let limiter = cryptotechnolog_eventbus::RateLimiter::new(100000);

        b.iter(|| {
            black_box(limiter.check("SOURCE"));
        });
    });
}

/// Benchmark rate limiter with multiple sources
fn bench_rate_limiter_multiple_sources(c: &mut Criterion) {
    c.bench_function("rate_limiter_multiple_sources", |b| {
        let limiter = cryptotechnolog_eventbus::RateLimiter::new(100000);
        
        // Add source-specific limits
        for i in 0..10 {
            limiter.set_source_limit(&format!("SOURCE_{}", i), 1000);
        }

        b.iter(|| {
            for i in 0..10 {
                black_box(limiter.check(&format!("SOURCE_{}", i)));
            }
        });
    });
}

// ==================== Backpressure Benchmarks ====================

/// Benchmark backpressure with DropLow strategy
fn bench_backpressure_drop_low(c: &mut Criterion) {
    c.bench_function("backpressure_drop_low", |b| {
        let bus = Arc::new(EnhancedEventBus::new());
        bus.set_backpressure_strategy(BackpressureStrategy::DropLow);
        let _receiver = bus.subscribe();

        b.iter(|| {
            let event = Event::new("TEST", "SOURCE", json!({"data": 42}));
            // Some will be dropped due to backpressure
            let _ = black_box(bus.publish(event));
        });
    });
}

/// Benchmark backpressure with DropNormal strategy
fn bench_backpressure_drop_normal(c: &mut Criterion) {
    c.bench_function("backpressure_drop_normal", |b| {
        let bus = Arc::new(EnhancedEventBus::new());
        bus.set_backpressure_strategy(BackpressureStrategy::DropNormal);
        let _receiver = bus.subscribe();

        b.iter(|| {
            let event = Event::new("TEST", "SOURCE", json!({"data": 42}));
            let _ = black_box(bus.publish(event));
        });
    });
}

// ==================== Concurrent Benchmarks ====================

/// Benchmark concurrent publish (multi-threaded)
fn bench_enhanced_concurrent_publish(c: &mut Criterion) {
    let mut group = c.benchmark_group("enhanced_concurrent_publish");

    for thread_count in [1, 2, 4, 8].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(thread_count),
            thread_count,
            |b, &count| {
                let bus = Arc::new(EnhancedEventBus::new());
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

// ==================== Metrics Benchmarks ====================

/// Benchmark metrics collection
fn bench_metrics_collection(c: &mut Criterion) {
    c.bench_function("enhanced_metrics_collection", |b| {
        let bus = EnhancedEventBus::new();
        
        // Add some events
        for i in 0..100 {
            let event = Event::new("TEST", "SOURCE", json!({"i": i}));
            let _ = bus.publish(event);
        }

        b.iter(|| {
            let _metrics = black_box(bus.get_metrics());
        });
    });
}

criterion_group!(
    benches,
    // Creation
    bench_enhanced_eventbus_creation,
    bench_event_creation,
    bench_event_creation_with_priority,
    // Priority Queue
    bench_priority_queue_push,
    bench_priority_queue_priority,
    // Publish/Subscribe
    bench_enhanced_publish_no_subscribers,
    bench_enhanced_publish_with_subscriber,
    bench_enhanced_publish_multiple_subscribers,
    bench_enhanced_publish_receive,
    // Rate Limiter
    bench_rate_limiter_check,
    bench_rate_limiter_multiple_sources,
    // Backpressure
    bench_backpressure_drop_low,
    bench_backpressure_drop_normal,
    // Concurrent
    bench_enhanced_concurrent_publish,
    // Metrics
    bench_metrics_collection,
);
criterion_main!(benches);
