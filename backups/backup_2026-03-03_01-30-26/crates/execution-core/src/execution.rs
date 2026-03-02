// ==================== CRYPTOTEHNOLOG Execution Engine ====================
// Execution module (placeholder - will be implemented in Phase 7)

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};

/// Order side
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderSide {
    Buy,
    Sell,
}

impl OrderSide {
    pub fn parse(s: &str) -> Option<Self> {
        match s.to_uppercase().as_str() {
            "BUY" => Some(OrderSide::Buy),
            "SELL" => Some(OrderSide::Sell),
            _ => None,
        }
    }

    pub fn is_buy(&self) -> bool {
        matches!(self, OrderSide::Buy)
    }

    pub fn opposite(&self) -> Self {
        match self {
            OrderSide::Buy => OrderSide::Sell,
            OrderSide::Sell => OrderSide::Buy,
        }
    }
}

/// Order type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderType {
    Market,
    Limit,
    StopLoss,
    TakeProfit,
}

impl OrderType {
    pub fn parse(s: &str) -> Option<Self> {
        match s.to_uppercase().as_str() {
            "MARKET" => Some(OrderType::Market),
            "LIMIT" => Some(OrderType::Limit),
            "STOPLOSS" | "STOP_LOSS" | "STOP" => Some(OrderType::StopLoss),
            "TAKEPROFIT" | "TAKE_PROFIT" => Some(OrderType::TakeProfit),
            _ => None,
        }
    }

    pub fn is_market(&self) -> bool {
        matches!(self, OrderType::Market)
    }

    pub fn is_stop(&self) -> bool {
        matches!(self, OrderType::StopLoss | OrderType::TakeProfit)
    }
}

/// Order status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderStatus {
    Pending,
    Open,
    PartiallyFilled,
    Filled,
    Cancelled,
    Rejected,
    Expired,
}

/// Order for execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Order {
    /// Order ID
    pub id: uuid::Uuid,
    /// Symbol (e.g., "BTCUSDT")
    pub symbol: String,
    /// Order side (BUY/SELL)
    pub side: OrderSide,
    /// Original order quantity
    pub original_quantity: f64,
    /// Remaining quantity to fill
    pub quantity: f64,
    /// Order price (limit price or stop price)
    pub price: f64,
    /// Order type (MARKET/LIMIT/STOPLOSS/TAKEPROFIT)
    pub order_type: OrderType,
    /// Order status
    pub status: OrderStatus,
    /// Stop price (for stop orders)
    pub stop_price: Option<f64>,
    /// Trailing stop callback rate (e.g., 0.001 = 0.1%)
    pub trailing_callback_rate: Option<f64>,
    /// Trailing stop activation price
    pub trailing_activation_price: Option<f64>,
    /// Timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
    /// Filled timestamp
    pub filled_at: Option<chrono::DateTime<chrono::Utc>>,
    /// Parent order ID (for OCO orders)
    pub parent_order_id: Option<uuid::Uuid>,
    /// Client order ID (for user reference)
    pub client_order_id: Option<String>,
}

