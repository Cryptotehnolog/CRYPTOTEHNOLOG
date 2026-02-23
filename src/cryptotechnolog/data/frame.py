# ==================== CRYPTOTEHNOLOG Data Frame Utilities ====================
# Polars and Pandas compatibility layer for gradual migration

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any, TypeAlias

import pandas as pd
import polars as pl

if TYPE_CHECKING:
    from pandas import DataFrame as PdDataFrame
    from pandas import Series as PdSeries
    from polars import DataFrame as PlDataFrame
    from polars import Series as PlSeries

# Type alias for dataframes
DataFrame: TypeAlias = pd.DataFrame | pl.DataFrame
Series: TypeAlias = pd.Series | pl.Series


# ==================== Conversion Functions ====================
def to_polars(df: DataFrame | Series) -> pl.DataFrame | pl.Series:
    """
    Convert DataFrame or Series to Polars.

    Args:
        df: DataFrame or Series (Pandas or Polars).

    Returns:
        Polars DataFrame or Series.

    Raises:
        TypeError: If input is not a DataFrame or Series.
    """
    if isinstance(df, (pl.DataFrame, pl.Series)):
        return df
    if isinstance(df, (pd.DataFrame, pd.Series)):
        return pl.from_pandas(df)
    raise TypeError(f"Expected DataFrame or Series, got {type(df)}")


def to_pandas(df: DataFrame | Series) -> pd.DataFrame | pd.Series:
    """
    Convert DataFrame or Series to Pandas.

    Args:
        df: DataFrame or Series (Pandas or Polars).

    Returns:
        Pandas DataFrame or Series.

    Raises:
        TypeError: If input is not a DataFrame or Series.
    """
    if isinstance(df, (pd.DataFrame, pd.Series)):
        return df
    if isinstance(df, (pl.DataFrame, pl.Series)):
        return df.to_pandas()
    raise TypeError(f"Expected DataFrame or Series, got {type(df)}")


# ==================== DataFrame Operations ====================
def read_csv(
    path: str,
    use_polars: bool = True,
    **kwargs: Any,
) -> pl.DataFrame | pd.DataFrame:
    """
    Read CSV file using Polars or Pandas.

    Args:
        path: Path to CSV file.
        use_polars: If True, use Polars (default). If False, use Pandas.
        **kwargs: Additional arguments passed to the CSV reader.

    Returns:
        DataFrame (Polars or Pandas).
    """
    if use_polars:
        return pl.read_csv(path, **kwargs)
    return pd.read_csv(path, **kwargs)


def read_parquet(
    path: str,
    use_polars: bool = True,
    **kwargs: Any,
) -> pl.DataFrame | pd.DataFrame:
    """
    Read Parquet file using Polars or Pandas.

    Args:
        path: Path to Parquet file.
        use_polars: If True, use Polars (default). If False, use Pandas.
        **kwargs: Additional arguments passed to the Parquet reader.

    Returns:
        DataFrame (Polars or Pandas).
    """
    if use_polars:
        return pl.read_parquet(path, **kwargs)
    return pd.read_parquet(path, **kwargs)


# ==================== Performance Utilities ====================
def benchmark_conversion(
    df: DataFrame,
    n_iterations: int = 10,
) -> dict[str, float]:
    """
    Benchmark conversion between Polars and Pandas.

    Args:
        df: DataFrame to convert.
        n_iterations: Number of iterations for benchmarking.

    Returns:
        Dictionary with benchmark results (mean times in seconds).
    """
    results: dict[str, list[float]] = {"to_polars": [], "to_pandas": []}

    for _ in range(n_iterations):
        # Pandas -> Polars
        if isinstance(df, pd.DataFrame):
            start = time.time()
            to_polars(df)
            results["to_polars"].append(time.time() - start)

        # Polars -> Pandas
        if isinstance(df, pl.DataFrame):
            start = time.time()
            to_pandas(df)
            results["to_pandas"].append(time.time() - start)

    # Calculate means
    return {key: (sum(values) / len(values) if values else 0.0) for key, values in results.items()}


