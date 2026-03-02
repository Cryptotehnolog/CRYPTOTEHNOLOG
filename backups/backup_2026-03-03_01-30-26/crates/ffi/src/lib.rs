// ==================== CRYPTOTEHNOLOG Python FFI Crate ====================
// Python bindings using PyO3 for high-performance interop
//
// This crate provides Python bindings for high-performance Rust components.
//
// Features:
// - PyO3 bindings for high-performance components
// - Zero-copy data transfer between Python and Rust
// - Async function support via pyo3-async-runtimes
// - Position size calculations
// - Portfolio risk calculations
//
// Performance targets:
// - Zero-copy operations
// - Sub-millisecond call overhead
// - Seamless Python integration
//
// This is compiled with maturin and imported in Python as:
// from cryptotechnolog_rust import calculate_position_size
//
// Python Support: 3.11, 3.12, 3.13
// PyO3 Version: 0.28.2
// pyo3-async-runtimes: 0.28 (fork for PyO3 0.21+ support)
//
// Allocator: Uses jemallocator on Linux/Mac for optimal performance,
//            system allocator on Windows (Microsoft's Low Fragmentation Heap)
//            which is well-optimized and integrated with the OS.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

// ==================== Global Allocator ====================
// Use jemallocator on non-Windows platforms for optimal performance
// Windows uses the system allocator which is well-optimized
#[cfg(all(not(windows), feature = "jemalloc"))]
use jemallocator::Jemalloc;

#[cfg(all(not(windows), feature = "jemalloc"))]
#[global_allocator]
static GLOBAL: Jemalloc = Jemalloc;

// ==================== Synchronous Functions ====================

/// Calculate position size based on risk parameters.
///
/// # Arguments
///
/// * `equity` - Total account equity
/// * `risk_percent` - Risk percentage per trade (e.g., 0.01 for 1%)
/// * `entry_price` - Entry price
/// * `stop_loss` - Stop loss price
///
/// # Returns
///
/// Position size in units
///
/// # Example
///
/// ```python
/// from cryptotechnolog_rust import calculate_position_size
/// size = calculate_position_size(10000.0, 0.01, 100.0, 98.0)
/// ```
#[pyfunction]
#[pyo3(signature = (equity, risk_percent, entry_price, stop_loss))]
fn calculate_position_size(
    equity: f64,
    risk_percent: f64,
    entry_price: f64,
    stop_loss: f64,
) -> PyResult<f64> {
    let risk_amount = equity * risk_percent;
    let price_risk = (entry_price - stop_loss).abs();

    if price_risk == 0.0 {
        return Err(PyValueError::new_err("Price risk cannot be zero"));
    }

    let position_size = risk_amount / price_risk;
    Ok(position_size)
}

/// Calculate portfolio risk based on positions.
///
/// # Arguments
///
/// * `positions` - List of tuples (entry_price, stop_loss, size)
///
/// # Returns
///
/// Total portfolio risk in currency units
///
/// # Example
///
/// ```python
/// from cryptotechnolog_rust import calculate_portfolio_risk
///
/// positions = [(100.0, 98.0, 50.0), (200.0, 195.0, 30.0)]
/// risk = calculate_portfolio_risk(positions)
/// # risk = 250.0
/// ```
#[pyfunction]
fn calculate_portfolio_risk(
    positions: Vec<(f64, f64, f64)>, // (entry, stop, size)
) -> PyResult<f64> {
    let total_risk: f64 = positions
        .iter()
        .map(|(entry, stop, size)| {
            let risk_per_unit = (entry - stop).abs();
            risk_per_unit * size
        })
        .sum();

    Ok(total_risk)
}

/// Calculate expected return based on win rate and reward/risk ratio.
///
/// # Arguments
///
/// * `win_rate` - Win rate (e.g., 0.6 for 60%)
/// * `reward_risk_ratio` - Reward to risk ratio (e.g., 2.0 for 2:1)
/// * `avg_risk` - Average risk per trade
///
/// # Returns
///
/// Expected return per trade
///
/// # Example
///
/// ```python
/// from cryptotechnolog_rust import calculate_expected_return
///
/// expected = calculate_expected_return(0.6, 2.0, 100.0)
/// # expected = 80.0
/// ```
#[pyfunction]
fn calculate_expected_return(
    win_rate: f64,
    reward_risk_ratio: f64,
    avg_risk: f64,
) -> PyResult<f64> {
    let win_reward = win_rate * avg_risk * reward_risk_ratio;
    let loss_cost = (1.0 - win_rate) * avg_risk;
    Ok(win_reward - loss_cost)
}

