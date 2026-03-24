// ==================== CRYPTOTEHNOLOG Audit Chain Crate ====================
// Immutable audit chain for regulatory compliance
//
//
// Core features:
// - Cryptographic audit chain (hash-based linking)
// - Immutable audit records
// - Regulatory compliance logging
// - Audit trail verification
// - Export for regulatory reporting
//
// Security properties:
// - Tamper-proof (cryptographic linking)
// - Immutable records
// - Verifiable chain integrity
// - SEC/MiFID II/SOX compliance ready

pub mod audit;

// ==================== Re-exports ====================
pub use audit::{AuditChain, AuditError, AuditRecord};
