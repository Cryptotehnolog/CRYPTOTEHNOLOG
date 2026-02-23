// ==================== CRYPTOTEHNOLOG Property-Based Tests ====================
// Merkle tree property-based tests

use cryptotechnolog_risk_ledger::merkle::MerkleTree;
use proptest::prelude::*;
use rand::Rng;

fn leaf_hashes(max: usize) -> impl Strategy<Value = Vec<[u8; 32]>> {
    proptest::collection::vec(
        proptest::collection::vec(proptest::num::u8::ANY, 32).prop_map(|v| {
            let mut arr = [0u8; 32];
            for (i, &byte) in v.iter().take(32).enumerate() { arr[i] = byte; }
            arr
        }),
        1..=max,
    )
}

fn random_leaf_hashes(count: usize) -> Vec<[u8; 32]> {
    let mut rng = rand::thread_rng();
    (0..count).map(|_| { let mut arr = [0u8; 32]; rng.fill(&mut arr); arr }).collect()
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(10000))]

    #[test]
    fn test_merkle_proof_verification(leaves in leaf_hashes(100)) {
        prop_assume!(!leaves.is_empty());
        let tree = MerkleTree::from_leaves(leaves.clone());
        for i in 0..leaves.len() {
            if let Some(proof) = tree.generate_proof(i) {
                prop_assert!(tree.verify(&leaves[i], &proof));
            }
        }
    }

    #[test]
    fn test_merkle_proof_wrong_leaf(leaves in leaf_hashes(50)) {
        prop_assume!(leaves.len() >= 2);
        let tree = MerkleTree::from_leaves(leaves.clone());
        let proof = tree.generate_proof(0).unwrap();
        prop_assert!(!tree.verify(&leaves[1], &proof));
    }

    #[test]
    fn test_merkle_root_consistency(leaves in leaf_hashes(64)) {
        let tree1 = MerkleTree::from_leaves(leaves.clone());
        let tree2 = MerkleTree::from_leaves(leaves.clone());
        prop_assert_eq!(tree1.root(), tree2.root());
    }

    #[test]
    fn test_merkle_modified_leaf(leaves in leaf_hashes(32)) {
        prop_assume!(!leaves.is_empty());
        let tree1 = MerkleTree::from_leaves(leaves.clone());
        let mut modified = leaves.clone();
        modified[0][0] = modified[0][0].wrapping_add(1);
        let tree2 = MerkleTree::from_leaves(modified);
        prop_assert_ne!(tree1.root(), tree2.root());
    }

    #[test]
    fn test_merkle_single_leaf(leaf in proptest::collection::vec(proptest::num::u8::ANY, 32).prop_map(|v| {
        let mut arr = [0u8; 32];
        for (i, &byte) in v.iter().take(32).enumerate() { arr[i] = byte; }
        arr
    })) {
        let tree = MerkleTree::from_leaves(vec![leaf.clone()]);
        prop_assert_eq!(tree.root(), leaf);
    }

    #[test]
    fn test_merkle_leaves_count(leaves in leaf_hashes(128)) {
        let tree = MerkleTree::from_leaves(leaves.clone());
        prop_assert_eq!(tree.leaves_count(), leaves.len());
    }

    #[test]
    fn test_merkle_height(leaves in leaf_hashes(128)) {
        let tree = MerkleTree::from_leaves(leaves.clone());
        let expected = if leaves.is_empty() { 0 } else { (leaves.len() as f64).log2().ceil() as usize };
        prop_assert_eq!(tree.height(), expected);
    }

    #[test]
    fn test_merkle_proof_path_length(leaves in leaf_hashes(64)) {
        prop_assume!(!leaves.is_empty());
        let tree = MerkleTree::from_leaves(leaves.clone());
        for i in 0..leaves.len() {
            if let Some(proof) = tree.generate_proof(i) {
                prop_assert_eq!(proof.path.len(), tree.height());
            }
        }
    }
}

#[test]
fn test_merkle_empty_tree() {
    let tree = MerkleTree::from_leaves(vec![]);
    assert_eq!(tree.root(), [0u8; 32]);
}

#[test]
fn test_merkle_odd_leaves() {
    for count in [3, 5, 7, 9, 15, 31, 63] {
        let leaves = random_leaf_hashes(count);
        let tree = MerkleTree::from_leaves(leaves.clone());
        assert_eq!(tree.leaves_count(), count);
        for i in 0..leaves.len() {
            if let Some(proof) = tree.generate_proof(i) {
                assert!(tree.verify(&leaves[i], &proof));
            }
        }
    }
}
