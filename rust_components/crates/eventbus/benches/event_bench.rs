// ==================== CRYPTOTEHNOLOG Event Bus Benchmarks ====================
// Criterion benchmarks for event bus performance

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};

// Placeholder imports - will be updated when eventbus is implemented
// use cryptotechnolog_eventbus::{Event, EventBus};

/// Benchmark event creation
fn bench_event_creation(c: &mut Criterion) {
    c.bench_function("event_creation", |b| {
        b.iter(|| {
            // Placeholder: Will use actual Event::new() in Phase 3
            let _event = black_box((
                "TEST_EVENT",
                "TEST_SOURCE",
                serde_json::json!({"data": "test"}),
            ));
        })
    });
}

/// Benchmark event serialization
fn bench_event_serialization(c: &mut Criterion) {
    c.bench_function("event_serialization", |b| {
        let event = black_box(serde_json::json!({
            "event_type": "TEST_EVENT",
            "source": "TEST_SOURCE",
            "timestamp": chrono::Utc::now(),
            "data": {"key": "value"}
        }));

        b.iter(|| {
            let _serialized = black_box(serde_json::to_string(&event).unwrap());
        })
    });
}

/// Benchmark event deserialization
fn bench_event_deserialization(c: &mut Criterion) {
    let serialized = serde_json::to_string(&serde_json::json!({
        "event_type": "TEST_EVENT",
        "source": "TEST_SOURCE",
        "timestamp": chrono::Utc::now(),
        "data": {"key": "value"}
    })).unwrap();

    c.bench_function("event_deserialization", |b| {
        b.iter(|| {
            let _deserialized: serde_json::Value =
                black_box(serde_json::from_str(&serialized).unwrap());
        })
    });
}

/// Benchmark multiple event sizes
fn bench_event_sizes(c: &mut Criterion) {
    let mut group = c.benchmark_group("event_sizes");

    for size in [10, 100, 1000, 10000].iter() {
        let data: Vec<i32> = (0..*size).collect();
        let event = serde_json::json!({
            "event_type": "TEST_EVENT",
            "source": "TEST_SOURCE",
            "timestamp": chrono::Utc::now(),
            "data": data
        });

        group.bench_with_input(BenchmarkId::from_parameter(size), size, |b, &_size| {
            b.iter(|| {
                let _serialized = black_box(serde_json::to_string(&event).unwrap());
            })
        });
    }

    group.finish();
}

criterion_group!(
    benches,
    bench_event_creation,
    bench_event_serialization,
    bench_event_deserialization,
    bench_event_sizes
);
criterion_main!(benches);
