// ==================== CRYPTOTEHNOLOG Property-Based Tests ====================
// Risk calculation property-based tests
//
// These tests verify that risk calculations maintain
// their invariants across 10,000+ random inputs.

use proptest::prelude::*;

// ==================== Position Sizing Tests ====================

/// Calculate position size based on risk parameters
fn calculate_position_size(
    account_balance: f64,
    risk_percent: f64,
    entry_price: f64,
    stop_loss_price: f64,
) -> f64 {
    if stop_loss_price <= 0.0 || entry_price <= 0.0 || account_balance <= 0.0 {
        return 0.0;
    }

    let risk_amount = account_balance * (risk_percent / 100.0);
    let price_risk = (entry_price - stop_loss_price).abs();

    if price_risk <= 0.0 {
        return 0.0;
    }

    risk_amount / price_risk
}

/// Calculate stop loss price for long position
fn calculate_stop_loss_long(entry_price: f64, risk_percent: f64) -> f64 {
    entry_price * (1.0 - risk_percent / 100.0)
}

/// Calculate stop loss price for short position
fn calculate_stop_loss_short(entry_price: f64, risk_percent: f64) -> f64 {
    entry_price * (1.0 + risk_percent / 100.0)
}

/// Calculate position PnL
fn calculate_pnl(position_size: f64, entry_price: f64, exit_price: f64, is_long: bool) -> f64 {
    let price_diff = exit_price - entry_price;
    if is_long {
        position_size * price_diff
    } else {
        position_size * -price_diff
    }
}

/// Calculate required margin
fn calculate_margin(position_size: f64, entry_price: f64, leverage: f64) -> f64 {
    if leverage <= 0.0 {
        return position_size * entry_price;
    }
    (position_size * entry_price) / leverage
}

/// Calculate liquidation price for long position
fn calculate_liquidation_long(entry_price: f64, leverage: f64) -> f64 {
    if leverage <= 0.0 {
        return 0.0;
    }
    entry_price * (1.0 - 1.0 / leverage)
}

