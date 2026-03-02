// ==================== CRYPTOTEHNOLOG Risk Ledger Benchmarks ====================
// Benchmarks for RiskLedger integrated performance
// Uses single-threaded runtime created once per benchmark for minimal overhead

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use cryptotechnolog_risk_ledger::ledger::Position;
use cryptotechnolog_risk_ledger::ledger::RiskLedger;
use tokio::runtime::Builder;

/// Benchmark RiskLedger creation
fn bench_ledger_creation(c: &mut Criterion) {
    c.bench_function("ledger_creation", |b| {
        b.iter(|| {
            // Create fresh runtime for each iteration (required for isolation)
            let rt = Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();
            let path = format!(
                "test_ledger_creation_{}.log",
                chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0)
            );
            rt.block_on(async { black_box(RiskLedger::new(path.into()).await.unwrap()) })
        });
    });
}

/// Benchmark position update
fn bench_position_update(c: &mut Criterion) {
    let position = Position {
        id: "BTC/USDT-1".to_string(),
        symbol: "BTC/USDT".to_string(),
        size: 100.0,
        entry_price: 50000.0,
        current_price: 51000.0,
        unrealized_pnl: 100000.0,
        timestamp: chrono::Utc::now(),
    };

    // Pre-create ledger
    let rt = Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    rt.block_on(async {
        let ledger = RiskLedger::new("test_ledger_update.log".into())
            .await
            .unwrap();

        let _ = ledger.update_position(position.clone()).await.unwrap();
    });

    // Benchmark with pre-created ledger
    c.bench_function("position_update", |b| {
        b.iter(|| {
            let rt = Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();
            rt.block_on(async {
                let ledger = RiskLedger::new("test_ledger_update.log".into())
                    .await
                    .unwrap();
                black_box(
                    ledger
                        .update_position(black_box(position.clone()))
                        .await
                        .unwrap(),
                )
            });
        });
    });

    // Cleanup
    std::fs::remove_file("test_ledger_update.log").ok();
}

/// Benchmark position retrieval
fn bench_position_retrieval(c: &mut Criterion) {
    // Pre-create ledger with data
    let rt = Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    rt.block_on(async {
        let ledger = RiskLedger::new("test_ledger_retrieve.log".into())
            .await
            .unwrap();
        let position = Position {
            id: "BTC/USDT-1".to_string(),
            symbol: "BTC/USDT".to_string(),
            size: 100.0,
            entry_price: 50000.0,
            current_price: 51000.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };
        ledger.update_position(position).await.unwrap();
    });

    c.bench_function("position_retrieval", |b| {
        b.iter(|| {
            let rt = Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();
            rt.block_on(async {
                let ledger = RiskLedger::new("test_ledger_retrieve.log".into())
                    .await
                    .unwrap();
                black_box(ledger.get_position(black_box("BTC/USDT-1")).await)
            })
        });
    });

    // Cleanup after benchmark
    std::fs::remove_file("test_ledger_retrieve.log").ok();
}

/// Benchmark portfolio value calculation
fn bench_portfolio_calculation(c: &mut Criterion) {
    let mut group = c.benchmark_group("portfolio_calculation");
    let position_counts = vec![1, 10, 100, 1000];

    for count in position_counts {
        group.bench_with_input(BenchmarkId::from_parameter(count), &count, |b, &count| {
            // Pre-create ledger with positions
            let rt = Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();
            rt.block_on(async {
                let ledger = RiskLedger::new(
                    format!("test_ledger_portfolio_{}.log", count).into(),
                )
                .await
                .unwrap();

                for i in 0..count {
                    let position = Position {
                        id: format!("SYMBOL-{}/USDT-{}", i % 10, i),
                        symbol: format!("SYMBOL-{}/USDT", i % 10),
                        size: 100.0,
                        entry_price: 50000.0,
                        current_price: 51000.0,
                        unrealized_pnl: 100000.0,
                        timestamp: chrono::Utc::now(),
                    };
                    ledger.update_position(position).await.unwrap();
                }
            });

            b.iter(|| {
                let rt = Builder::new_current_thread()
                    .enable_all()
                    .build()
                    .unwrap();
                rt.block_on(async {
                    let ledger = RiskLedger::new(
                        format!("test_ledger_portfolio_{}.log", count).into(),
                    )
                    .await
                    .unwrap();
                    black_box(ledger.calculate_portfolio_value().await)
                })
            });

            // Cleanup
            std::fs::remove_file(format!("test_ledger_portfolio_{}.log", count)).ok();
        });
    }
    group.finish();
}

