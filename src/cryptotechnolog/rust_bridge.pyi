# ==================== CRYPTOTEHNOLOG Rust Bridge Type Stubs ====================
# Type stubs for Python-Rust interop module

from __future__ import annotations

# ==================== Public Functions ====================
def get_rust_version() -> str | None:
    """Get the version of the Rust extension."""
    ...

def is_rust_available() -> bool:
    """Check if Rust extension is available."""
    ...

def calculate_position_size(
    equity: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
) -> float:
    """Calculate position size based on risk parameters."""
    ...

def calculate_portfolio_risk(
    positions: list[tuple[float, float, float]],
) -> float:
    """Calculate portfolio risk based on positions."""
    ...

def calculate_expected_return(
    win_rate: float,
    reward_risk_ratio: float,
    avg_risk: float,
) -> float:
    """Calculate expected return based on win rate and reward/risk ratio."""
    ...

async def async_calculate_position_size(
    equity: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
) -> float:
    """Calculate position size (async version)."""
    ...

async def async_calculate_portfolio_risk(
    positions: list[tuple[float, float, float]],
) -> float:
    """Calculate portfolio risk (async version)."""
    ...

# ==================== Module Variables ====================
HAS_RUST: bool