impl Order {
    /// Create a new order
    pub fn new(
        symbol: String,
        side: OrderSide,
        quantity: f64,
        price: f64,
        order_type: OrderType,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            symbol,
            side,
            original_quantity: quantity,
            quantity,
            price,
            order_type,
            status: OrderStatus::Pending,
            stop_price: None,
            trailing_callback_rate: None,
            trailing_activation_price: None,
            timestamp: chrono::Utc::now(),
            filled_at: None,
            parent_order_id: None,
            client_order_id: None,
        }
    }

    /// Create a stop-loss order
    pub fn stop_loss(
        symbol: String,
        side: OrderSide,
        quantity: f64,
        stop_price: f64,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            symbol,
            side,
            original_quantity: quantity,
            quantity,
            price: stop_price,
            order_type: OrderType::StopLoss,
            status: OrderStatus::Pending,
            stop_price: Some(stop_price),
            trailing_callback_rate: None,
            trailing_activation_price: None,
            timestamp: chrono::Utc::now(),
            filled_at: None,
            parent_order_id: None,
            client_order_id: None,
        }
    }

    /// Create a take-profit order
    pub fn take_profit(
        symbol: String,
        side: OrderSide,
        quantity: f64,
        stop_price: f64,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            symbol,
            side,
            original_quantity: quantity,
            quantity,
            price: stop_price,
            order_type: OrderType::TakeProfit,
            status: OrderStatus::Pending,
            stop_price: Some(stop_price),
            trailing_callback_rate: None,
            trailing_activation_price: None,
            timestamp: chrono::Utc::now(),
            filled_at: None,
            parent_order_id: None,
            client_order_id: None,
        }
    }

    /// Create a trailing stop order
    pub fn trailing_stop(
        symbol: String,
        side: OrderSide,
        quantity: f64,
        callback_rate: f64,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            symbol,
            side,
            original_quantity: quantity,
            quantity,
            price: 0.0, // Will be updated based on market
            order_type: OrderType::StopLoss,
            status: OrderStatus::Pending,
            stop_price: None,
            trailing_callback_rate: Some(callback_rate),
            trailing_activation_price: None,
            timestamp: chrono::Utc::now(),
            filled_at: None,
            parent_order_id: None,
            client_order_id: None,
        }
    }

    /// Check if order can match with another
    pub fn can_match_with(&self, other: &Order) -> bool {
        self.symbol == other.symbol && self.side != other.side
    }

    /// Calculate execution price for a match
    pub fn execution_price(&self, other: &Order) -> f64 {
        // For market orders, use the limit order price
        // For two limit orders, use price-time priority
        if self.order_type == OrderType::Market {
            other.price
        } else if other.order_type == OrderType::Market {
            self.price
        } else {
            // Both limit orders: use price-time priority
            // Higher price wins for buys, lower price wins for sells
            if self.side.is_buy() {
                self.price.max(other.price)
            } else {
                self.price.min(other.price)
            }
        }
    }

    /// Calculate notional value
    pub fn notional(&self) -> f64 {
        self.quantity * self.price
    }

    /// Check if stop order should trigger
    pub fn should_trigger_stop(&self, current_price: f64) -> bool {
        if !self.order_type.is_stop() {
            return false;
        }

        let stop = match self.stop_price {
            Some(p) => p,
            None => return false,
        };

        match self.order_type {
            OrderType::StopLoss => {
                if self.side.is_buy() {
                    // Buy stop triggers when price goes above stop price
                    current_price >= stop
                } else {
                    // Sell stop triggers when price goes below stop price
                    current_price <= stop
                }
            }
            OrderType::TakeProfit => {
                if self.side.is_buy() {
                    current_price >= stop
                } else {
                    current_price <= stop
                }
            }
            _ => false,
        }
    }

    /// Update trailing stop price
    pub fn update_trailing_stop(&mut self, _current_price: f64, highest_price: f64, lowest_price: f64) -> bool {
        let callback_rate = match self.trailing_callback_rate {
            Some(rate) => rate,
            None => return false,
        };

        if self.side.is_buy() {
            // For long trailing stop, track highest price
            let activation = self.trailing_activation_price.unwrap_or(highest_price);

            if highest_price > activation {
                // Calculate new stop price
                let new_stop = highest_price * (1.0 - callback_rate);

                // Only update if new stop is higher
                if self.stop_price.is_none_or(|old| new_stop > old) {
                    self.stop_price = Some(new_stop);
                    self.trailing_activation_price = Some(highest_price);
                    return true;
                }
            }
        } else {
            // For short trailing stop, track lowest price
            let activation = self.trailing_activation_price.unwrap_or(lowest_price);

            if lowest_price < activation {
                // Calculate new stop price
                let new_stop = lowest_price * (1.0 + callback_rate);

                // Only update if new stop is lower
                if self.stop_price.is_none_or(|old| new_stop < old) {
                    self.stop_price = Some(new_stop);
                    self.trailing_activation_price = Some(lowest_price);
                    return true;
                }
            }
        }

        false
    }

    /// Fill order (partially or fully)
    pub fn fill(&mut self, fill_qty: f64) {
        self.quantity = (self.quantity - fill_qty).max(0.0);

        if self.quantity <= 0.0 {
            self.status = OrderStatus::Filled;
            self.filled_at = Some(chrono::Utc::now());
        } else {
            self.status = OrderStatus::PartiallyFilled;
        }
    }

    /// Check if order is still active
    pub fn is_active(&self) -> bool {
        matches!(
            self.status,
            OrderStatus::Pending | OrderStatus::Open | OrderStatus::PartiallyFilled
        )
    }

    /// Get fill percentage
    pub fn fill_percentage(&self) -> f64 {
        if self.original_quantity <= 0.0 {
            return 0.0;
        }
        let filled = self.original_quantity - self.quantity;
        (filled / self.original_quantity) * 100.0
    }
}

