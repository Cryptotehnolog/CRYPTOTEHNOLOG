# ==================== CRYPTOTEHNOLOG Data Frame Type Stubs ====================
# Type stubs for data frame utilities module

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Union

    import pandas as pd
    import polars as pl

    # Type aliases for better IDE support
    DataFrame = Union[pd.DataFrame, pl.DataFrame]
    Series = Union[pd.Series, pl.Series]
else:
    # Runtime type aliases
    DataFrame = Any
    Series = Any

# ==================== Conversion Functions ====================
def to_polars(df: DataFrame | Series) -> pl.DataFrame | pl.Series:
    """Convert DataFrame or Series to Polars."""
    ...

def to_pandas(df: DataFrame | Series) -> pd.DataFrame | pd.Series:
    """Convert DataFrame or Series to Pandas."""
    ...

# ==================== DataFrame Operations ====================
def read_csv(
    path: str,
    use_polars: bool = True,
    **kwargs: Any,
) -> pl.DataFrame | pd.DataFrame:
    """Read CSV file using Polars or Pandas."""
    ...

def read_parquet(
    path: str,
    use_polars: bool = True,
    **kwargs: Any,
) -> pl.DataFrame | pd.DataFrame:
    """Read Parquet file using Polars or Pandas."""
    ...

# ==================== Performance Utilities ====================
def benchmark_conversion(
    df: DataFrame,
    n_iterations: int = 10,
) -> dict[str, float]:
    """Benchmark conversion between Polars and Pandas."""
    ...

# ==================== Trading Data Utilities ====================
def _convert_timeframe_for_polars(timeframe: str) -> str:
    """Convert Pandas-style timeframe to Polars-style timeframe."""
    ...

def resample_ohlcv(
    df: DataFrame,
    timeframe: str,
    use_polars: bool = True,
) -> pl.DataFrame | pd.DataFrame:
    """Resample OHLCV data to a different timeframe."""
    ...

def calculate_returns(
    df: DataFrame,
    column: str = "close",
    use_polars: bool = True,
) -> pl.DataFrame | pd.DataFrame:
    """Calculate returns for a given column."""
    ...
