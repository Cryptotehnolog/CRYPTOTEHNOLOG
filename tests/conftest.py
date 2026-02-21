# ==================== CRYPTOTEHNOLOG Test Configuration ====================
# Pytest configuration and fixtures

import sys
from collections.abc import Generator
import os
from pathlib import Path

import pytest

# Add src directory to Python path for pytest-xdist compatibility
# This is required because pytest pythonpath in pyproject.toml doesn't work
# reliably with pytest-xdist (parallel test execution).
# See: https://github.com/pytest-dev/pytest-xdist/issues/32
_src_path = Path(__file__).parent.parent / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from cryptotechnolog.config.settings import Settings  # noqa: E402

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"


@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables."""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["POSTGRES_DB"] = "trading_test"
    os.environ["REDIS_DB"] = "1"
    yield
    # Cleanup after session


@pytest.fixture(autouse=True)
def isolate_environment():
    """Isolate environment variables for each test."""
    # Store original environment
    original_env = dict(os.environ)

    yield

    # Restore environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def test_settings():
    """Provide test settings instance."""
    return Settings()


@pytest.fixture
def temp_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary directory for tests."""
    yield tmp_path


@pytest.fixture
def sample_market_data():
    """Provide sample market data for testing."""
    return {
        "exchange": "bybit",
        "symbol": "BTCUSDT",
        "timestamp": "2024-01-01T00:00:00Z",
        "open": 42000.0,
        "high": 42500.0,
        "low": 41800.0,
        "close": 42300.0,
        "volume": 100.5,
    }


@pytest.fixture
def sample_order():
    """Provide sample order data for testing."""
    return {
        "exchange": "bybit",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 0.1,
        "price": 42000.0,
    }


@pytest.fixture
def sample_position():
    """Provide sample position data for testing."""
    return {
        "exchange": "bybit",
        "symbol": "BTCUSDT",
        "side": "LONG",
        "quantity": 0.1,
        "entry_price": 42000.0,
        "leverage": 1.0,
    }


# Pytest markers configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "slowest: Very slow running tests")