// ==================== Asynchronous Functions ====================

/// Calculate position size based on risk parameters (async).
///
/// This is an async version of calculate_position_size for use in async contexts.
///
/// # Arguments
///
/// * `equity` - Total account equity
/// * `risk_percent` - Risk percentage per trade
/// * `entry_price` - Entry price
/// * `stop_loss` - Stop loss price
///
/// # Returns
///
/// Position size in units
///
/// # Example
///
/// ```python
/// import asyncio
/// from cryptotechnolog_rust import async_calculate_position_size
///
/// async def main():
///     size = await async_calculate_position_size(10000.0, 0.01, 100.0, 98.0)
///     print(size)
/// asyncio.run(main())
/// ```
#[pyfunction]
#[pyo3(signature = (equity, risk_percent, entry_price, stop_loss))]
fn async_calculate_position_size(
    py: Python<'_>,
    equity: f64,
    risk_percent: f64,
    entry_price: f64,
    stop_loss: f64,
) -> PyResult<Bound<'_, PyAny>> {
    future_into_py(py, async move {
        let risk_amount = equity * risk_percent;
        let price_risk = (entry_price - stop_loss).abs();

        if price_risk == 0.0 {
            return Err(PyValueError::new_err("Price risk cannot be zero"));
        }

        let position_size = risk_amount / price_risk;
        Ok(position_size)
    })
}

/// Calculate portfolio risk (async).
///
/// This is an async version of calculate_portfolio_risk for use in async contexts.
///
/// # Arguments
///
/// * `positions` - List of tuples (entry_price, stop_loss, size)
///
/// # Returns
///
/// Total portfolio risk in currency units
#[pyfunction]
fn async_calculate_portfolio_risk(
    py: Python<'_>,
    positions: Vec<(f64, f64, f64)>, // (entry, stop, size)
) -> PyResult<Bound<'_, PyAny>> {
    future_into_py(py, async move {
        let total_risk: f64 = positions
            .iter()
            .map(|(entry, stop, size)| {
                let risk_per_unit = (entry - stop).abs();
                risk_per_unit * size
            })
            .sum();

        Ok(total_risk)
    })
}

// ==================== Python Module Definition ====================

/// Python module definition
#[pymodule]
fn cryptotechnolog_rust<'py>(_py: Python<'py>, m: &Bound<'py, PyModule>) -> PyResult<()> {
    // Add synchronous functions
    m.add_function(wrap_pyfunction!(calculate_position_size, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_portfolio_risk, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_expected_return, m)?)?;

    // Add asynchronous functions
    m.add_function(wrap_pyfunction!(async_calculate_position_size, m)?)?;
    m.add_function(wrap_pyfunction!(async_calculate_portfolio_risk, m)?)?;

    // Add module info
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__author__", "CRYPTOTEHNOLOG Team")?;

    Ok(())
}

// ==================== Tests ====================
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_position_size() {
        let size = calculate_position_size(10000.0, 0.01, 100.0, 98.0).unwrap();
        assert_eq!(size, 50.0);
    }

    #[test]
    fn test_calculate_position_size_zero_risk() {
        let result = calculate_position_size(10000.0, 0.01, 100.0, 100.0);
        assert!(result.is_err());
    }

    #[test]
    fn test_calculate_portfolio_risk() {
        let positions = vec![(100.0, 98.0, 50.0), (200.0, 195.0, 30.0)];
        let risk = calculate_portfolio_risk(positions).unwrap();
        assert_eq!(risk, 250.0);
    }

    #[test]
    fn test_calculate_expected_return() {
        let expected = calculate_expected_return(0.6, 2.0, 100.0).unwrap();
        assert_eq!(expected, 80.0);
    }
}