/// Trade execution result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trade {
    /// Buy order ID
    pub buy_order_id: uuid::Uuid,
    /// Sell order ID
    pub sell_order_id: uuid::Uuid,
    /// Symbol
    pub symbol: String,
    /// Execution price
    pub price: f64,
    /// Execution quantity
    pub quantity: f64,
    /// Trade timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

impl Trade {
    /// Create a new trade
    pub fn new(buy_id: uuid::Uuid, sell_id: uuid::Uuid, symbol: String, price: f64, quantity: f64) -> Self {
        Self {
            buy_order_id: buy_id,
            sell_order_id: sell_id,
            symbol,
            price,
            quantity,
            timestamp: chrono::Utc::now(),
        }
    }

    /// Calculate trade value
    pub fn value(&self) -> f64 {
        self.price * self.quantity
    }
}

/// OCO (One Cancels Other) order group
#[derive(Debug, Clone)]
pub struct OcoGroup {
    /// First order
    pub order1: Order,
    /// Second order
    pub order2: Order,
    /// Whether one has been filled
    pub is_active: bool,
}

impl OcoGroup {
    /// Create a new OCO group
    pub fn new(order1: Order, order2: Order) -> Self {
        Self {
            order1,
            order2,
            is_active: true,
        }
    }

    /// Get orders that are still active
    pub fn active_orders(&self) -> Vec<&Order> {
        if !self.is_active {
            return vec![];
        }

        let mut orders = Vec::new();
        if self.order1.is_active() {
            orders.push(&self.order1);
        }
        if self.order2.is_active() {
            orders.push(&self.order2);
        }
        orders
    }

    /// Handle fill - cancel the other order
    pub fn on_fill(&mut self, filled_order_id: uuid::Uuid) {
        if !self.is_active {
            return;
        }

        if self.order1.id == filled_order_id {
            self.order2.status = OrderStatus::Cancelled;
        } else if self.order2.id == filled_order_id {
            self.order1.status = OrderStatus::Cancelled;
        }

        self.is_active = false;
    }
}

/// Order matching engine
#[derive(Debug, Clone)]
pub struct OrderMatchingEngine {
    /// Pending buy orders (price, order)
    buy_orders: VecDeque<Order>,
    /// Pending sell orders (price, order)
    sell_orders: VecDeque<Order>,
    /// Pending stop orders
    stop_orders: Vec<Order>,
    /// OCO groups
    oco_groups: Vec<OcoGroup>,
    /// Order lookup by ID
    orders_by_id: HashMap<uuid::Uuid, Order>,
    /// Current market price (last traded)
    last_price: f64,
    /// 24h high price
    high_24h: f64,
    /// 24h low price
    low_24h: f64,
}

impl OrderMatchingEngine {
    /// Create a new order matching engine
    pub fn new() -> Self {
        Self {
            buy_orders: VecDeque::new(),
            sell_orders: VecDeque::new(),
            stop_orders: Vec::new(),
            oco_groups: Vec::new(),
            orders_by_id: HashMap::new(),
            last_price: 0.0,
            high_24h: 0.0,
            low_24h: f64::MAX,
        }
    }

