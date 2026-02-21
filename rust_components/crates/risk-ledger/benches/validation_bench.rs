// ==================== CRYPTOTEHNOLOG Validation Benchmarks ====================
// Benchmarks for double-entry validation performance

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use cryptotechnolog_risk_ledger::validation::{DoubleEntryValidator, Transaction};

/// Benchmark double-entry validation
fn bench_double_entry_validation(c: &mut Criterion) {
    let mut group = c.benchmark_group("double_entry_validation");
    let transaction_counts = vec![2, 10, 100, 1000];

    for count in transaction_counts {
        group.bench_with_input(BenchmarkId::from_parameter(count), &count, |b, &count| {
            let validator = DoubleEntryValidator::new();

            // Create balanced transactions (debits are negative, credits are positive)
            let mut transactions = Vec::new();

            for i in 0..(count / 2) {
                let amount = 100.0;
                transactions.push(Transaction::new(format!("ACCOUNT_{}", i), -amount)); // Debit
                transactions.push(Transaction::new(format!("ACCOUNT_{}", i + 1000), amount)); // Credit
            }

            b.iter(|| {
                black_box(validator.validate(black_box(&transactions)).unwrap())
            });
        });
    }
    group.finish();
}

/// Benchmark transaction creation
fn bench_transaction_creation(c: &mut Criterion) {
    c.bench_function("transaction_creation", |b| {
        b.iter(|| {
            black_box(Transaction::new(
                "TEST_ACCOUNT".to_string(),
                100.0,
            ))
        });
    });
}

/// Benchmark validator creation
fn bench_validator_creation(c: &mut Criterion) {
    c.bench_function("validator_creation", |b| {
        b.iter(|| {
            black_box(DoubleEntryValidator::new())
        });
    });
}

/// Benchmark imbalance detection
fn bench_imbalance_detection(c: &mut Criterion) {
    let validator = DoubleEntryValidator::new();

    c.bench_function("imbalance_detection", |b| {
        b.iter(|| {
            let transactions = vec![
                Transaction::new("ACCOUNT_1".to_string(), -100.0), // Debit
                Transaction::new("ACCOUNT_2".to_string(), -50.0),  // Debit
                Transaction::new("ACCOUNT_3".to_string(), 100.0),  // Credit
                Transaction::new("ACCOUNT_4".to_string(), 49.99),  // Credit (0.01 imbalanced)
            ];

            black_box(validator.validate(&transactions))
        });
    });
}

/// Benchmark concurrent validation
fn bench_concurrent_validation(c: &mut Criterion) {
    let mut group = c.benchmark_group("concurrent_validation");
    let thread_counts = vec![1, 2, 4, 8];

    for count in thread_counts {
        group.bench_with_input(BenchmarkId::from_parameter(count), &count, |b, &count| {
            b.iter(|| {
                use std::sync::Arc;
                use std::thread;

                let validator = Arc::new(DoubleEntryValidator::new());
                let mut handles = vec![];

                for _ in 0..count {
                    let validator_clone = validator.clone();
                    let handle = thread::spawn(move || {
                        let transactions = vec![
                            Transaction::new("ACCOUNT_1".to_string(), -100.0), // Debit
                            Transaction::new("ACCOUNT_2".to_string(), 100.0),  // Credit
                        ];
                        validator_clone.validate(&transactions)
                    });
                    handles.push(handle);
                }

                for handle in handles {
                    let _ = black_box(handle.join().unwrap());
                }
            });
        });
    }
    group.finish();
}

/// Benchmark validation with varying amounts
fn bench_validation_amounts(c: &mut Criterion) {
    let mut group = c.benchmark_group("validation_amounts");
    let amounts = vec![0.01, 1.0, 100.0, 10000.0, 1000000.0];

    for amount in amounts {
        group.bench_with_input(BenchmarkId::from_parameter(amount), &amount, |b, &amount| {
            let validator = DoubleEntryValidator::new();

            b.iter(|| {
                let transactions = vec![
                    Transaction::new("ACCOUNT_1".to_string(), -amount), // Debit
                    Transaction::new("ACCOUNT_2".to_string(), amount),  // Credit
                ];

                black_box(validator.validate(&transactions).unwrap())
            });
        });
    }
    group.finish();
}

criterion_group!(
    benches,
    bench_double_entry_validation,
    bench_transaction_creation,
    bench_validator_creation,
    bench_imbalance_detection,
    bench_concurrent_validation,
    bench_validation_amounts
);
criterion_main!(benches);