/// Calculate liquidation price for short position
fn calculate_liquidation_short(entry_price: f64, leverage: f64) -> f64 {
    if leverage <= 0.0 {
        return 0.0;
    }
    entry_price * (1.0 + 1.0 / leverage)
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(10_000))]

    /// Property: Position size is never negative
    #[test]
    fn test_position_size_non_negative(
        account_balance in 1000.0f64..1_000_000.0,
        risk_percent in 0.1f64..5.0,
        entry_price in 1.0f64..100000.0,
        stop_loss_price in 0.01f64..99999.0,
    ) {
        let size = calculate_position_size(account_balance, risk_percent, entry_price, stop_loss_price);
        assert!(size >= 0.0, "Position size should never be negative");
    }

    /// Property: Risk amount never exceeds account balance
    #[test]
    fn test_risk_within_balance(
        account_balance in 1000.0f64..1_000_000.0,
        risk_percent in 0.1f64..10.0,
        entry_price in 1.0f64..100000.0,
        stop_loss_price in 0.01f64..99999.0,
    ) {
        let size = calculate_position_size(account_balance, risk_percent, entry_price, stop_loss_price);
        let risk_amount = size * (entry_price - stop_loss_price).abs();

        // Allow small floating point error
        assert!(
            risk_amount <= account_balance * (risk_percent / 100.0) + 0.01,
            "Risk should not exceed intended amount"
        );
    }

    /// Property: Stop loss for long is below entry
    #[test]
    fn test_stop_loss_long_below_entry(
        entry_price in 1.0f64..100000.0,
        risk_percent in 0.1f64..50.0,
    ) {
        let stop_loss = calculate_stop_loss_long(entry_price, risk_percent);
        assert!(
            stop_loss < entry_price,
            "Long stop loss should be below entry price"
        );
    }

    /// Property: Stop loss for short is above entry
    #[test]
    fn test_stop_loss_short_above_entry(
        entry_price in 1.0f64..100000.0,
        risk_percent in 0.1f64..50.0,
    ) {
        let stop_loss = calculate_stop_loss_short(entry_price, risk_percent);
        assert!(
            stop_loss > entry_price,
            "Short stop loss should be above entry price"
        );
    }

    /// Property: Long PnL is positive when exit > entry
    #[test]
    fn test_long_pnl_positive(
        position_size in 0.1f64..100.0,
        entry_price in 1.0f64..100000.0,
    ) {
        let exit_price = entry_price * 1.1; // 10% higher
        let pnl = calculate_pnl(position_size, entry_price, exit_price, true);
        assert!(
            pnl > 0.0,
            "Long PnL should be positive when exit > entry"
        );
    }

    /// Property: Long PnL is negative when exit < entry
    #[test]
    fn test_long_pnl_negative(
        position_size in 0.1f64..100.0,
        entry_price in 1.0f64..100000.0,
    ) {
        let exit_price = entry_price * 0.9; // 10% lower
        let pnl = calculate_pnl(position_size, entry_price, exit_price, true);
        assert!(
            pnl < 0.0,
            "Long PnL should be negative when exit < entry"
        );
    }

    /// Property: Short PnL is positive when exit < entry
    #[test]
    fn test_short_pnl_positive(
        position_size in 0.1f64..100.0,
        entry_price in 1.0f64..100000.0,
    ) {
        let exit_price = entry_price * 0.9; // 10% lower
        let pnl = calculate_pnl(position_size, entry_price, exit_price, false);
        assert!(
            pnl > 0.0,
            "Short PnL should be positive when exit < entry"
        );
    }

    /// Property: Short PnL is negative when exit > entry
    #[test]
    fn test_short_pnl_negative(
        position_size in 0.1f64..100.0,
        entry_price in 1.0f64..100000.0,
    ) {
        let exit_price = entry_price * 1.1; // 10% higher
        let pnl = calculate_pnl(position_size, entry_price, exit_price, false);
        assert!(
            pnl < 0.0,
            "Short PnL should be negative when exit > entry"
        );
    }

    /// Property: PnL is zero when exit equals entry
    #[test]
    fn test_pnl_zero_at_entry(
        position_size in 0.1f64..100.0,
        entry_price in 1.0f64..100000.0,
    ) {
        let pnl_long = calculate_pnl(position_size, entry_price, entry_price, true);
        let pnl_short = calculate_pnl(position_size, entry_price, entry_price, false);

        assert!((pnl_long - 0.0).abs() < 0.0001, "Long PnL should be zero at entry");
        assert!((pnl_short - 0.0).abs() < 0.0001, "Short PnL should be zero at entry");
    }

    /// Property: Margin is always positive
    #[test]
    fn test_margin_non_negative(
        position_size in 0.1f64..1000.0,
        entry_price in 1.0f64..100000.0,
        leverage in 1.0f64..100.0,
    ) {
        let margin = calculate_margin(position_size, entry_price, leverage);
        assert!(margin >= 0.0, "Margin should never be negative");
    }

    /// Property: Higher leverage requires less margin
    #[test]
    fn test_higher_leverage_less_margin(
        position_size in 1.0f64..100.0,
        entry_price in 1000.0f64..100000.0,
    ) {
        let margin_1x = calculate_margin(position_size, entry_price, 1.0);
        let margin_10x = calculate_margin(position_size, entry_price, 10.0);
        let margin_100x = calculate_margin(position_size, entry_price, 100.0);

        assert!(
            margin_10x < margin_1x,
            "10x leverage should require less margin than 1x"
        );
        assert!(
            margin_100x < margin_10x,
            "100x leverage should require less margin than 10x"
        );
    }

    /// Property: Liquidation price is correct for long
    #[test]
    fn test_liquidation_long_calculation(
        entry_price in 1000.0f64..100000.0,
        leverage in 1.1f64..100.0,
    ) {
        let liq_price = calculate_liquidation_long(entry_price, leverage);
        let expected = entry_price * (1.0 - 1.0 / leverage);

        assert!(
            (liq_price - expected).abs() < 0.01,
            "Liquidation price calculation is incorrect"
        );
    }

    /// Property: Liquidation price is correct for short
    #[test]
    fn test_liquidation_short_calculation(
        entry_price in 1000.0f64..100000.0,
        leverage in 1.1f64..100.0,
    ) {
        let liq_price = calculate_liquidation_short(entry_price, leverage);
        let expected = entry_price * (1.0 + 1.0 / leverage);

        assert!(
            (liq_price - expected).abs() < 0.01,
            "Liquidation price calculation is incorrect"
        );
    }

    /// Property: Liquidation price is always on the losing side
    #[test]
    fn test_liquidation_on_losing_side(
        entry_price in 1000.0f64..100000.0,
        leverage in 2.0f64..50.0,
    ) {
        let liq_long = calculate_liquidation_long(entry_price, leverage);
        let liq_short = calculate_liquidation_short(entry_price, leverage);

        // Long liquidation should be below entry
        assert!(
            liq_long < entry_price,
            "Long liquidation should be below entry"
        );

        // Short liquidation should be above entry
        assert!(
            liq_short > entry_price,
            "Short liquidation should be above entry"
        );
    }

    /// Property: Position size scales linearly with account balance
    #[test]
    fn test_position_size_scales_with_balance(
        risk_percent in 1.0f64..5.0,
        entry_price in 1000.0f64..100000.0,
        stop_loss_price in 500.0f64..99000.0,
    ) {
        let balance1 = 10000.0;
        let balance2 = 50000.0; // 5x balance

        let size1 = calculate_position_size(balance1, risk_percent, entry_price, stop_loss_price);
        let size2 = calculate_position_size(balance2, risk_percent, entry_price, stop_loss_price);

        // Size should scale approximately 5x
        let ratio = size2 / size1;
        assert!(
            (ratio - 5.0).abs() < 0.01,
            "Position size should scale linearly with balance"
        );
    }

    /// Property: Risk percent doesn't affect position size ratio
    #[test]
    fn test_risk_percent_independent_ratio(
        account_balance in 10000.0f64..100000.0,
        entry_price in 1000.0f64..100000.0,
        stop_loss_price in 500.0f64..99000.0,
    ) {
        let size_1pct = calculate_position_size(account_balance, 1.0, entry_price, stop_loss_price);
        let size_2pct = calculate_position_size(account_balance, 2.0, entry_price, stop_loss_price);

        // 2% risk should give exactly 2x the position size of 1% risk
        let ratio = size_2pct / size_1pct;
        assert!(
            (ratio - 2.0).abs() < 0.01,
            "Position size should scale linearly with risk percent"
        );
    }
}
