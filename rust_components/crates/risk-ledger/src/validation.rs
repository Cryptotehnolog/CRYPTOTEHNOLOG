// ==================== CRYPTOTEHNOLOG Risk Ledger Validation ====================
// Double-entry validation for risk ledger operations
//
// Double-entry validation ensures:
// - Every debit has a corresponding credit
// - Total debits equal total credits
// - Account balances remain consistent
// - No funds are created or destroyed

use serde::{Deserialize, Serialize};

/// Validation error types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ValidationError {
    /// Debits and credits are imbalanced
    Imbalance {
        total_debit: f64,
        total_credit: f64,
        difference: f64,
    },
    /// Invalid amount (negative or zero)
    InvalidAmount { amount: f64 },
    /// Invalid account
    InvalidAccount { account: String },
    /// Insufficient balance
    InsufficientBalance {
        account: String,
        balance: f64,
        required: f64,
    },
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ValidationError::Imbalance { total_debit, total_credit, difference } => {
                write!(
                    f,
                    "Balance mismatch: debits={}, credits={}, difference={}",
                    total_debit, total_credit, difference
                )
            }
            ValidationError::InvalidAmount { amount } => {
                write!(f, "Invalid amount: {}", amount)
            }
            ValidationError::InvalidAccount { account } => {
                write!(f, "Invalid account: {}", account)
            }
            ValidationError::InsufficientBalance { account, balance, required } => {
                write!(
                    f,
                    "Insufficient balance for {}: balance={}, required={}",
                    account, balance, required
                )
            }
        }
    }
}

impl std::error::Error for ValidationError {}

/// Transaction representing a single entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Account identifier
    pub account: String,
    /// Transaction amount (positive for credit, negative for debit)
    pub amount: f64,
    /// Transaction timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
    /// Transaction metadata
    pub metadata: Option<serde_json::Value>,
}

impl Transaction {
    /// Create a new transaction
    pub fn new(account: String, amount: f64) -> Self {
        Self {
            account,
            amount,
            timestamp: chrono::Utc::now(),
            metadata: None,
        }
    }

    /// Check if transaction is a debit
    pub fn is_debit(&self) -> bool {
        self.amount < 0.0
    }

    /// Check if transaction is a credit
    pub fn is_credit(&self) -> bool {
        self.amount > 0.0
    }

    /// Get absolute amount
    pub fn abs_amount(&self) -> f64 {
        self.amount.abs()
    }
}

/// Validator for double-entry transactions
pub struct DoubleEntryValidator {
    /// Tolerance for floating point comparison
    tolerance: f64,
}

impl DoubleEntryValidator {
    /// Create a new validator with default tolerance
    pub fn new() -> Self {
        Self {
            tolerance: 1e-9,
        }
    }

    /// Create a new validator with custom tolerance
    pub fn with_tolerance(tolerance: f64) -> Self {
        Self { tolerance }
    }

    /// Validate a set of transactions
    ///
    /// Ensures that total debits equal total credits
    pub fn validate(&self, transactions: &[Transaction]) -> Result<(), ValidationError> {
        let total_debit: f64 = transactions
            .iter()
            .filter(|t| t.is_debit())
            .map(|t| t.abs_amount())
            .sum();

        let total_credit: f64 = transactions
            .iter()
            .filter(|t| t.is_credit())
            .map(|t| t.abs_amount())
            .sum();

        let difference = (total_debit - total_credit).abs();

        if difference > self.tolerance {
            return Err(ValidationError::Imbalance {
                total_debit,
                total_credit,
                difference,
            });
        }

        Ok(())
    }

    /// Validate a single transaction amount
    pub fn validate_amount(&self, amount: f64) -> Result<(), ValidationError> {
        if amount.abs() < self.tolerance {
            return Err(ValidationError::InvalidAmount { amount });
        }

        if amount.is_nan() || amount.is_infinite() {
            return Err(ValidationError::InvalidAmount { amount });
        }

        Ok(())
    }

    /// Validate account balance
    pub fn validate_balance(
        &self,
        account: &str,
        balance: f64,
        required: f64,
    ) -> Result<(), ValidationError> {
        if balance < required {
            return Err(ValidationError::InsufficientBalance {
                account: account.to_string(),
                balance,
                required,
            });
        }

        Ok(())
    }
}

impl Default for DoubleEntryValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transaction_creation() {
        let tx = Transaction::new("account1".to_string(), 100.0);

        assert_eq!(tx.account, "account1");
        assert_eq!(tx.amount, 100.0);
        assert!(tx.is_credit());
        assert!(!tx.is_debit());
        assert_eq!(tx.abs_amount(), 100.0);
    }

    #[test]
    fn test_double_entry_validation_success() {
        let validator = DoubleEntryValidator::new();

        let transactions = vec![
            Transaction::new("account1".to_string(), -100.0), // Debit
            Transaction::new("account2".to_string(), 100.0),  // Credit
        ];

        assert!(validator.validate(&transactions).is_ok());
    }

    #[test]
    fn test_double_entry_validation_imbalance() {
        let validator = DoubleEntryValidator::new();

        let transactions = vec![
            Transaction::new("account1".to_string(), -100.0), // Debit
            Transaction::new("account2".to_string(), 90.0),   // Credit (10 short)
        ];

        let result = validator.validate(&transactions);
        assert!(result.is_err());

        if let Err(ValidationError::Imbalance { total_debit, total_credit, difference }) = result {
            assert_eq!(total_debit, 100.0);
            assert_eq!(total_credit, 90.0);
            assert_eq!(difference, 10.0);
        } else {
            panic!("Expected ValidationError::Imbalance");
        }
    }

    #[test]
    fn test_validate_amount_valid() {
        let validator = DoubleEntryValidator::new();

        assert!(validator.validate_amount(100.0).is_ok());
        assert!(validator.validate_amount(-100.0).is_ok());
    }

    #[test]
    fn test_validate_amount_invalid() {
        let validator = DoubleEntryValidator::new();

        assert!(validator.validate_amount(0.0).is_err());
        assert!(validator.validate_amount(f64::NAN).is_err());
        assert!(validator.validate_amount(f64::INFINITY).is_err());
    }

    #[test]
    fn test_validate_balance_success() {
        let validator = DoubleEntryValidator::new();

        assert!(validator.validate_balance("account1", 1000.0, 500.0).is_ok());
    }

    #[test]
    fn test_validate_balance_insufficient() {
        let validator = DoubleEntryValidator::new();

        let result = validator.validate_balance("account1", 100.0, 500.0);
        assert!(result.is_err());

        if let Err(ValidationError::InsufficientBalance { account, balance, required }) = result {
            assert_eq!(account, "account1");
            assert_eq!(balance, 100.0);
            assert_eq!(required, 500.0);
        } else {
            panic!("Expected ValidationError::InsufficientBalance");
        }
    }

    #[test]
    fn test_validator_with_tolerance() {
        let validator = DoubleEntryValidator::with_tolerance(0.01);

        let transactions = vec![
            Transaction::new("account1".to_string(), -100.0), // Debit
            Transaction::new("account2".to_string(), 100.005),  // Credit (0.005 over)
        ];

        // Should pass within tolerance
        assert!(validator.validate(&transactions).is_ok());
    }
}