/// Benchmark Merkle proof generation
fn bench_merkle_proof_ledger(c: &mut Criterion) {
    // Pre-create ledger with 100 positions
    let rt = Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    rt.block_on(async {
        let ledger = RiskLedger::new("test_ledger_merkle.log".into())
            .await
            .unwrap();

        for i in 0..100 {
            let position = Position {
                id: format!("BTC/USDT-{}", i),
                symbol: "BTC/USDT".to_string(),
                size: 100.0,
                entry_price: 50000.0,
                current_price: 51000.0,
                unrealized_pnl: 100000.0,
                timestamp: chrono::Utc::now(),
            };
            ledger.update_position(position).await.unwrap();
        }
    });

    c.bench_function("merkle_proof_ledger", |b| {
        b.iter(|| {
            let rt = Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();
            rt.block_on(async {
                let ledger = RiskLedger::new("test_ledger_merkle.log".into())
                    .await
                    .unwrap();
                black_box(ledger.generate_proof(black_box("BTC/USDT-50")).await)
            })
        });
    });

    std::fs::remove_file("test_ledger_merkle.log").ok();
}

/// Benchmark Merkle proof verification
fn bench_merkle_verify_ledger(c: &mut Criterion) {
    let rt = Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    let proof = rt.block_on(async {
        let ledger = RiskLedger::new("test_ledger_verify.log".into())
            .await
            .unwrap();

        let position = Position {
            id: "BTC/USDT-1".to_string(),
            symbol: "BTC/USDT".to_string(),
            size: 100.0,
            entry_price: 50000.0,
            current_price: 51000.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };
        ledger.update_position(position).await.unwrap();
        ledger.generate_proof("BTC/USDT-1").await.unwrap()
    });

    c.bench_function("merkle_verify_ledger", |b| {
        b.iter(|| {
            let rt = Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();
            rt.block_on(async {
                let ledger = RiskLedger::new("test_ledger_verify.log".into())
                    .await
                    .unwrap();
                black_box(
                    ledger
                        .verify_proof(black_box("BTC/USDT-1"), black_box(&proof))
                        .await,
                )
            })
        });
    });

    std::fs::remove_file("test_ledger_verify.log").ok();
}

/// Benchmark WAL replay
fn bench_wal_replay_ledger(c: &mut Criterion) {
    let path = "test_ledger_replay.log";

    // Setup: write 100 positions to WAL
    let setup_rt = Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    setup_rt.block_on(async {
        let ledger = RiskLedger::new(path.into()).await.unwrap();
        for i in 0..100 {
            let position = Position {
                id: format!("BTC/USDT-{}", i),
                symbol: "BTC/USDT".to_string(),
                size: 100.0,
                entry_price: 50000.0,
                current_price: 51000.0,
                unrealized_pnl: 100000.0,
                timestamp: chrono::Utc::now(),
            };
            ledger.update_position(position).await.unwrap();
        }
        ledger.close_wal().await.unwrap();
    });

    c.bench_function("wal_replay_ledger", |b| {
        b.iter(|| {
            let rt = Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();
            rt.block_on(async {
                let ledger = RiskLedger::new(path.into()).await.unwrap();
                black_box(ledger.replay_wal().await.unwrap())
            })
        });
    });

    // Cleanup
    std::fs::remove_file(path).ok();
}

/// Benchmark full position lifecycle
fn bench_position_lifecycle(c: &mut Criterion) {
    c.bench_function("position_lifecycle", |b| {
        b.iter(|| {
            let rt = Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();
            rt.block_on(async {
                let ledger = RiskLedger::new("test_ledger_lifecycle.log".into())
                    .await
                    .unwrap();

                let position = Position {
                    id: format!(
                        "BTC/USDT-{}",
                        chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0)
                    ),
                    symbol: "BTC/USDT".to_string(),
                    size: 100.0,
                    entry_price: 50000.0,
                    current_price: 51000.0,
                    unrealized_pnl: 100000.0,
                    timestamp: chrono::Utc::now(),
                };

                black_box(ledger.update_position(position).await.unwrap());
                black_box(ledger.get_all_positions().await);
                black_box(ledger.calculate_portfolio_value().await);
                black_box(ledger.calculate_total_pnl().await);

                ledger.close().await.ok();
            });

            std::fs::remove_file("test_ledger_lifecycle.log").ok();
        });
    });
}

criterion_group!(
    benches,
    bench_ledger_creation,
    bench_position_update,
    bench_position_retrieval,
    bench_portfolio_calculation,
    bench_merkle_proof_ledger,
    bench_merkle_verify_ledger,
    bench_wal_replay_ledger,
    bench_position_lifecycle
);
criterion_main!(benches);
