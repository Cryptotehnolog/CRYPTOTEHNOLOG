# ==================== CRYPTOTEHNOLOG Data Layer Integration Tests ====================
# Integration tests for data layer components
#
# These tests verify that:
# 1. Polars/Pandas conversion works correctly
# 2. Data frame utilities function properly
# 3. Trading data operations work as expected

from __future__ import annotations

from datetime import datetime
import math

import pandas as pd
import polars as pl
import pytest

from cryptotechnolog.data.frame import (
    benchmark_conversion,
    calculate_returns,
    resample_ohlcv,
    to_pandas,
    to_polars,
)


class TestDataFrameConversion:
    """Test suite for DataFrame conversion utilities."""

    def test_to_polars_from_pandas(self):
        """Test converting Pandas DataFrame to Polars."""
        pd_df = pd.DataFrame({
            "a": [1, 2, 3],
            "b": [4.0, 5.0, 6.0],
            "c": ["x", "y", "z"],
        })

        pl_df = to_polars(pd_df)

        # Verify it's a Polars DataFrame
        assert pl_df.shape == (3, 3)  # type: ignore
        assert list(pl_df.columns) == ["a", "b", "c"]  # type: ignore

    def test_to_pandas_from_polars(self):
        """Test converting Polars DataFrame to Pandas."""
        pl_df = pl.DataFrame({
            "a": [1, 2, 3],
            "b": [4.0, 5.0, 6.0],
            "c": ["x", "y", "z"],
        })

        pd_df = to_pandas(pl_df)

        # Verify it's a Pandas DataFrame
        assert pd_df.shape == (3, 3)  # type: ignore
        assert list(pd_df.columns) == ["a", "b", "c"]  # type: ignore

    def test_to_polars_passthrough(self):
        """Test that Polars DataFrame passes through unchanged."""
        pl_df = pl.DataFrame({"a": [1, 2, 3]})
        result = to_polars(pl_df)

        # Should be the same object
        assert result is pl_df

    def test_to_pandas_passthrough(self):
        """Test that Pandas DataFrame passes through unchanged."""
        pd_df = pd.DataFrame({"a": [1, 2, 3]})
        result = to_pandas(pd_df)

        # Should be the same object
        assert result is pd_df

    def test_invalid_type_raises_error(self):
        """Test that invalid type raises TypeError."""
        with pytest.raises(TypeError):
            to_polars([1, 2, 3])  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            to_pandas([1, 2, 3])  # type: ignore[arg-type]


class TestTradingDataOperations:
    """Test suite for trading data operations."""

    def test_calculate_returns_pandas(self):
        """Test calculating returns with Pandas."""
        pd_df = pd.DataFrame({
            "close": [100.0, 101.0, 102.0, 101.5],
        })

        result = calculate_returns(pd_df, column="close", use_polars=False)

        # Check returns are calculated
        assert "returns" in result.columns  # type: ignore
        # First return should be NaN
        assert math.isnan(result["returns"].iloc[0])  # type: ignore
        # Second return: (101 - 100) / 100 = 0.01
        assert abs(float(result["returns"].iloc[1]) - 0.01) < 1e-6  # type: ignore

    def test_calculate_returns_polars(self):
        """Test calculating returns with Polars."""
        pl_df = pl.DataFrame({
            "close": [100.0, 101.0, 102.0, 101.5],
        })

        result = calculate_returns(pl_df, column="close", use_polars=True)

        # Check returns are calculated
        assert "returns" in result.columns  # type: ignore
        # Second return: (101 - 100) / 100 = 0.01
        assert abs(float(result["returns"][1]) - 0.01) < 1e-6  # type: ignore

    def test_resample_ohlcv_pandas(self):
        """Test resampling OHLCV data with Pandas."""
        pd_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="1min"),
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "volume": [10.0] * 10,
        })

        result = resample_ohlcv(pd_df, timeframe="5min", use_polars=False)

        # Should have 2 rows (10 minutes / 5 minutes = 2)
        assert len(result) == 2  # type: ignore
        assert all(col in result.columns for col in ["open", "high", "low", "close", "volume"])  # type: ignore[attr-defined]

    def test_resample_ohlcv_polars(self):
        """Test resampling OHLCV data with Polars."""
        # Create timestamps manually using datetime objects
        timestamps = [datetime(2024, 1, 1, 0, i) for i in range(10)]

        pl_df = pl.DataFrame({
            "timestamp": timestamps,
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "volume": [10.0] * 10,
        })

        result = resample_ohlcv(pl_df, timeframe="5min", use_polars=True)

        # Should have 2 rows
        assert len(result) == 2  # type: ignore
        assert "open" in result.columns  # type: ignore[attr-defined]


class TestBenchmarking:
    """Test suite for benchmarking utilities."""

    def test_benchmark_conversion_pandas(self):
        """Test benchmarking Pandas to Polars conversion."""
        pd_df = pd.DataFrame({
            "a": list(range(100)),
            "b": list(range(100, 200)),
        })

        results = benchmark_conversion(pd_df, n_iterations=3)

        assert "to_polars" in results
        assert results["to_polars"] >= 0.0  # type: ignore

    def test_benchmark_conversion_polars(self):
        """Test benchmarking Polars to Pandas conversion."""
        pl_df = pl.DataFrame({
            "a": list(range(100)),
            "b": list(range(100, 200)),
        })

        results = benchmark_conversion(pl_df, n_iterations=3)

        assert "to_pandas" in results
        assert results["to_pandas"] >= 0.0  # type: ignore


class TestDataConsistency:
    """Test suite for data consistency across conversions."""

    def test_roundtrip_pandas_polars_pandas(self):
        """Test that data survives roundtrip conversion."""
        original = pd.DataFrame({
            "a": [1, 2, 3],
            "b": [4.0, 5.0, 6.0],
            "c": ["x", "y", "z"],
        })

        # Pandas -> Polars -> Pandas
        pl_df = to_polars(original)
        result = to_pandas(pl_df)

        # Check data is preserved
        assert result.shape == original.shape  # type: ignore
        assert list(result.columns) == list(original.columns)  # type: ignore
        assert list(result["a"].tolist()) == list(original["a"].tolist())  # type: ignore[attr-defined]

    def test_roundtrip_polars_pandas_polars(self):
        """Test that data survives roundtrip conversion."""
        original = pl.DataFrame({
            "a": [1, 2, 3],
            "b": [4.0, 5.0, 6.0],
            "c": ["x", "y", "z"],
        })

        # Polars -> Pandas -> Polars
        pd_df = to_pandas(original)
        result = to_polars(pd_df)

        # Check data is preserved
        assert result.shape == original.shape  # type: ignore
        assert list(result.columns) == list(original.columns)  # type: ignore
        assert result["a"].to_list() == original["a"].to_list()  # type: ignore[attr-defined]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
