# ==================== CRYPTOTEHNOLOG Rust Bridge Tests ====================
# Tests for Python-Rust interop with graceful degradation

import pytest

from cryptotechnolog.rust_bridge import (
    async_calculate_portfolio_risk,  # type: ignore
    async_calculate_position_size,  # type: ignore
    calculate_expected_return,  # type: ignore
    calculate_portfolio_risk,  # type: ignore
    calculate_position_size,  # type: ignore
    get_rust_version,
    is_rust_available,
)


class TestRustBridge:
    """Test suite for Rust bridge functionality."""

    def test_rust_availability(self):
        """Test that we can check if Rust is available."""
        available = is_rust_available()
        assert isinstance(available, bool)

    def test_get_rust_version(self):
        """Test that we can get Rust version."""
        version = get_rust_version()
        if is_rust_available():
            assert version is not None
            assert isinstance(version, str)
        else:
            assert version is None

    def test_calculate_position_size(self):
        """Test position size calculation."""
        # Test case 1: Normal calculation
        size = calculate_position_size(10000.0, 0.01, 100.0, 98.0)
        assert size == 50.0

        # Test case 2: Different values
        size = calculate_position_size(20000.0, 0.02, 50.0, 48.0)
        assert size == 200.0

        # Test case 3: Zero risk should raise error
        with pytest.raises(ValueError):
            calculate_position_size(10000.0, 0.01, 100.0, 100.0)

    def test_calculate_portfolio_risk(self):
        """Test portfolio risk calculation."""
        # Test case 1: Single position
        positions = [(100.0, 98.0, 50.0)]
        risk = calculate_portfolio_risk(positions)
        assert risk == 100.0

        # Test case 2: Multiple positions
        positions = [(100.0, 98.0, 50.0), (200.0, 195.0, 30.0)]
        risk = calculate_portfolio_risk(positions)
        assert risk == 250.0

        # Test case 3: Empty positions
        positions = []
        risk = calculate_portfolio_risk(positions)
        assert risk == 0.0

    def test_calculate_expected_return(self):
        """Test expected return calculation."""
        # Test case 1: Positive expected return
        expected = calculate_expected_return(0.6, 2.0, 100.0)
        assert expected == 80.0

        # Test case 2: Different win rate
        expected = calculate_expected_return(0.5, 2.0, 100.0)
        assert expected == 50.0

        # Test case 3: Negative expected return
        expected = calculate_expected_return(0.4, 1.5, 100.0)
        assert expected == 0.0  # (0.4 * 1.5 * 100) - (0.6 * 100) = 60 - 60 = 0

    @pytest.mark.asyncio
    async def test_async_calculate_position_size(self):
        """Test async position size calculation."""
        size = await async_calculate_position_size(10000.0, 0.01, 100.0, 98.0)
        assert size == 50.0

    @pytest.mark.asyncio
    async def test_async_calculate_portfolio_risk(self):
        """Test async portfolio risk calculation."""
        positions = [(100.0, 98.0, 50.0), (200.0, 195.0, 30.0)]
        risk = await async_calculate_portfolio_risk(positions)
        assert risk == 250.0

    def test_calculate_position_size_large_values(self):
        """Test position size with large values."""
        size = calculate_position_size(1_000_000.0, 0.01, 1000.0, 990.0)
        assert size == 1000.0

    def test_calculate_portfolio_risk_many_positions(self):
        """Test portfolio risk with many positions."""
        positions = [(100.0 + i, 98.0 + i, 10.0) for i in range(100)]
        risk = calculate_portfolio_risk(positions)
        assert risk == 2000.0

    def test_calculate_expected_return_edge_cases(self):
        """Test expected return with edge cases."""
        # Zero win rate
        expected = calculate_expected_return(0.0, 2.0, 100.0)
        assert expected == -100.0

        # 100% win rate
        expected = calculate_expected_return(1.0, 2.0, 100.0)
        assert expected == 200.0

        # Zero reward/risk ratio
        expected = calculate_expected_return(0.5, 0.0, 100.0)
        assert expected == -50.0
