// ==================== CRYPTOTEHNOLOG Risk Ledger Crate ====================
// High-performance risk ledger with WAL, Merkle tree, and double-entry validation
//
// Features:
// - Append-only operations
// - WAL for durability
// - Merkle tree for integrity
// - Double-entry validation for consistency
// - O(log n) proof generation and verification
//
// Performance targets:
// - 100,000+ position updates per second
// - Sub-millisecond risk calculations
// - Zero-copy operations for high-frequency paths

// Force cargo to recognize these dependencies at crate level
pub use cryptotechnolog_audit_chain as _audit_chain;
pub use cryptotechnolog_common as _common;

pub mod ledger;
pub mod merkle;
pub mod validation;
pub mod wal;

// ==================== Re-exports ====================
pub use ledger::{Position, RiskLedger};
pub use merkle::{MerkleProof, MerkleTree};
pub use validation::{DoubleEntryValidator, Transaction, ValidationError};
pub use wal::{WALEntry, WriteAheadLog};