    /// Add an order to the book
    pub fn add_order(&mut self, mut order: Order) -> Vec<Trade> {
        let mut trades = Vec::new();

        // Store order reference
        order.status = OrderStatus::Open;
        let order_id = order.id;
        let symbol = order.symbol.clone();

        if order.order_type.is_stop() {
            // Add to stop orders
            self.stop_orders.push(order.clone());
            self.orders_by_id.insert(order_id, order);
            return trades;
        }

        if order.side.is_buy() {
            // Try to match with sell orders
            while let Some(mut sell_order) = self.sell_orders.pop_front() {
                // Market orders match any price, limit orders need price check
                let can_match = order.order_type == OrderType::Market 
                    || order.can_match_with(&sell_order) && order.price >= sell_order.price;
                
                if can_match {
                    let exec_price = order.execution_price(&sell_order);
                    let exec_qty = order.quantity.min(sell_order.quantity);

                    trades.push(Trade::new(
                        order.id,
                        sell_order.id,
                        symbol.clone(),
                        exec_price,
                        exec_qty,
                    ));

                    // Fill orders
                    order.fill(exec_qty);
                    sell_order.fill(exec_qty);

                    // Update market prices
                    self.update_market_prices(exec_price);

                    // Handle partial fills
                    if sell_order.quantity > 0.0 {
                        self.sell_orders.push_front(sell_order);
                    }

                    if order.quantity <= 0.0 {
                        break;
                    }
                } else {
                    // Put back and stop
                    self.sell_orders.push_front(sell_order);
                    break;
                }
            }

            // Add remaining to book if limit order and still has quantity
            if order.quantity > 0.0 && order.order_type == OrderType::Limit {
                self.buy_orders.push_back(order.clone());
            }
        } else {
            // Sell order - try to match with buy orders
            while let Some(mut buy_order) = self.buy_orders.pop_front() {
                // Market orders match any price, limit orders need price check
                let can_match = order.order_type == OrderType::Market
                    || order.can_match_with(&buy_order) && order.price <= buy_order.price;
                
                if can_match {
                    let exec_price = order.execution_price(&buy_order);
                    let exec_qty = order.quantity.min(buy_order.quantity);

                    trades.push(Trade::new(
                        buy_order.id,
                        order.id,
                        symbol.clone(),
                        exec_price,
                        exec_qty,
                    ));

                    // Fill orders
                    order.fill(exec_qty);
                    buy_order.fill(exec_qty);

                    // Update market prices
                    self.update_market_prices(exec_price);

                    // Handle partial fills
                    if buy_order.quantity > 0.0 {
                        self.buy_orders.push_front(buy_order);
                    }

                    if order.quantity <= 0.0 {
                        break;
                    }
                } else {
                    // Put back and stop
                    self.buy_orders.push_front(buy_order);
                    break;
                }
            }

            // Add remaining to book if limit order
            if order.quantity > 0.0 && order.order_type == OrderType::Limit {
                self.sell_orders.push_back(order.clone());
            }
        }

        // Store in lookup
        self.orders_by_id.insert(order_id, order);

        // Check for OCO fills
        self.check_oco_groups();

        // Check stop orders after trade
        if !trades.is_empty() {
            trades.extend(self.check_stop_orders());
        }

        trades
    }

    /// Cancel an order by ID
    pub fn cancel_order(&mut self, order_id: uuid::Uuid) -> Result<Order, String> {
        // Remove from buy orders
        if let Some(pos) = self.buy_orders.iter().position(|o| o.id == order_id) {
            let order = self.buy_orders.remove(pos).unwrap();
            let mut cancelled = order;
            cancelled.status = OrderStatus::Cancelled;
            self.orders_by_id.remove(&order_id);
            return Ok(cancelled);
        }

        // Remove from sell orders
        if let Some(pos) = self.sell_orders.iter().position(|o| o.id == order_id) {
            let order = self.sell_orders.remove(pos).unwrap();
            let mut cancelled = order;
            cancelled.status = OrderStatus::Cancelled;
            self.orders_by_id.remove(&order_id);
            return Ok(cancelled);
        }

        // Remove from stop orders
        if let Some(pos) = self.stop_orders.iter().position(|o| o.id == order_id) {
            let order = self.stop_orders.remove(pos);
            let mut cancelled = order;
            cancelled.status = OrderStatus::Cancelled;
            self.orders_by_id.remove(&order_id);
            return Ok(cancelled);
        }

        Err(format!("Order {} not found", order_id))
    }

