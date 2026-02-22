// ==================== CRYPTOTEHNOLOG WAL Benchmarks ====================
// Benchmarks for WriteAheadLog performance

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use cryptotechnolog_risk_ledger::wal::WriteAheadLog;
use serde_json::json;
use std::path::PathBuf;
use tokio::runtime::Runtime;

/// Benchmark WAL append operation
fn bench_wal_append(c: &mut Criterion) {
    c.bench_function("wal_append_single", |b| {
        let rt = Runtime::new().unwrap();

        rt.block_on(async {
            let wal = std::sync::Arc::new(tokio::sync::Mutex::new(
                WriteAheadLog::new("test_wal_append.log".into())
                    .await
                    .unwrap(),
            ));

            b.iter(|| {
                let data = json!({
                    "id": "TEST-001",
                    "symbol": "BTC/USDT",
                    "size": 100.0,
                    "price": 50000.0
                });

                rt.block_on(async {
                    let mut wal_lock = wal.lock().await;
                    black_box(
                        wal_lock
                            .append("TEST_OPERATION".to_string(), data)
                            .await
                            .unwrap(),
                    )
                })
            });

            // Cleanup
            std::fs::remove_file("test_wal_append.log").ok();
        });
    });
}

/// Benchmark WAL append with different payload sizes
fn bench_wal_append_sizes(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();

    let mut group = c.benchmark_group("wal_append_sizes");
    let sizes = vec![10, 100, 1000, 10000];

    for size in sizes {
        group.bench_with_input(BenchmarkId::from_parameter(size), &size, |b, &size| {
            rt.block_on(async {
                let wal = std::sync::Arc::new(tokio::sync::Mutex::new(
                    WriteAheadLog::new(format!("test_wal_size_{}.log", size).into())
                        .await
                        .unwrap(),
                ));

                // Create payload of specified size
                let mut data = json!({});
                for i in 0..size {
                    let key = format!("field_{}", i);
                    data[key] = json!(i);
                }

                b.iter(|| {
                    rt.block_on(async {
                        let mut wal_lock = wal.lock().await;
                        black_box(
                            wal_lock
                                .append("TEST_OPERATION".to_string(), data.clone())
                                .await
                                .unwrap(),
                        )
                    })
                });

                // Cleanup
                std::fs::remove_file(format!("test_wal_size_{}.log", size)).ok();
            });
        });
    }
    group.finish();
}

/// Benchmark WAL flush operation
fn bench_wal_flush(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();

    c.bench_function("wal_flush", |b| {
        rt.block_on(async {
            let wal = std::sync::Arc::new(tokio::sync::Mutex::new(
                WriteAheadLog::new("test_wal_flush.log".into())
                    .await
                    .unwrap(),
            ));

            // Write some data first
            {
                let mut wal_lock = wal.lock().await;
                for i in 0..100 {
                    let data = json!({"index": i});
                    wal_lock
                        .append("TEST_OPERATION".to_string(), data)
                        .await
                        .unwrap();
                }
            }

            b.iter(|| {
                rt.block_on(async {
                    let mut wal_lock = wal.lock().await;
                    black_box(wal_lock.flush().await.unwrap())
                })
            });

            // Cleanup
            std::fs::remove_file("test_wal_flush.log").ok();
        });
    });
}

/// Benchmark WAL replay operation
fn bench_wal_replay(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();

    c.bench_function("wal_replay", |b| {
        rt.block_on(async {
            let path = PathBuf::from("test_wal_replay.log");

            // Setup: write some entries
            {
                let mut wal = WriteAheadLog::new(path.clone()).await.unwrap();
                for i in 0..1000 {
                    let data = json!({
                        "id": format!("TEST-{:04}", i),
                        "index": i
                    });
                    wal.append("TEST_OPERATION".to_string(), data)
                        .await
                        .unwrap();
                }
                wal.flush().await.unwrap();
            }

            b.iter(|| {
                rt.block_on(async {
                    black_box(WriteAheadLog::replay_from_file(&path).await.unwrap())
                })
            });

            // Cleanup
            std::fs::remove_file(path).ok();
        });
    });
}

/// Benchmark concurrent WAL operations
fn bench_wal_concurrent(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();

    c.bench_function("wal_concurrent_writes", |b| {
        rt.block_on(async {
            let wal = std::sync::Arc::new(tokio::sync::RwLock::new(
                WriteAheadLog::new("test_wal_concurrent.log".into())
                    .await
                    .unwrap(),
            ));

            b.iter(|| {
                let wal_clone = wal.clone();
                rt.block_on(async move {
                    let mut wal_guard = wal_clone.write().await;
                    let data = json!({"timestamp": chrono::Utc::now().timestamp()});
                    black_box(
                        wal_guard
                            .append("CONCURRENT_OP".to_string(), data)
                            .await
                            .unwrap(),
                    )
                })
            });

            // Cleanup
            std::fs::remove_file("test_wal_concurrent.log").ok();
        });
    });
}

criterion_group!(
    benches,
    bench_wal_append,
    bench_wal_append_sizes,
    bench_wal_flush,
    bench_wal_replay,
    bench_wal_concurrent
);
criterion_main!(benches);
