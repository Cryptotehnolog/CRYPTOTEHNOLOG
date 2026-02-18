// ==================== CRYPTOTEHNOLOG Utilities ====================
// Common utility functions for the trading platform

use super::error::{CryptoError, Result};
use sha2::{Digest, Sha256};

/// Compute SHA-256 hash of data
///
/// # Arguments
///
/// * `data` - Bytes to hash
///
/// # Returns
///
/// Hex-encoded SHA-256 hash string
///
/// # Examples
///
/// ```rust,ignore
/// use cryptotechnolog_core::utils;
///
/// let hash = utils::compute_hash(b"test data");
/// assert_eq!(hash.len(), 64); // SHA-256 produces 64 hex characters
/// ```
pub fn compute_hash(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let result = hasher.finalize();
    hex::encode(result)
}

/// Validate that a value is within a range
///
/// # Arguments
///
/// * `value` - Value to validate
/// * `min` - Minimum allowed value (inclusive)
/// * `max` - Maximum allowed value (inclusive)
///
/// # Returns
///
/// Ok(()) if value is in range, Err otherwise
///
/// # Examples
///
/// ```rust,ignore
/// use cryptotechnolog_core::utils;
///
/// let result = utils::validate_range(5, 1, 10);
/// assert!(result.is_ok());
///
/// let result = utils::validate_range(0, 1, 10);
/// assert!(result.is_err());
/// ```
pub fn validate_range<T>(value: T, min: T, max: T) -> Result<()>
where
    T: PartialOrd + std::fmt::Display,
{
    if value < min {
        return Err(CryptoError::Validation(format!(
            "Value {} is below minimum {}",
            value, min
        )));
    }
    if value > max {
        return Err(CryptoError::Validation(format!(
            "Value {} is above maximum {}",
            value, max
        )));
    }
    Ok(())
}

/// Clamp a value to a range
///
/// # Arguments
///
/// * `value` - Value to clamp
/// * `min` - Minimum value
/// * `max` - Maximum value
///
/// # Returns
///
/// Clamped value within [min, max]
///
/// # Examples
///
/// ```rust,ignore
/// use cryptotechnolog_core::utils;
///
/// assert_eq!(utils::clamp(5, 1, 10), 5);
/// assert_eq!(utils::clamp(0, 1, 10), 1);
/// assert_eq!(utils::clamp(11, 1, 10), 10);
/// ```
pub fn clamp<T>(value: T, min: T, max: T) -> T
where
    T: PartialOrd + Ord,
{
    if value < min {
        min
    } else if value > max {
        max
    } else {
        value
    }
}

/// Calculate percentage
///
/// # Arguments
///
/// * `value` - Current value
/// * `total` - Total value
///
/// # Returns
///
/// Percentage as f64
///
/// # Examples
///
/// ```rust,ignore
/// use cryptotechnolog_core::utils;
///
/// let percentage = utils::percentage(50, 100);
/// assert_eq!(percentage, 0.5);
/// ```
pub fn percentage(value: f64, total: f64) -> f64 {
    if total == 0.0 {
        0.0
    } else {
        value / total
    }
}

/// Round to specified decimal places
///
/// # Arguments
///
/// * `value` - Value to round
/// * `decimals` - Number of decimal places
///
/// # Returns
///
/// Rounded value
///
/// # Examples
///
/// ```rust,ignore
/// use cryptotechnolog_core::utils;
///
/// let rounded = utils::round(3.14159, 2);
/// assert_eq!(rounded, 3.14);
/// ```
pub fn round(value: f64, decimals: u32) -> f64 {
    let multiplier = 10_f64.powi(decimals as i32);
    (value * multiplier).round() / multiplier
}

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
    fn test_compute_hash_deterministic() {
        let data = b"test data";
        let hash1 = compute_hash(data);
        let hash2 = compute_hash(data);

        assert_eq!(hash1, hash2); // Hash should be deterministic
    }

    #[test]
    fn test_validate_range_success() {
        let result = validate_range(5, 1, 10);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_range_at_bounds() {
        let result = validate_range(1, 1, 10);
        assert!(result.is_ok());

        let result = validate_range(10, 1, 10);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_range_below_min() {
        let result = validate_range(0, 1, 10);
        assert!(result.is_err());
        if let Err(CryptoError::Validation(msg)) = result {
            assert!(msg.contains("below minimum"));
        }
    }

    #[test]
    fn test_validate_range_above_max() {
        let result = validate_range(11, 1, 10);
        assert!(result.is_err());
        if let Err(CryptoError::Validation(msg)) = result {
            assert!(msg.contains("above maximum"));
        }
    }

    #[test]
    fn test_clamp() {
        assert_eq!(clamp(5, 1, 10), 5);
        assert_eq!(clamp(0, 1, 10), 1);
        assert_eq!(clamp(11, 1, 10), 10);
        assert_eq!(clamp(1, 1, 10), 1);
        assert_eq!(clamp(10, 1, 10), 10);
    }

    #[test]
    fn test_percentage() {
        assert_eq!(percentage(50.0, 100.0), 0.5);
        assert_eq!(percentage(25.0, 100.0), 0.25);
        assert_eq!(percentage(100.0, 100.0), 1.0);
        assert_eq!(percentage(0.0, 100.0), 0.0);
        assert_eq!(percentage(50.0, 0.0), 0.0); // Division by zero protection
    }

    #[test]
    fn test_round() {
        assert_eq!(round(3.14159, 2), 3.14);
        assert_eq!(round(3.149, 2), 3.15);
        assert_eq!(round(3.1449, 2), 3.14);
        assert_eq!(round(3.0, 0), 3.0);
    }
}
