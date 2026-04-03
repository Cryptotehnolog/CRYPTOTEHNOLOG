# ==================== CRYPTOTEHNOLOG Backtest Examples ====================

from typing import Any, cast

import pandas as pd

from cryptotechnolog.backtest.events import TickEvent
from cryptotechnolog.backtest.recorder import BALANCE_STOP_THRESHOLD, SPREAD_THRESHOLD
from cryptotechnolog.backtest.replay_engine import ReplayConfig, ReplayEngine


# Example 1: Simple tick processing
def example_simple() -> dict[str, Any]:
    """Simple example with in-memory data."""
    # Create sample tick data
    data = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="1s"),
            "symbol": ["BTCUSDT"] * 100,
            "bid": [42000 + i * 10 for i in range(100)],
            "ask": [42000 + i * 10 + 5 for i in range(100)],
            "last": [42000 + i * 10 + 2 for i in range(100)],
            "volume": [1.0] * 100,
        }
    )

    # Create config
    config = ReplayConfig(
        data_source="dataframe",
        initial_balance=10_000.0,
        commission_rate=0.001,
    )

    # Create and run engine
    engine = ReplayEngine(config)
    results: dict[str, Any] = engine.load_dataframe(data).run()

    print(f"Processed {results['ticks_processed']} ticks")
    print(f"Final balance: ${results['final_balance']:.2f}")

    return results


# Example 2: With callbacks
def example_with_callbacks() -> dict[str, Any]:
    """Example with strategy callbacks."""
    position = {"size": 0.0, "entry_price": 0.0}

    def on_tick(tick: TickEvent) -> None:
        """Simple mean-reversion strategy."""
        spread = tick.ask - tick.bid
        mid = tick.mid

        if spread > SPREAD_THRESHOLD:  # Wide spread - potential mean reversion
            if position["size"] == 0:
                # Buy
                position["size"] = 0.01
                position["entry_price"] = mid
                print(f"BUY at {mid:.2f}")
        elif position["size"] > 0 and tick.last > position["entry_price"] + 50:
            # Take profit
            pnl = position["size"] * (tick.last - position["entry_price"])
            print(f"SELL at {tick.last:.2f}, PnL: {pnl:.2f}")
            position["size"] = 0.0

    config = ReplayConfig(
        on_tick=on_tick,
        initial_balance=10_000.0,
    )

    # Create sample data
    data = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=1000, freq="1s"),
            "symbol": ["BTCUSDT"] * 1000,
            "bid": [42000 + i * 0.5 for i in range(1000)],
            "ask": [42000 + i * 0.5 + 2 for i in range(1000)],
            "last": [42000 + i * 0.5 + 1 for i in range(1000)],
            "volume": [1.0] * 1000,
        }
    )

    engine = ReplayEngine(config)
    results: dict[str, Any] = engine.load_dataframe(data).run()

    print(f"Final position: {position}")
    return results


# Example 3: Load from CSV
def example_from_csv(csv_path: str) -> dict[str, Any]:
    """Example loading from CSV file."""
    config = ReplayConfig(
        data_source="csv",
        output_dir="./backtest_results",
        on_tick=lambda _: None,  # Add your strategy here
    )

    engine = ReplayEngine(config)
    results: dict[str, Any] = engine.load_csv(csv_path).run()

    # Get recorded events
    if engine.recorder:
        events_df = engine.recorder.to_dataframe()
        trades_df = engine.recorder.trades_to_dataframe()

        print(f"Total events: {len(events_df)}")
        print(f"Total trades: {len(trades_df)}")

        # Save to file
        engine.recorder.save()

    return results


# Example 4: Conditional run
def example_conditional() -> dict[str, Any]:
    """Run until certain condition is met."""
    config = ReplayConfig()

    def stop_condition(tick: TickEvent, state: dict[str, Any]) -> bool:
        """Stop when balance drops below $9000."""
        balance = cast("float", state["balance"])
        result: bool = balance < BALANCE_STOP_THRESHOLD
        return result

    data = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=10000, freq="1s"),
            "symbol": ["BTCUSDT"] * 10000,
            "bid": [42000 - i * 0.1 for i in range(10000)],  # Declining price
            "ask": [42000 - i * 0.1 + 5 for i in range(10000)],
            "last": [42000 - i * 0.1 + 2 for i in range(10000)],
            "volume": [1.0] * 10000,
        }
    )

    engine = ReplayEngine(config)
    results: dict[str, Any] = engine.load_dataframe(data).run_until(stop_condition, max_ticks=5000)

    print(f"Stopped after {results['ticks_processed']} ticks")
    print(f"Balance: ${results['final_balance']:.2f}")

    return results


if __name__ == "__main__":
    print("=== Example 1: Simple ===")
    example_simple()

    print("\n=== Example 2: With callbacks ===")
    example_with_callbacks()

    print("\n=== Example 4: Conditional ===")
    example_conditional()
