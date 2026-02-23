// ==================== CRYPTOTEHNOLOG Property-Based Tests ====================
// Double-entry validation property-based tests

use cryptotechnolog_risk_ledger::validation::{DoubleEntryValidator, Transaction, ValidationError};
use proptest::prelude::*;
use rand::Rng;

fn balanced_transactions() -> impl Strategy<Value = Vec<Transaction>> {
    (2..=10u32).prop_flat_map(|count| {
        proptest::collection::vec(
            (1.0f64..10000.0).prop_map(|amount| {
                let mut rng = rand::thread_rng();
                let sign: f64 = if rng.gen::<bool>() { 1.0 } else { -1.0 };
                Transaction::new(format!("account_{}", rng.gen::<u32>() % 100), amount * sign)
            }),
            (count * 2) as usize,
        )
    })
}

fn unbalanced_transactions() -> impl Strategy<Value = Vec<Transaction>> {
    proptest::collection::vec(
        proptest::num::f64::ANY.prop_map(|amount| {
            let mut rng = rand::thread_rng();
            Transaction::new(format!("account_{}", rng.gen::<u32>() % 100), amount)
        }),
        2..20,
    ).prop_filter("unbalanced", |txs| txs.iter().map(|t| t.amount).sum::<f64>().abs() > 1e-6)
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(10000))]

    #[test]
    fn test_double_entry_balanced_transactions(transactions in balanced_transactions()) {
        let validator = DoubleEntryValidator::new();
        let result = validator.validate(&transactions);
        let total_debit: f64 = transactions.iter().filter(|t| t.is_debit()).map(|t| t.abs_amount()).sum();
        let total_credit: f64 = transactions.iter().filter(|t| t.is_credit()).map(|t| t.abs_amount()).sum();
        if (total_debit - total_credit).abs() <= 1e-9 {
            prop_assert!(result.is_ok());
        }
    }

    #[test]
    fn test_double_entry_unbalanced_transactions(transactions in unbalanced_transactions()) {
        let validator = DoubleEntryValidator::new();
        let result = validator.validate(&transactions);
        prop_assert!(result.is_err());
        if let Err(ValidationError::Imbalance { difference, .. }) = result {
            prop_assert!(difference > 1e-9);
        }
    }

    #[test]
    fn test_double_entry_validation_consistency(transactions in balanced_transactions()) {
        let validator1 = DoubleEntryValidator::new();
        let validator2 = DoubleEntryValidator::new();
        let result1 = validator1.validate(&transactions);
        let result2 = validator2.validate(&transactions);
        match (result1, result2) {
            (Ok(_), Ok(_)) | (Err(_), Err(_)) => {}
            _ => panic!("Results should be consistent"),
        }
    }

    #[test]
    fn test_single_balanced_pair(amount in 1.0f64..1_000_000.0) {
        let validator = DoubleEntryValidator::new();
        let transactions = vec![
            Transaction::new("account1".to_string(), -amount),
            Transaction::new("account2".to_string(), amount),
        ];
        prop_assert!(validator.validate(&transactions).is_ok());
    }

    #[test]
    fn test_multiple_accounts_net_zero(accounts in proptest::collection::vec(1.0f64..10000.0, 2..10)) {
        let validator = DoubleEntryValidator::new();
        
        // Create exactly balanced transactions
        let mut transactions = Vec::new();
        for (i, &amount) in accounts.iter().enumerate() {
            if i % 2 == 0 {
                transactions.push(Transaction::new(format!("account_{}", i), -amount));
            } else {
                transactions.push(Transaction::new(format!("account_{}", i), amount));
            }
        }
        
        // Add balancing transaction to make sum exactly zero
        let total: f64 = transactions.iter().map(|t| t.amount).sum();
        transactions.push(Transaction::new("balance".to_string(), -total));
        
        prop_assert!(validator.validate(&transactions).is_ok());
    }

    #[test]
    fn test_amount_validation_rejects_invalid(
        amount in proptest::num::f64::ANY.prop_filter("invalid", |x| x.is_nan() || x.is_infinite() || x.abs() < 1e-9)
    ) {
        let validator = DoubleEntryValidator::new();
        prop_assert!(validator.validate_amount(amount).is_err());
    }

    #[test]
    fn test_amount_validation_accepts_valid(amount in 1.0f64..1_000_000.0) {
        let validator = DoubleEntryValidator::new();
        prop_assert!(validator.validate_amount(amount).is_ok());
    }

    #[test]
    fn test_balance_validation(balance in 0.0f64..1_000_000.0, required in 0.0f64..1_000_000.0) {
        let validator = DoubleEntryValidator::new();
        let result = validator.validate_balance("test_account", balance, required);
        if balance >= required {
            prop_assert!(result.is_ok());
        } else {
            prop_assert!(result.is_err());
        }
    }
}
