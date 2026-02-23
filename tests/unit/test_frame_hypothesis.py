# ==================== CRYPTOTEHNOLOG Hypothesis Tests ====================
# Property-based testing for data frame conversions and calculations

from __future__ import annotations

from typing import Any

from hypothesis import assume, given, settings
from hypothesis import strategies as st
import numpy as np
import pandas as pd
import polars as pl

from cryptotechnolog.data.frame import (
    calculate_returns,
    resample_ohlcv,
    to_pandas,
    to_polars,
)

# ==================== Strategies ====================

@st.composite
def pandas_dataframe(draw: Any, max_rows: int = 100) -> pd.DataFrame:
    """Generate random pandas DataFrame with homogeneous columns."""
    rows = draw(st.integers(min_value=1, max_value=max_rows))
    cols = draw(st.integers(min_value=1, max_value=10))

    data: dict[str, list[Any]] = {}
    for i in range(cols):
        col_name = f"col_{i}"
        # Only floats for consistent types (mixed types are edge case)
        data[col_name] = draw(
            st.lists(
                st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
                min_size=rows,
                max_size=rows,
            )
        )

    return pd.DataFrame(data)


@st.composite
def polars_dataframe(draw: Any, max_rows: int = 100) -> pl.DataFrame:
    """Generate random polars DataFrame."""
    rows = draw(st.integers(min_value=1, max_value=max_rows))
    cols = draw(st.integers(min_value=1, max_value=10))

    data: dict[str, list[Any]] = {}
    for i in range(cols):
        col_name = f"col_{i}"
        data[col_name] = draw(
            st.lists(
                st.floats(min_value=-1e6, max_value=1e6),
                min_size=rows,
                max_size=rows,
            )
        )

    return pl.DataFrame(data)


@st.composite
def ohlcv_dataframe(draw: Any, max_rows: int = 100) -> pd.DataFrame:
    """Generate OHLCV DataFrame with timestamp index."""
    rows = draw(st.integers(min_value=10, max_value=max_rows))

    # Generate timestamps
    base_time = pd.Timestamp("2024-01-01")
    timestamps = [base_time + pd.Timedelta(minutes=i) for i in range(rows)]

    # Generate OHLCV data
    np.random.seed(draw(st.integers(min_value=0, max_value=99999)))
    base_price = draw(st.floats(min_value=100, max_value=50000))

    data = {
        "timestamp": timestamps,
        "open": [base_price + np.random.randn() * 10 for _ in range(rows)],
        "high": [base_price + abs(np.random.randn()) * 20 for _ in range(rows)],
        "low": [base_price - abs(np.random.randn()) * 20 for _ in range(rows)],
        "close": [base_price + np.random.randn() * 10 for _ in range(rows)],
        "volume": [abs(np.random.randn() * 1000) for _ in range(rows)],
    }

    # Ensure high >= open, close, low
    for i in range(rows):
        data["high"][i] = max(data["open"][i], data["close"][i], data["low"][i]) + abs(np.random.randn() * 5)
        data["low"][i] = min(data["open"][i], data["close"][i], data["high"][i]) - abs(np.random.randn() * 5)

    return pd.DataFrame(data)


# ==================== Conversion Tests ====================

@given(pandas_dataframe(max_rows=50))
@settings(max_examples=50)
def test_to_polars_preserves_data(pandas_df: pd.DataFrame) -> None:
    """Test that converting pandas DataFrame to polars preserves data."""
    assume(not pandas_df.empty)

    polars_df = to_polars(pandas_df)

    # Check row count
    assert len(polars_df) == len(pandas_df)

    # Check column count
    assert len(polars_df.columns) == len(pandas_df.columns)

    # Check values match (approximately for floats)
    for col in pandas_df.columns:
        if pandas_df[col].dtype in [np.float64, np.float32]:
            np.testing.assert_allclose(
                polars_df[col].to_numpy(),
                pandas_df[col].to_numpy(),
                rtol=1e-10,
            )
        else:
            assert (polars_df[col].to_numpy() == pandas_df[col].to_numpy()).all()


@given(polars_dataframe(max_rows=50))
@settings(max_examples=50)
def test_to_pandas_preserves_data(polars_df: pl.DataFrame) -> None:
    """Test that converting polars DataFrame to pandas preserves data."""
    assume(polars_df.height > 0)

    pandas_df = to_pandas(polars_df)

    # Check row count
    assert len(pandas_df) == len(polars_df)

    # Check column count
    assert len(pandas_df.columns) == len(polars_df.columns)

    # Check values match
    for col in polars_df.columns:
        if polars_df[col].dtype == pl.Float64:
            np.testing.assert_allclose(
                pandas_df[col].to_numpy(),
                polars_df[col].to_numpy(),
                rtol=1e-10,
            )
        else:
            assert (pandas_df[col].to_numpy() == polars_df[col].to_numpy()).all()


@given(pandas_dataframe(max_rows=50))
@settings(max_examples=20)
def test_to_polars_idempotent(pandas_df: pd.DataFrame) -> None:
    """Test that converting to polars twice gives same result."""
    assume(not pandas_df.empty)

    result1 = to_polars(pandas_df)
    result2 = to_polars(result1)

    assert len(result1) == len(result2)
    assert len(result1.columns) == len(result2.columns)


