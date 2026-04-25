from __future__ import annotations

import cryptotechnolog.bootstrap as bootstrap_module
from cryptotechnolog.bootstrap import _BybitConnectorScopeTruth
from cryptotechnolog.config.settings import Settings


def test_spot_scope_reuse_is_disabled_when_trade_count_policy_changes() -> None:
    settings = Settings.model_validate(
        {
            "environment": "test",
            "debug": True,
            "base_r_percent": 0.01,
            "max_r_per_trade": 0.02,
            "max_portfolio_r": 0.05,
            "risk_max_total_exposure_usd": 25000.0,
            "risk_kelly_fraction_cap": 0.25,
            "risk_min_order_notional_usd": 20.0,
            "redis_url": "redis://localhost:6379/0",
            "database_url": "postgresql://user:pass@localhost:5432/test_db",
            "jwt_secret_key": "test-secret-key-for-jwt-minimum-32-chars",
            "secret_key": "test-secret-key-minimum-32-chars!!!",
            "bybit_spot_market_data_connector_enabled": True,
            "bybit_spot_universe_min_trade_count_24h": 1,
            "bybit_spot_quote_asset_filter": "usdt_usdc",
        }
    )
    existing_truth = _BybitConnectorScopeTruth(
        scope_mode="universe",
        discovery_status="ready",
        trade_count_filter_minimum=1000,
        discovery_signature=bootstrap_module._build_bybit_discovery_signature(
            settings=settings,
            contour="spot",
        ),
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 9000),),
        instruments_passed_final_filter=1,
    )

    reused = bootstrap_module._reuse_bybit_universe_scope_if_possible(
        settings=settings,
        contour="spot",
        existing_truth=existing_truth,
    )

    assert reused is None