    /// Cancel all orders for a symbol
    pub fn cancel_all_for_symbol(&mut self, symbol: &str) -> Vec<Order> {
        let mut cancelled = Vec::new();

        // Cancel buy orders
        let buy_ids: Vec<_> = self.buy_orders
            .iter()
            .filter(|o| o.symbol == symbol)
            .map(|o| o.id)
            .collect();

        for id in buy_ids {
            if let Ok(order) = self.cancel_order(id) {
                cancelled.push(order);
            }
        }

        // Cancel sell orders
        let sell_ids: Vec<_> = self.sell_orders
            .iter()
            .filter(|o| o.symbol == symbol)
            .map(|o| o.id)
            .collect();

        for id in sell_ids {
            if let Ok(order) = self.cancel_order(id) {
                cancelled.push(order);
            }
        }

        // Cancel stop orders
        let stop_ids: Vec<_> = self.stop_orders
            .iter()
            .filter(|o| o.symbol == symbol)
            .map(|o| o.id)
            .collect();

        for id in stop_ids {
            if let Ok(order) = self.cancel_order(id) {
                cancelled.push(order);
            }
        }

        cancelled
    }

    /// Add OCO order group
    pub fn add_oco(&mut self, order1: Order, order2: Order) -> OcoGroup {
        let oco = OcoGroup::new(order1.clone(), order2.clone());

        // Add both orders
        self.add_order(order1);
        self.add_order(order2);

        self.oco_groups.push(oco.clone());
        oco
    }

    /// Check and trigger stop orders
    fn check_stop_orders(&mut self) -> Vec<Trade> {
        let mut trades = Vec::new();

        // Collect triggered orders first
        let triggered: Vec<Order> = self.stop_orders
            .iter()
            .filter(|o| o.should_trigger_stop(self.last_price))
            .cloned()
            .collect();

        // Remove triggered from the list
        self.stop_orders.retain(|o| !triggered.iter().any(|t| t.id == o.id));

        // Execute each triggered order
        for mut order in triggered {
            // Convert to market order and execute
            order.order_type = OrderType::Market;
            order.price = self.last_price;
            order.status = OrderStatus::Open;

            let new_trades = self.add_order(order);
            trades.extend(new_trades);
        }

        trades
    }

    /// Check OCO groups for fills
    fn check_oco_groups(&mut self) {
        for group in &mut self.oco_groups {
            if group.is_active && (!group.order1.is_active() || !group.order2.is_active()) {
                // One filled - cancel the other
                group.on_fill(
                    if !group.order1.is_active() {
                        group.order1.id
                    } else {
                        group.order2.id
                    },
                );
            }
        }
    }

    /// Update market prices
    fn update_market_prices(&mut self, price: f64) {
        self.last_price = price;
        if price > self.high_24h || self.high_24h == 0.0 {
            self.high_24h = price;
        }
        if price < self.low_24h {
            self.low_24h = price;
        }
    }

    /// Update trailing stops
    pub fn update_trailing_stops(&mut self) -> Vec<Trade> {
        let trades = Vec::new();

        for order in &mut self.stop_orders {
            if order.trailing_callback_rate.is_some() {
                let _ = order.update_trailing_stop(self.last_price, self.high_24h, self.low_24h);
            }
        }

        trades
    }

    /// Get pending orders count
    pub fn pending_count(&self) -> (usize, usize, usize) {
        (self.buy_orders.len(), self.sell_orders.len(), self.stop_orders.len())
    }

    /// Get order by ID
    pub fn get_order(&self, order_id: uuid::Uuid) -> Option<&Order> {
        self.orders_by_id.get(&order_id)
    }