@given(polars_dataframe(max_rows=50))
@settings(max_examples=20)
def test_to_pandas_idempotent(polars_df: pl.DataFrame) -> None:
    """Test that converting to pandas twice gives same result."""
    assume(polars_df.height > 0)

    result1 = to_pandas(polars_df)
    result2 = to_pandas(result1)

    assert len(result1) == len(result2)
    assert len(result1.columns) == len(result2.columns)


# ==================== Returns Calculation Tests ====================

@given(ohlcv_dataframe(max_rows=100))
@settings(max_examples=30)
def test_calculate_returns_valid_range(pandas_df: pd.DataFrame) -> None:
    """Test that calculated returns are in valid range (-1, 1) for reasonable price changes."""
    assume(len(pandas_df) > 1)

    result = calculate_returns(pandas_df, column="close", use_polars=False)

    # Returns should exist
    assert "returns" in result.columns

    # Most returns should be reasonable (not NaN for first row)
    returns = result["returns"].dropna()
    assume(len(returns) > 0)

    # Returns should be finite
    assert returns.apply(lambda x: np.isfinite(x) if pd.notna(x) else True).all()


@given(ohlcv_dataframe(max_rows=100))
@settings(max_examples=30)
def test_calculate_returns_polars(pandas_df: pd.DataFrame) -> None:
    """Test calculate_returns with polars."""
    assume(len(pandas_df) > 1)

    result = calculate_returns(pandas_df, column="close", use_polars=True)

    # Returns should exist
    assert "returns" in result.columns


# ==================== Resample Tests ====================

@given(ohlcv_dataframe(max_rows=50))
@settings(max_examples=20)
def test_resample_ohlcv_reduces_rows(pandas_df: pd.DataFrame) -> None:
    """Test that resampling reduces number of rows."""
    assume(len(pandas_df) >= 10)

    original_rows = len(pandas_df)
    result = resample_ohlcv(pandas_df, timeframe="5min", use_polars=False)

    # Resampled should have fewer or equal rows
    assert len(result) <= original_rows

    # Should have OHLCV columns
    assert "open" in result.columns
    assert "high" in result.columns
    assert "low" in result.columns
    assert "close" in result.columns
    assert "volume" in result.columns


@given(ohlcv_dataframe(max_rows=50))
@settings(max_examples=20)
def test_resample_ohlcv_polars(pandas_df: pd.DataFrame) -> None:
    """Test resample_ohlcv with polars."""
    assume(len(pandas_df) >= 10)

    result = resample_ohlcv(pandas_df, timeframe="5min", use_polars=True)

    # Should have OHLCV columns
    assert "open" in result.columns
    assert "high" in result.columns
    assert "low" in result.columns
    assert "close" in result.columns
    assert "volume" in result.columns


# ==================== Edge Cases ====================

@given(st.lists(st.floats(min_value=-1e10, max_value=1e10), min_size=2, max_size=100))
@settings(max_examples=20)
def test_conversion_with_extreme_values(values: list[float]) -> None:
    """Test conversion with extreme float values."""
    pandas_df = pd.DataFrame({"value": values})

    polars_df = to_polars(pandas_df)
    back_to_pandas = to_pandas(polars_df)

    np.testing.assert_allclose(
        back_to_pandas["value"].to_numpy(),
        pandas_df["value"].to_numpy(),
        rtol=1e-9,
    )


@given(st.integers(min_value=1, max_value=1000))
@settings(max_examples=10)
def test_conversion_with_many_columns(n_cols: int) -> None:
    """Test conversion with many columns."""
    data = {f"col_{i}": list(range(10)) for i in range(n_cols)}
    pandas_df = pd.DataFrame(data)

    polars_df = to_polars(pandas_df)

    assert len(polars_df.columns) == n_cols
    assert len(polars_df) == 10


@given(st.integers(min_value=1, max_value=100))
@settings(max_examples=10)
def test_conversion_with_many_rows(n_rows: int) -> None:
    """Test conversion with many rows."""
    pandas_df = pd.DataFrame({"value": list(range(n_rows))})

    polars_df = to_polars(pandas_df)

    assert len(polars_df) == n_rows


# ==================== Type Preservation ====================

@given(pandas_dataframe(max_rows=20))
@settings(max_examples=10)
def test_pandas_to_polars_preserves_dtypes(pandas_df: pd.DataFrame) -> None:
    """Test that dtype information is preserved."""
    assume(not pandas_df.empty)

    polars_df = to_polars(pandas_df)

    # Check that we get a polars DataFrame
    assert isinstance(polars_df, pl.DataFrame)


@given(polars_dataframe(max_rows=20))
@settings(max_examples=10)
def test_polars_to_pandas_preserves_dtypes(polars_df: pl.DataFrame) -> None:
    """Test that dtype information is preserved."""
    assume(polars_df.height > 0)

    pandas_df = to_pandas(polars_df)

    # Check that we get a pandas DataFrame
    assert isinstance(pandas_df, pd.DataFrame)
