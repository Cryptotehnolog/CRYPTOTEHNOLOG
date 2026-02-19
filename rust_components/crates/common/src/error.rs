// ==================== CRYPTOTEHNOLOG Error Types ====================
// Comprehensive error handling for the trading platform

use thiserror::Error;

/// Main error type for CRYPTOTEHNOLOG
///
/// This enum encompasses all possible error types that can occur
/// in the high-performance components of the trading platform.
#[derive(Error, Debug)]
pub enum CryptoError {
    /// IO errors from file system operations
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// JSON serialization/deserialization errors
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// Redis connection and operation errors
    #[error("Redis error: {0}")]
    Redis(String),

    /// Cryptographic operation errors
    #[error("Cryptography error: {0}")]
    Cryptography(String),

    /// Validation errors for inputs and configurations
    #[error("Validation error: {0}")]
    Validation(String),

    /// Network connectivity and communication errors
    #[error("Network error: {0}")]
    Network(String),

    /// Configuration loading and parsing errors
    #[error("Configuration error: {0}")]
    Configuration(String),

    /// Internal system errors
    #[error("Internal error: {0}")]
    Internal(String),

    /// Database errors
    #[error("Database error: {0}")]
    Database(String),

    /// Event bus errors
    #[error("Event bus error: {0}")]
    EventBus(String),

    /// Risk management errors
    #[error("Risk management error: {0}")]
    Risk(String),

    /// Execution errors
    #[error("Execution error: {0}")]
    Execution(String),
}

/// Result type alias for convenient error handling
///
/// Usage:
/// ```rust,ignore
/// use cryptotechnolog_common::error::{CryptoError, Result};
///
/// fn do_something() -> Result<String> {
///     Ok("success".to_string())
/// }
/// ```
pub type Result<T> = std::result::Result<T, CryptoError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_display() {
        let error = CryptoError::Redis("connection failed".to_string());
        assert_eq!(error.to_string(), "Redis error: connection failed");
    }

    #[test]
    fn test_error_from_io() {
        let io_error = std::io::Error::new(std::io::ErrorKind::NotFound, "file not found");
        let crypto_error: CryptoError = io_error.into();
        assert!(matches!(crypto_error, CryptoError::Io(_)));
    }

    #[test]
    fn test_result_type() {
        let result: Result<String> = Ok("test".to_string());
        assert!(result.is_ok());

        let error: Result<String> = Err(CryptoError::Validation("invalid value".to_string()));
        assert!(error.is_err());
    }
}
