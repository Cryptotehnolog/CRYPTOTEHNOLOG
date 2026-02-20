// ==================== CRYPTOTEHNOLOG Merkle Tree ====================
// In-memory Merkle tree for risk ledger integrity verification
//
// The Merkle tree provides:
// - O(log n) proof generation and verification
// - Historical data integrity
// - Tamper-evidence detection
// - Efficient root hash computation

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fmt;

/// Merkle proof for verifying leaf inclusion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleProof {
    /// Hash of the leaf
    pub leaf_hash: [u8; 32],
    /// Sibling hashes along the path
    pub path: Vec<[u8; 32]>,
    /// Direction for each sibling (true = right sibling, false = left sibling)
    pub directions: Vec<bool>,
}

/// Merkle tree for integrity verification
pub struct MerkleTree {
    /// Tree nodes (leaf nodes are first)
    nodes: Vec<[u8; 32]>,
    /// Number of leaf nodes
    leaves: usize,
}

impl MerkleTree {
    /// Create a new Merkle tree from leaf hashes
    pub fn from_leaves(leaves: Vec<[u8; 32]>) -> Self {
        let leaves_count = leaves.len();

        if leaves_count == 0 {
            return Self {
                nodes: vec![],
                leaves: 0,
            };
        }

        // Start with leaves
        let mut nodes = leaves.clone();

        // Build tree level by level
        let mut level_start = 0;
        let mut level_size = leaves_count;

        while level_size > 1 {
            // Process pairs at current level
            for i in 0..(level_size / 2) {
                let left = nodes[level_start + 2 * i];
                let right = nodes[level_start + 2 * i + 1];
                let parent = Self::hash_pair(&left, &right);
                nodes.push(parent);
            }

            // Handle odd number of nodes
            if level_size % 2 == 1 {
                let last = nodes[level_start + level_size - 1];
                let parent = Self::hash_pair(&last, &last);
                nodes.push(parent);
            }

            level_start += level_size;
            level_size = (level_size + 1) / 2;
        }

        Self {
            nodes,
            leaves: leaves_count,
        }
    }

    /// Get the root hash of the Merkle tree
    pub fn root(&self) -> [u8; 32] {
        if self.nodes.is_empty() {
            [0u8; 32]
        } else {
            *self.nodes.last().unwrap()
        }
    }

    /// Generate a Merkle proof for a leaf
    pub fn generate_proof(&self, leaf_index: usize) -> Option<MerkleProof> {
        if leaf_index >= self.leaves {
            return None;
        }

        let mut path = Vec::new();
        let mut directions = Vec::new();
        let mut level_start = 0;
        let mut level_size = self.leaves;
        let mut current_index = leaf_index;

        while level_size > 1 {
            // Determine if current node is left or right child
            let is_right = current_index % 2 == 1;
            directions.push(is_right);

            // Get sibling index
            let sibling_index = if is_right {
                current_index - 1
            } else {
                current_index + 1
            };

            // Add sibling hash to path (if it exists)
            if sibling_index < level_size {
                path.push(self.nodes[level_start + sibling_index]);
            }

            // Move to parent level
            current_index /= 2;
            level_start += level_size;
            level_size = (level_size + 1) / 2;
        }

        Some(MerkleProof {
            leaf_hash: self.nodes[leaf_index],
            path,
            directions,
        })
    }

    /// Verify a Merkle proof
    pub fn verify(&self, leaf_hash: &[u8; 32], proof: &MerkleProof) -> bool {
        if leaf_hash != &proof.leaf_hash {
            return false;
        }

        let mut current_hash = *leaf_hash;

        for (i, sibling_hash) in proof.path.iter().enumerate() {
            if proof.directions[i] {
                // Current hash is right child
                current_hash = Self::hash_pair(sibling_hash, &current_hash);
            } else {
                // Current hash is left child
                current_hash = Self::hash_pair(&current_hash, sibling_hash);
            }
        }

        current_hash == self.root()
    }

    /// Hash a pair of nodes
    fn hash_pair(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(left);
        hasher.update(right);
        hasher.finalize().into()
    }

    /// Get the number of leaves
    pub fn leaves_count(&self) -> usize {
        self.leaves
    }

    /// Get the height of the tree
    pub fn height(&self) -> usize {
        if self.leaves == 0 {
            0
        } else {
            (self.leaves as f64).log2().ceil() as usize
        }
    }
}

impl fmt::Display for MerkleTree {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(f, "MerkleTree:")?;
        writeln!(f, "  Leaves: {}", self.leaves)?;
        writeln!(f, "  Height: {}", self.height())?;
        writeln!(f, "  Root: {}", hex::encode(self.root()))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hash_data(data: &str) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        hasher.finalize().into()
    }

    #[test]
    fn test_merkle_tree_creation() {
        let leaves = vec![
            hash_data("leaf1"),
            hash_data("leaf2"),
            hash_data("leaf3"),
            hash_data("leaf4"),
        ];

        let tree = MerkleTree::from_leaves(leaves);

        assert_eq!(tree.leaves_count(), 4);
        assert_eq!(tree.height(), 2);
    }

    #[test]
    fn test_merkle_tree_root() {
        let leaves = vec![
            hash_data("leaf1"),
            hash_data("leaf2"),
        ];

        let tree = MerkleTree::from_leaves(leaves);
        let root = tree.root();

        // Root should be hash of leaf1 + leaf2
        let expected = MerkleTree::hash_pair(&hash_data("leaf1"), &hash_data("leaf2"));
        assert_eq!(root, expected);
    }

    #[test]
    fn test_merkle_proof_generation() {
        let leaves = vec![
            hash_data("leaf1"),
            hash_data("leaf2"),
            hash_data("leaf3"),
            hash_data("leaf4"),
        ];

        let tree = MerkleTree::from_leaves(leaves);

        // Generate proof for leaf 1
        let proof = tree.generate_proof(1).unwrap();
        assert_eq!(proof.leaf_hash, hash_data("leaf2"));
        assert_eq!(proof.path.len(), 2); // height = 2
    }

    #[test]
    fn test_merkle_proof_verification() {
        let leaves = vec![
            hash_data("leaf1"),
            hash_data("leaf2"),
            hash_data("leaf3"),
            hash_data("leaf4"),
        ];

        let tree = MerkleTree::from_leaves(leaves);

        // Generate and verify proof for leaf 1
        let proof = tree.generate_proof(1).unwrap();
        assert!(tree.verify(&hash_data("leaf2"), &proof));
    }

    #[test]
    fn test_merkle_tree_odd_leaves() {
        let leaves = vec![
            hash_data("leaf1"),
            hash_data("leaf2"),
            hash_data("leaf3"),
        ];

        let tree = MerkleTree::from_leaves(leaves);

        assert_eq!(tree.leaves_count(), 3);
        assert!(tree.root() != [0u8; 32]);
    }

    #[test]
    fn test_merkle_tree_empty() {
        let leaves = vec![];
        let tree = MerkleTree::from_leaves(leaves);

        assert_eq!(tree.leaves_count(), 0);
        assert_eq!(tree.root(), [0u8; 32]);
    }
}
