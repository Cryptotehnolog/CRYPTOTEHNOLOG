// ==================== CRYPTOTEHNOLOG Merkle Tree Benchmarks ====================
// Benchmarks for MerkleTree performance

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use cryptotechnolog_risk_ledger::merkle::MerkleTree;
use sha2::{Digest, Sha256};

/// Generate random hash
fn generate_hash(seed: u64) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(seed.to_le_bytes());
    hasher.finalize().into()
}

/// Benchmark Merkle tree construction
fn bench_merkle_construction(c: &mut Criterion) {
    let mut group = c.benchmark_group("merkle_construction");
    let leaf_counts = vec![10, 100, 1000, 10000];

    for count in leaf_counts {
        group.bench_with_input(BenchmarkId::from_parameter(count), &count, |b, &count| {
            let leaves: Vec<[u8; 32]> = (0..count).map(|i| generate_hash(i)).collect();

            b.iter(|| {
                black_box(MerkleTree::from_leaves(black_box(leaves.clone())))
            });
        });
    }
    group.finish();
}

/// Benchmark Merkle root calculation
fn bench_merkle_root(c: &mut Criterion) {
    let mut group = c.benchmark_group("merkle_root");
    let leaf_counts = vec![10, 100, 1000, 10000];

    for count in leaf_counts {
        group.bench_with_input(BenchmarkId::from_parameter(count), &count, |b, &count| {
            let leaves: Vec<[u8; 32]> = (0..count).map(|i| generate_hash(i)).collect();
            let tree = MerkleTree::from_leaves(leaves);

            b.iter(|| {
                black_box(tree.root())
            });
        });
    }
    group.finish();
}

/// Benchmark Merkle proof generation
fn bench_merkle_proof_generation(c: &mut Criterion) {
    let mut group = c.benchmark_group("merkle_proof_generation");
    let leaf_counts = vec![10, 100, 1000, 10000];

    for count in leaf_counts {
        group.bench_with_input(BenchmarkId::from_parameter(count), &count, |b, &count| {
            let leaves: Vec<[u8; 32]> = (0..count).map(|i| generate_hash(i)).collect();
            let tree = MerkleTree::from_leaves(leaves);

            b.iter(|| {
                let index = (count / 2) as usize;
                black_box(tree.generate_proof(black_box(index)))
            });
        });
    }
    group.finish();
}

/// Benchmark Merkle proof verification
fn bench_merkle_proof_verification(c: &mut Criterion) {
    let mut group = c.benchmark_group("merkle_proof_verification");
    let leaf_counts = vec![10, 100, 1000, 10000];

    for count in leaf_counts {
        group.bench_with_input(BenchmarkId::from_parameter(count), &count, |b, &count| {
            let leaves: Vec<[u8; 32]> = (0..count).map(|i| generate_hash(i)).collect();
            let tree = MerkleTree::from_leaves(leaves.clone());
            let index = (count / 2) as usize;
            let proof = tree.generate_proof(index).unwrap();

            b.iter(|| {
                black_box(tree.verify(black_box(&leaves[index]), black_box(&proof)))
            });
        });
    }
    group.finish();
}

/// Benchmark full Merkle tree lifecycle
fn bench_merkle_lifecycle(c: &mut Criterion) {
    let mut group = c.benchmark_group("merkle_lifecycle");
    let leaf_counts = vec![100, 1000];

    for count in leaf_counts {
        group.bench_with_input(BenchmarkId::from_parameter(count), &count, |b, &count| {
            b.iter(|| {
                // Build tree
                let leaves: Vec<[u8; 32]> = (0..count).map(|i| generate_hash(i)).collect();
                let tree = MerkleTree::from_leaves(black_box(leaves.clone()));

                // Get root
                let _root = black_box(tree.root());

                // Generate proof
                let index = (count / 2) as usize;
                let proof = black_box(tree.generate_proof(index).unwrap());

                // Verify proof
                let _verified = black_box(tree.verify(black_box(&leaves[index]), black_box(&proof)));
            });
        });
    }
    group.finish();
}

criterion_group!(
    benches,
    bench_merkle_construction,
    bench_merkle_root,
    bench_merkle_proof_generation,
    bench_merkle_proof_verification,
    bench_merkle_lifecycle
);
criterion_main!(benches);
