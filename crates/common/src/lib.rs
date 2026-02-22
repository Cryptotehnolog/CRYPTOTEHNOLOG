// ==================== CRYPTOTEHNOLOG Common Crate ====================
// Shared types, errors, and utilities

pub mod error;
pub mod utils;

// ==================== Re-exports ====================
// Re-export commonly used types for convenience
pub use error::{CryptoError, Result};

// ==================== Public API ====================
// Utility functions
pub use utils::{clamp, compute_hash, percentage, round, validate_range};

// ==================== Tests ====================
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_hash() {
        let data = b"test data";
        let hash = compute_hash(data);

        assert_eq!(hash.len(), 64); // SHA-256 produces 64 hex characters
        assert!(!hash.is_empty());
    }

    #[test]
    fn test_validate_range_success() {
        let result = validate_range(5, 1, 10);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_range_below_min() {
        let result = validate_range(0, 1, 10);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_range_above_max() {
        let result = validate_range(11, 1, 10);
        assert!(result.is_err());
    }

    #[test]
    fn test_clamp() {
        assert_eq!(clamp(5, 1, 10), 5);
        assert_eq!(clamp(0, 1, 10), 1);
        assert_eq!(clamp(11, 1, 10), 10);
    }
}