# ==================== Trading Data Utilities ====================
def _convert_timeframe_for_polars(timeframe: str) -> str:
    """
    Convert Pandas-style timeframe to Polars-style timeframe.

    Pandas uses: '1min', '5min', '1H', '1D'
    Polars uses: '1m', '5m', '1h', '1d'

    Args:
        timeframe: Pandas-style timeframe string.

    Returns:
        Polars-style timeframe string.
    """
    # Map common Pandas formats to Polars formats
    conversion_map = {
        "min": "m",  # minutes
        "H": "h",  # hours
        "D": "d",  # days
        "W": "w",  # weeks
        "M": "mo",  # months
        "Y": "y",  # years
    }

    # Check if it's a number followed by unit (e.g., "5min", "1H")
    match = re.match(r"^(\d+)([a-zA-Z]+)$", timeframe)
    if match:
        number = match.group(1)
        unit = match.group(2)

        # Convert unit if needed
        polars_unit = conversion_map.get(unit, unit.lower())
        return f"{number}{polars_unit}"

    # Return as-is if no conversion needed
    return timeframe


def resample_ohlcv(
    df: DataFrame,
    timeframe: str,
    use_polars: bool = True,
) -> pl.DataFrame | pd.DataFrame:
    """
    Resample OHLCV data to a different timeframe.

    Args:
        df: DataFrame with OHLCV data (columns: timestamp, open, high, low, close, volume).
        timeframe: Target timeframe (e.g., '1m', '5m', '1h', '1d', '1min', '1H', '1D').
        use_polars: If True, use Polars (default). If False, use Pandas.

    Returns:
        Resampled DataFrame.
    """
    if use_polars:
        # Convert timeframe to Polars format
        polars_timeframe = _convert_timeframe_for_polars(timeframe)

        pl_df = to_polars(df)
        # Cast to DataFrame to satisfy mypy (Series can't be resampled)
        if isinstance(pl_df, pl.Series):
            raise TypeError("Cannot resample Series, use DataFrame")
        return pl_df.group_by_dynamic(
            pl.col("timestamp").alias("time"),
            every=polars_timeframe,
        ).agg(
            [
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
            ]
        )
    else:
        pd_df = to_pandas(df)
        df_typed = pd_df.set_index("timestamp")
        resampled: pd.DataFrame = df_typed.resample(timeframe).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        return resampled.reset_index()


def calculate_returns(
    df: DataFrame,
    column: str = "close",
    use_polars: bool = True,
) -> pl.DataFrame | pd.DataFrame:
    """
    Calculate returns for a given column.

    Args:
        df: DataFrame with price data.
        column: Column name to calculate returns for (default: 'close').
        use_polars: If True, use Polars (default). If False, use Pandas.

    Returns:
        DataFrame with returns column added.
    """
    if use_polars:
        pl_df = to_polars(df)
        # Cast to DataFrame to satisfy mypy (Series can't have with_columns)
        if isinstance(pl_df, pl.Series):
            raise TypeError("Cannot calculate returns on Series, use DataFrame")
        return pl_df.with_columns((pl.col(column) / pl.col(column).shift(1) - 1).alias("returns"))
    else:
        pd_df = to_pandas(df)
        # Ensure we have a DataFrame, not a Series
        if isinstance(pd_df, pd.Series):
            raise TypeError("Cannot calculate returns on Series, use DataFrame")
        pd_df["returns"] = pd_df[column].pct_change()
        return pd_df


# ==================== Main ====================
if __name__ == "__main__":
    # Test conversion functions
    pd_df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    pl_df = to_polars(pd_df)
    print("Polars DataFrame:")
    print(pl_df)

    back_to_pd = to_pandas(pl_df)
    print("\nBack to Pandas:")
    print(back_to_pd)

    # Test benchmark
    results = benchmark_conversion(pd_df, n_iterations=5)
    print("\nBenchmark results:")
    for key, value in results.items():
        print(f"  {key}: {value:.6f}s")
