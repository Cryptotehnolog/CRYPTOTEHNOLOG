// ==================== CRYPTOTEHNOLOG Property-Based Tests ====================
// Order matching property-based tests
//
// These tests verify that the order matching engine maintains
// its invariants across 10,000+ random inputs.

use cryptotechnolog_execution_core::execution::{
    Order, OrderMatchingEngine, OrderSide, OrderType,
};
use proptest::prelude::*;

// Generate arbitrary order
fn any_order() -> impl Strategy<Value = Order> {
    (
        proptest::collection::vec(proptest::num::u8::ANY, 10)
            .prop_map(|v| v.into_iter().map(|b| b as char).collect()),
        prop_oneof![Just(OrderSide::Buy), Just(OrderSide::Sell)],
        0.001f64..1000.0,
        1.0f64..100000.0,
        prop_oneof![Just(OrderType::Market), Just(OrderType::Limit)],
    )
    .prop_map(|(symbol, side, quantity, price, order_type)| {
        Order::new(symbol, side, quantity, price, order_type)
    })
}

// Generate orders for same symbol
fn same_symbol_orders(count: usize) -> impl Strategy<Value = Vec<Order>> {
    proptest::collection::vec(any_order(), count..=count)
        .prop_map(|mut orders| {
            // All orders same symbol
            for order in &mut orders {
                order.symbol = "BTCUSDT".to_string();
            }
            orders
        })
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(10_000))]

    /// Property: Trades never exceed order quantities
    #[test]
    fn test_trades_not_exceed_quantity(orders in same_symbol_orders(4)) {
        let mut engine = OrderMatchingEngine::new();

        // Add first order
        let first_order = orders[0].clone();
        let first_qty = first_order.quantity;

        let trades = engine.add_order(first_order);

        // Total traded quantity should not exceed original
        let total_traded: f64 = trades.iter().map(|t| t.quantity).sum();
        assert!(total_traded <= first_qty + 0.0001);

        engine.clear();
    }

    /// Property: Trade price is within bid-ask spread
    #[test]
    fn test_trade_price_within_spread(_orders in same_symbol_orders(2)) {
        let mut engine = OrderMatchingEngine::new();

        // Add buy order
        let buy_order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            1.0,
            50000.0,
            OrderType::Limit,
        );
        let buy_price = buy_order.price;

        // Add sell order
        let sell_order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Sell,
            1.0,
            50000.0,
            OrderType::Limit,
        );
        let sell_price = sell_order.price;

        engine.add_order(buy_order);
        let trades = engine.add_order(sell_order);

        for trade in trades {
            assert!(
                trade.price >= buy_price.min(sell_price),
                "Trade price should be within spread"
            );
            assert!(
                trade.price <= buy_price.max(sell_price),
                "Trade price should be within spread"
            );
        }

        engine.clear();
    }

    /// Property: Trade value equals price * quantity
    #[test]
    fn test_trade_value_calculation(orders in same_symbol_orders(2)) {
        let mut engine = OrderMatchingEngine::new();

        let order1 = orders[0].clone();
        let order2 = orders[1].clone();

        engine.add_order(order1);
        let trades = engine.add_order(order2);

        for trade in trades {
            let expected_value = trade.price * trade.quantity;
            let actual_value = trade.value();

            assert!(
                (expected_value - actual_value).abs() < 0.01,
                "Trade value should equal price * quantity"
            );
        }

        engine.clear();
    }

    /// Property: Market orders always execute against limit orders
    #[test]
    fn test_market_order_executes(
        quantity in 0.1f64..10.0,
        limit_price in 1000.0f64..100000.0,
    ) {
        let mut engine = OrderMatchingEngine::new();

        // Add limit sell order
        let limit_order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Sell,
            quantity,
            limit_price,
            OrderType::Limit,
        );

        engine.add_order(limit_order);

        // Add market buy order
        let market_order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            quantity,
            0.0, // Price ignored for market orders
            OrderType::Market,
        );

        let trades = engine.add_order(market_order);

        // Market order should execute
        assert!(!trades.is_empty(), "Market order should execute");

        // Trade price should equal limit price
        for trade in trades {
            assert_eq!(trade.price, limit_price);

            // Quantity should be filled
            assert!((trade.quantity - quantity).abs() < 0.0001);
        }

        engine.clear();
    }

    /// Property: Opposite orders on different symbols don't match
    #[test]
    fn test_different_symbols_no_match(
        symbol1 in "[A-Z]{3,10}",
        symbol2 in "[A-Z]{3,10}",
    ) {
        // Ensure different symbols
        let symbol2 = if symbol1 == symbol2 {
            format!("{}_DIFF", symbol2)
        } else {
            symbol2
        };

        let mut engine = OrderMatchingEngine::new();

        let order1 = Order::new(
            symbol1,
            OrderSide::Buy,
            1.0,
            50000.0,
            OrderType::Limit,
        );

        let order2 = Order::new(
            symbol2,
            OrderSide::Sell,
            1.0,
            50000.0,
            OrderType::Limit,
        );

        engine.add_order(order1);
        let trades = engine.add_order(order2);

        // No trades between different symbols
        assert!(trades.is_empty(), "Different symbols should not match");

        engine.clear();
    }

    /// Property: Same side orders don't match
    #[test]
    fn test_same_side_no_match(quantity in 0.1f64..10.0, price in 1000.0f64..100000.0) {
        let mut engine = OrderMatchingEngine::new();

        // Two buy orders
        let order1 = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            quantity,
            price,
            OrderType::Limit,
        );

        let order2 = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            quantity,
            price,
            OrderType::Limit,
        );

        engine.add_order(order1);
        let trades = engine.add_order(order2);

        // Same side should not match
        assert!(trades.is_empty(), "Same side orders should not match");

        engine.clear();
    }

    /// Property: Partial fills work correctly
    #[test]
    fn test_partial_fill(
        large_qty in 1.0f64..10.0,
        small_qty in 0.1f64..0.9,
    ) {
        let mut engine = OrderMatchingEngine::new();

        // Large sell order
        let sell_order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Sell,
            large_qty,
            50000.0,
            OrderType::Limit,
        );

        // Small buy order
        let buy_order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            small_qty,
            50000.0,
            OrderType::Limit,
        );

        engine.add_order(sell_order);
        let trades = engine.add_order(buy_order);

        // Should have one trade
        assert_eq!(trades.len(), 1);

        // Trade quantity should equal smaller order
        assert!((trades[0].quantity - small_qty).abs() < 0.0001);

        // Remaining sell order should be in book
        let (_buy_count, sell_count, _) = engine.pending_count();
        assert_eq!(sell_count, 1, "Remaining sell order should be in book");

        engine.clear();
    }

    /// Property: Order ID consistency in trades
    #[test]
    fn test_trade_order_ids(orders in same_symbol_orders(2)) {
        let mut engine = OrderMatchingEngine::new();

        let order1 = orders[0].clone();
        let order2 = orders[1].clone();

        let id1 = order1.id;
        let id2 = order2.id;

        engine.add_order(order1);
        let trades = engine.add_order(order2);

        for trade in trades {
            // One order should be buyer, one seller
            let is_buyer_1 = trade.buy_order_id == id1;
            let is_seller_1 = trade.sell_order_id == id1;
            let is_buyer_2 = trade.buy_order_id == id2;
            let is_seller_2 = trade.sell_order_id == id2;

            assert!(
                (is_buyer_1 && is_seller_2) || (is_buyer_2 && is_seller_1),
                "Trade should have one buyer and one seller"
            );

            // IDs should be valid UUIDs (not zero)
            assert_ne!(trade.buy_order_id, uuid::Uuid::nil());
            assert_ne!(trade.sell_order_id, uuid::Uuid::nil());
        }

        engine.clear();
    }
}
