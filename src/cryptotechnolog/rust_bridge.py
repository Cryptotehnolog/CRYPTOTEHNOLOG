# ==================== CRYPTOTEHNOLOG Rust Bridge ====================
# Graceful degradation for Python-Rust interop

import asyncio

# Try to import Rust extension
try:
    from cryptotechnolog_rust import (
        async_calculate_portfolio_risk,
        async_calculate_position_size,
        calculate_expected_return,
        calculate_portfolio_risk,
        calculate_position_size,
    )

    HAS_RUST = True
except ImportError:
    HAS_RUST = False

    # Python fallback implementations
    def calculate_position_size(
        equity: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """
        Calculate position size based on risk parameters (Python fallback).

        Args:
            equity: Total account equity
            risk_percent: Risk percentage per trade (e.g., 0.01 for 1%)
            entry_price: Entry price
            stop_loss: Stop loss price

        Returns:
            Position size in units

        Raises:
            ValueError: If price risk is zero
        """
        risk_amount = equity * risk_percent
        price_risk = abs(entry_price - stop_loss)

        if price_risk == 0.0:
            raise ValueError("Price risk cannot be zero")

        position_size = risk_amount / price_risk
        return position_size

    def calculate_portfolio_risk(
        positions: list[tuple[float, float, float]],  # (entry, stop, size)
    ) -> float:
        """
        Calculate portfolio risk based on positions (Python fallback).

        Args:
            positions: List of tuples (entry_price, stop_loss, size)

        Returns:
            Total portfolio risk in currency units
        """
        total_risk = 0.0
        for entry, stop, size in positions:
            risk_per_unit = abs(entry - stop)
            total_risk += risk_per_unit * size

        return total_risk

    def calculate_expected_return(
        win_rate: float,
        reward_risk_ratio: float,
        avg_risk: float,
    ) -> float:
        """
        Calculate expected return based on win rate and reward/risk ratio (Python fallback).

        Args:
            win_rate: Win rate (e.g., 0.6 for 60%)
            reward_risk_ratio: Reward to risk ratio (e.g., 2.0 for 2:1)
            avg_risk: Average risk per trade

        Returns:
            Expected return per trade
        """
        win_reward = win_rate * avg_risk * reward_risk_ratio
        loss_cost = (1.0 - win_rate) * avg_risk
        return win_reward - loss_cost

    async def async_calculate_position_size(
        equity: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """
        Calculate position size based on risk parameters (async Python fallback).

        Args:
            equity: Total account equity
            risk_percent: Risk percentage per trade
            entry_price: Entry price
            stop_loss: Stop loss price

        Returns:
            Position size in units

        Raises:
            ValueError: If price risk is zero
        """
        # Simulate async operation
        await asyncio.sleep(0)
        return calculate_position_size(equity, risk_percent, entry_price, stop_loss)

    async def async_calculate_portfolio_risk(
        positions: list[tuple[float, float, float]],  # (entry, stop, size)
    ) -> float:
        """
        Calculate portfolio risk based on positions (async Python fallback).

        Args:
            positions: List of tuples (entry_price, stop_loss, size)

        Returns:
            Total portfolio risk in currency units
        """
        # Simulate async operation
        await asyncio.sleep(0)
        return calculate_portfolio_risk(positions)


# ==================== Public API ====================
def get_rust_version() -> str | None:
    """
    Get the version of the Rust extension.

    Returns:
        Version string if Rust is available, None otherwise.
    """
    if HAS_RUST:
        try:
            import cryptotechnolog_rust  # noqa: PLC0415

            return cryptotechnolog_rust.__version__
        except Exception:
            return None
    return None


def is_rust_available() -> bool:
    """
    Check if Rust extension is available.

    Returns:
        True if Rust extension is available, False otherwise.
    """
    return HAS_RUST


# ==================== Main ====================
if __name__ == "__main__":
    # Test the bridge
    print(f"Rust available: {HAS_RUST}")
    print(f"Rust version: {get_rust_version()}")

    # Test position size calculation
    size = calculate_position_size(10000.0, 0.01, 100.0, 98.0)
    print(f"Position size: {size}")  # Expected: 50.0

    # Test portfolio risk calculation
    positions = [(100.0, 98.0, 50.0), (200.0, 195.0, 30.0)]
    risk = calculate_portfolio_risk(positions)
    print(f"Portfolio risk: {risk}")  # Expected: 250.0

    # Test expected return calculation
    expected = calculate_expected_return(0.6, 2.0, 100.0)
    print(f"Expected return: {expected}")  # Expected: 80.0

    # Test async functions
    async def test_async():
        size = await async_calculate_position_size(10000.0, 0.01, 100.0, 98.0)
        print(f"Async position size: {size}")  # Expected: 50.0

        risk = await async_calculate_portfolio_risk(positions)
        print(f"Async portfolio risk: {risk}")  # Expected: 250.0

    asyncio.run(test_async())
