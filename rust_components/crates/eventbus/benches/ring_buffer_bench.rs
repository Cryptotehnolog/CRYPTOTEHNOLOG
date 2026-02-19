// ==================== CRYPTOTEHNOLOG Ring Buffer Benchmarks ====================
// Criterion benchmarks for lock-free ring buffer vs standard implementations

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};

#[cfg(feature = "lock-free")]
use cryptotechnolog_eventbus::LockFreeRingBuffer;

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

/// Benchmark lock-free ring buffer push
#[cfg(feature = "lock-free")]
fn bench_ring_buffer_push(c: &mut Criterion) {
    let mut group = c.benchmark_group("ring_buffer_push");

    for capacity in [16, 256, 1024, 4096].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(capacity), capacity, |b, &_cap| {
            let buffer: LockFreeRingBuffer<i32, 4096> = LockFreeRingBuffer::new();

            b.iter(|| {
                black_box(buffer.push(black_box(42))).ok();
            })
        });
    }

    group.finish();
}

/// Benchmark lock-free ring buffer pop
#[cfg(feature = "lock-free")]
fn bench_ring_buffer_pop(c: &mut Criterion) {
    let mut group = c.benchmark_group("ring_buffer_pop");

    for capacity in [16, 256, 1024, 4096].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(capacity), capacity, |b, &cap| {
            let buffer: LockFreeRingBuffer<i32, 4096> = LockFreeRingBuffer::new();

            // Pre-fill buffer
            for i in 0..cap {
                buffer.push(i).unwrap();
            }

            b.iter(|| {
                black_box(buffer.pop());
            })
        });
    }

    group.finish();
}

/// Benchmark standard VecDeque push (for comparison)
fn bench_vecdeque_push(c: &mut Criterion) {
    let mut group = c.benchmark_group("vecdeque_push");

    for capacity in [16, 256, 1024, 4096].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(capacity), capacity, |b, &cap| {
            let mut deque = VecDeque::with_capacity(cap);

            b.iter(|| {
                black_box(deque.push_back(black_box(42)));
            })
        });
    }

    group.finish();
}

/// Benchmark standard VecDeque pop (for comparison)
fn bench_vecdeque_pop(c: &mut Criterion) {
    let mut group = c.benchmark_group("vecdeque_pop");

    for capacity in [16, 256, 1024, 4096].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(capacity), capacity, |b, &cap| {
            let mut deque: VecDeque<i32> = (0..cap).collect();

            b.iter(|| {
                black_box(deque.pop_front());
            })
        });
    }

    group.finish();
}

/// Benchmark Mutex<VecDeque> push (for comparison)
fn bench_mutex_vecdeque_push(c: &mut Criterion) {
    let mut group = c.benchmark_group("mutex_vecdeque_push");

    for capacity in [16, 256, 1024, 4096].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(capacity), capacity, |b, &cap| {
            let deque = Mutex::new(VecDeque::with_capacity(cap));

            b.iter(|| {
                let mut d = deque.lock().unwrap();
                black_box(d.push_back(black_box(42)));
            })
        });
    }

    group.finish();
}

/// Benchmark Mutex<VecDeque> pop (for comparison)
fn bench_mutex_vecdeque_pop(c: &mut Criterion) {
    let mut group = c.benchmark_group("mutex_vecdeque_pop");

    for capacity in [16, 256, 1024, 4096].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(capacity), capacity, |b, &cap| {
            let deque = Mutex::new((0..cap).collect::<VecDeque<i32>>());

            b.iter(|| {
                let mut d = deque.lock().unwrap();
                black_box(d.pop_front());
            })
        });
    }

    group.finish();
}

/// Benchmark concurrent push-pop with lock-free ring buffer
#[cfg(feature = "lock-free")]
fn bench_ring_buffer_concurrent(c: &mut Criterion) {
    use std::thread;

    c.bench_function("ring_buffer_concurrent_2_threads", |b| {
        b.iter(|| {
            let buffer = Arc::new(LockFreeRingBuffer::<i32, 4096>::new());
            let buffer_clone = buffer.clone();

            // Producer thread
            let producer = thread::spawn(move || {
                for i in 0..1000 {
                    buffer.push(i).ok();
                }
            });

            // Consumer thread
            let consumer = thread::spawn(move || {
                let mut count = 0;
                while count < 1000 {
                    if buffer_clone.pop().is_some() {
                        count += 1;
                    }
                }
            });

            producer.join().unwrap();
            consumer.join().unwrap();
        })
    });
}

criterion_group!(
    benches,
    bench_ring_buffer_push,
    bench_ring_buffer_pop,
    bench_vecdeque_push,
    bench_vecdeque_pop,
    bench_mutex_vecdeque_push,
    bench_mutex_vecdeque_pop,
    bench_ring_buffer_concurrent
);
criterion_main!(benches);