    /// Get last price
    pub fn last_price(&self) -> f64 {
        self.last_price
    }

    /// Get 24h high
    pub fn high_24h(&self) -> f64 {
        self.high_24h
    }

    /// Get 24h low
    pub fn low_24h(&self) -> f64 {
        self.low_24h
    }

    /// Clear all orders
    pub fn clear(&mut self) {
        self.buy_orders.clear();
        self.sell_orders.clear();
        self.stop_orders.clear();
        self.oco_groups.clear();
        self.orders_by_id.clear();
    }
}

impl Default for OrderMatchingEngine {
    fn default() -> Self {
        Self::new()
    }
}

/// Order execution engine
///
/// This is a placeholder implementation. The full implementation
/// will be added in Phase 7.
#[derive(Debug, Clone)]
pub struct ExecutionEngine {
    placeholder: bool,
}

impl Default for ExecutionEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl ExecutionEngine {
    /// Create a new execution engine
    pub fn new() -> Self {
        Self { placeholder: true }
    }
}

// ==================== Tests ====================
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_execution_engine_creation() {
        let engine = ExecutionEngine::new();
        assert!(engine.placeholder);
    }

    #[test]
    fn test_order_creation() {
        let order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            0.1,
            50000.0,
            OrderType::Limit,
        );

        assert_eq!(order.symbol, "BTCUSDT");
        assert_eq!(order.side, OrderSide::Buy);
        assert_eq!(order.quantity, 0.1);
        assert_eq!(order.status, OrderStatus::Pending);
    }

    #[test]
    fn test_stop_loss_order() {
        let order = Order::stop_loss(
            "BTCUSDT".to_string(),
            OrderSide::Sell,
            1.0,
            45000.0,
        );

        assert_eq!(order.order_type, OrderType::StopLoss);
        assert_eq!(order.stop_price, Some(45000.0));
    }

    #[test]
    fn test_trailing_stop_order() {
        let order = Order::trailing_stop(
            "BTCUSDT".to_string(),
            OrderSide::Sell,
            1.0,
            0.002, // 0.2% callback
        );

        assert!(order.trailing_callback_rate.is_some());
    }

    #[test]
    fn test_order_fill() {
        let mut order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            1.0,
            50000.0,
            OrderType::Limit,
        );

        assert_eq!(order.status, OrderStatus::Pending);

        order.fill(0.5);
        assert_eq!(order.status, OrderStatus::PartiallyFilled);
        assert_eq!(order.quantity, 0.5);

        order.fill(0.5);
        assert_eq!(order.status, OrderStatus::Filled);
        assert_eq!(order.quantity, 0.0);
    }

    #[test]
    fn test_order_matching() {
        let mut engine = OrderMatchingEngine::new();

        let buy_order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            1.0,
            50000.0,
            OrderType::Limit,
        );

        let sell_order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Sell,
            1.0,
            50000.0,
            OrderType::Limit,
        );

        engine.add_order(buy_order);
        let trades = engine.add_order(sell_order);

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].price, 50000.0);
        assert_eq!(trades[0].quantity, 1.0);
    }

    #[test]
    fn test_order_cancellation() {
        let mut engine = OrderMatchingEngine::new();

        let order = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            1.0,
            50000.0,
            OrderType::Limit,
        );

        let order_id = order.id;
        engine.add_order(order);

        let result = engine.cancel_order(order_id);
        assert!(result.is_ok());
        assert_eq!(result.unwrap().status, OrderStatus::Cancelled);
    }

    #[test]
    fn test_oco_group() {
        let order1 = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            1.0,
            51000.0,
            OrderType::Limit,
        );

        let order2 = Order::new(
            "BTCUSDT".to_string(),
            OrderSide::Buy,
            1.0,
            49000.0,
            OrderType::Limit,
        );

        let mut group = OcoGroup::new(order1, order2);
        assert_eq!(group.active_orders().len(), 2);

        // Simulate fill of order1
        group.on_fill(group.order1.id);
        assert!(!group.is_active);
    }
}
