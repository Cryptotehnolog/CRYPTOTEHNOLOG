# ruff: noqa: E402
# ==================== Tests: Data Frame Utilities ====================

# Diagnostic output to understand import order and sys.path
import sys

print("[test_data_frame] Module loading started")
print(f"[test_data_frame] sys.path[0:3] = {sys.path[:3]}")
print(f"[test_data_frame] cryptotechnolog in sys.modules = {'cryptotechnolog' in sys.modules}")

# Try to import cryptotechnolog.data FIRST
try:
    from cryptotechnolog.data import (
        benchmark_conversion,
        calculate_returns,
        resample_ohlcv,
        to_pandas,
        to_polars,
    )
    print("[test_data_frame] Successfully imported cryptotechnolog.data")
except ImportError as e:
    print(f"[test_data_frame] FAILED to import cryptotechnolog.data: {e}")
    print(f"[test_data_frame] cryptotechnolog in sys.modules: {'cryptotechnolog' in sys.modules}")
    if 'cryptotechnolog' in sys.modules:
        print(f"[test_data_frame] cryptotechnolog.__file__: {getattr(sys.modules['cryptotechnolog'], '__file__', 'NO FILE')}")
        print(f"[test_data_frame] cryptotechnolog.__path__: {getattr(sys.modules['cryptotechnolog'], '__path__', 'NO PATH')}")
    raise

import pandas as pd
import polars as pl
import pytest

print("[test_data_frame] All imports completed")


class TestConversion:
    """Test DataFrame conversion functions."""

    def test_pandas_to_polars(self) -> None:
        """Test converting Pandas DataFrame to Polars."""
        pd_df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        pl_df = to_polars(pd_df)

        assert isinstance(pl_df, pl.DataFrame)
        assert pl_df.shape == (3, 2)
        assert list(pl_df.columns) == ["a", "b"]

    def test_polars_to_pandas(self) -> None:
        """Test converting Polars DataFrame to Pandas."""
        pl_df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        pd_df = to_pandas(pl_df)

        assert isinstance(pd_df, pd.DataFrame)
        assert pd_df.shape == (3, 2)
        assert list(pd_df.columns) == ["a", "b"]

    def test_polars_to_polars(self) -> None:
        """Test that Polars DataFrame is returned as-is."""
        pl_df = pl.DataFrame({"a": [1, 2, 3]})
        result = to_polars(pl_df)

        assert result is pl_df

    def test_pandas_to_pandas(self) -> None:
        """Test that Pandas DataFrame is returned as-is."""
        pd_df = pd.DataFrame({"a": [1, 2, 3]})
        result = to_pandas(pd_df)

        assert result is pd_df

    def test_invalid_type_to_polars(self) -> None:
        """Test that invalid type raises TypeError."""
        with pytest.raises(TypeError):
            to_polars("not a dataframe")  # type: ignore[arg-type]

    def test_invalid_type_to_pandas(self) -> None:
        """Test that invalid type raises TypeError."""
        with pytest.raises(TypeError):
            to_pandas("not a dataframe")  # type: ignore[arg-type]


class TestCalculateReturns:
    """Test returns calculation."""

    def test_calculate_returns_polars(self) -> None:
        """Test calculating returns with Polars."""
        pd_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3),
                "close": [100.0, 105.0, 110.0],
            }
        )

        result = calculate_returns(pd_df, use_polars=True)

        assert isinstance(result, pl.DataFrame)
        assert "returns" in result.columns
        # Returns should be: [NaN, 0.05, 0.0476...]
        assert result["returns"][1] == pytest.approx(0.05, rel=1e-3)

    def test_calculate_returns_pandas(self) -> None:
        """Test calculating returns with Pandas."""
        pd_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3),
                "close": [100.0, 105.0, 110.0],
            }
        )

        result = calculate_returns(pd_df, use_polars=False)

        assert isinstance(result, pd.DataFrame)
        assert "returns" in result.columns
        assert result["returns"].iloc[1] == pytest.approx(0.05, rel=1e-3)

    def test_calculate_returns_series_error(self) -> None:
        """Test that Series raises TypeError."""
        series = pd.Series([1, 2, 3])

        with pytest.raises(TypeError, match="Cannot calculate returns on Series"):
            calculate_returns(series, use_polars=False)  # type: ignore[arg-type]


class TestResampleOHLCV:
    """Test OHLCV resampling."""

    def test_resample_ohlcv_polars(self) -> None:
        """Test resampling with Polars."""
        pd_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=4, freq="1min"),
                "open": [100.0, 101.0, 102.0, 103.0],
                "high": [101.0, 102.0, 103.0, 104.0],
                "low": [99.0, 100.0, 101.0, 102.0],
                "close": [101.0, 102.0, 103.0, 104.0],
                "volume": [10, 20, 30, 40],
            }
        )

        result = resample_ohlcv(pd_df, "2m", use_polars=True)

        assert isinstance(result, pl.DataFrame)
        assert result.shape == (2, 6)  # 2 rows (4min / 2min), 6 columns

    def test_resample_ohlcv_pandas(self) -> None:
        """Test resampling with Pandas."""
        pd_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=4, freq="1min"),
                "open": [100.0, 101.0, 102.0, 103.0],
                "high": [101.0, 102.0, 103.0, 104.0],
                "low": [99.0, 100.0, 101.0, 102.0],
                "close": [101.0, 102.0, 103.0, 104.0],
                "volume": [10, 20, 30, 40],
            }
        )

        result = resample_ohlcv(pd_df, "2min", use_polars=False)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (2, 6)


class TestBenchmark:
    """Test benchmarking functions."""

    def test_benchmark_conversion(self) -> None:
        """Test benchmarking conversion."""
        # Use larger Polars DataFrame for more reliable benchmarking
        pl_df = pl.DataFrame({"a": list(range(1000)), "b": list(range(1000))})

        results = benchmark_conversion(pl_df, n_iterations=10)

        assert "to_polars" in results
        assert "to_pandas" in results
        assert results["to_polars"] >= 0  # May be 0 if already Polars
        assert results["to_pandas"] >= 0  # May be 0 for very fast conversions
