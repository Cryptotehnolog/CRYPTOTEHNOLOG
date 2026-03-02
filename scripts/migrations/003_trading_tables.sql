-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 003
-- Description: Trading Tables - Orders, Positions, Executions
-- Created: 2026-02-28
-- Author: CRYPTOTEHNOLOG Team
-- ============================================================

-- ============================================================
-- Section 1: Orders Tables
-- ============================================================

-- Orders (all order records)
CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    price DOUBLE PRECISION,
    size DOUBLE PRECISION NOT NULL,
    filled_size DOUBLE PRECISION DEFAULT 0,
    remaining_size DOUBLE PRECISION GENERATED ALWAYS AS (size - filled_size) STORED,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    leverage DOUBLE PRECISION DEFAULT 1.0,
    
    -- Execution details
    average_price DOUBLE PRECISION,
    last_fill_price DOUBLE PRECISION,
    last_fill_size DOUBLE PRECISION,
    
    -- Time constraints
    time_in_force VARCHAR(10) DEFAULT 'GTC',
    expire_time TIMESTAMP WITH TIME ZONE,
    
    -- State machine integration
    state VARCHAR(50) DEFAULT 'created',
    state_version INTEGER DEFAULT 0,
    
    -- Metadata
    client_order_id VARCHAR(100),
    exchange_order_id VARCHAR(200),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    filled_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT chk_order_side CHECK (side IN ('BUY', 'SELL', 'SHORT', 'LONG')),
    CONSTRAINT chk_order_type CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit', 'market_if_touched')),
    CONSTRAINT chk_order_status CHECK (status IN ('pending', 'open', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired')),
    CONSTRAINT chk_time_in_force CHECK (time_in_force IN ('GTC', 'IOC', 'FOK', 'GTX', 'GTT')),
    CONSTRAINT chk_size_positive CHECK (size > 0),
    CONSTRAINT chk_price_positive CHECK (price IS NULL OR price > 0),
    CONSTRAINT chk_leverage CHECK (leverage >= 1.0)
);

-- Order History (state changes over time)
CREATE TABLE IF NOT EXISTS order_history (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100) NOT NULL,
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    trigger VARCHAR(50),
    filled_size_at_change DOUBLE PRECISION DEFAULT 0,
    price_at_change DOUBLE PRECISION,
    metadata JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_order_history_status CHECK (
        to_status IN ('pending', 'open', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired')
    )
);

-- ============================================================
-- Section 2: Positions Tables
-- ============================================================

-- Positions (current open positions)
CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    position_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    current_price DOUBLE PRECISION,
    leverage DOUBLE PRECISION DEFAULT 1.0,
    
    -- P&L calculations
    unrealized_pnl DOUBLE PRECISION DEFAULT 0,
    realized_pnl DOUBLE PRECISION DEFAULT 0,
    total_pnl DOUBLE PRECISION GENERATED ALWAYS AS (unrealized_pnl + realized_pnl) STORED,
    
    -- Margin
    margin_used DOUBLE PRECISION DEFAULT 0,
    liquidation_price DOUBLE PRECISION,
    
    -- State
    status VARCHAR(20) DEFAULT 'open',
    
    -- Timestamps
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT chk_position_side CHECK (side IN ('LONG', 'SHORT')),
    CONSTRAINT chk_position_status CHECK (status IN ('open', 'closed', 'liquidated', 'settled')),
    CONSTRAINT chk_position_size_nonzero CHECK (size != 0)
);

-- Position History (historical positions for audit)
CREATE TABLE IF NOT EXISTS position_history (
    id BIGSERIAL PRIMARY KEY,
    position_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_price DOUBLE PRECISION,
    leverage DOUBLE PRECISION,
    realized_pnl DOUBLE PRECISION,
    closed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    close_reason VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================================
-- Section 3: Executions Tables
-- ============================================================

-- Executions (individual fills/trades)
CREATE TABLE IF NOT EXISTS executions (
    id BIGSERIAL PRIMARY KEY,
    execution_id VARCHAR(100) UNIQUE NOT NULL,
    order_id VARCHAR(100) NOT NULL,
    position_id VARCHAR(100),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION DEFAULT 0,
    fee_currency VARCHAR(10) DEFAULT 'USDT',
    
    -- Execution details
    execution_type VARCHAR(20) DEFAULT 'fill',
    liquidity VARCHAR(10) DEFAULT 'unknown',
    
    -- State
    state VARCHAR(50) DEFAULT 'confirmed',
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamp
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_execution_side CHECK (side IN ('BUY', 'SELL')),
    CONSTRAINT chk_execution_type CHECK (execution_type IN ('fill', 'cancel', 'reject', 'expire')),
    CONSTRAINT chk_liquidity CHECK (liquidity IN ('maker', 'taker', 'unknown')),
    CONSTRAINT chk_execution_size CHECK (size > 0),
    CONSTRAINT chk_execution_price CHECK (price > 0)
);

-- ============================================================
-- Section 4: Indexes
-- ============================================================

-- Orders indexes
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_state ON orders(state);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_client_order_id ON orders(client_order_id) WHERE client_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_exchange_order_id ON orders(exchange_order_id) WHERE exchange_order_id IS NOT NULL;

-- Order History indexes
CREATE INDEX IF NOT EXISTS idx_order_history_order_id ON order_history(order_id);
CREATE INDEX IF NOT EXISTS idx_order_history_timestamp ON order_history(timestamp DESC);

-- Positions indexes
CREATE INDEX IF NOT EXISTS idx_positions_position_id ON positions(position_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_positions_opened_at ON positions(opened_at DESC);

-- Position History indexes
CREATE INDEX IF NOT EXISTS idx_position_history_position_id ON position_history(position_id);
CREATE INDEX IF NOT EXISTS idx_position_history_closed_at ON position_history(closed_at DESC);

-- Executions indexes
CREATE INDEX IF NOT EXISTS idx_executions_execution_id ON executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_executions_order_id ON executions(order_id);
CREATE INDEX IF NOT EXISTS idx_executions_position_id ON executions(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_executions_symbol ON executions(symbol);
CREATE INDEX IF NOT EXISTS idx_executions_timestamp ON executions(timestamp DESC);

-- ============================================================
-- Migration Metadata
-- ============================================================

INSERT INTO schema_migrations (version, description)
VALUES ('003', 'Trading Tables - Orders, Positions, Executions')
ON CONFLICT (version) DO NOTHING;

-- ============================================================
-- Comments for Documentation
-- ============================================================

COMMENT ON TABLE orders IS 'All order records with state tracking';
COMMENT ON TABLE order_history IS 'Historical order state changes';
COMMENT ON TABLE positions IS 'Current open positions';
COMMENT ON TABLE position_history IS 'Historical closed positions';
COMMENT ON TABLE executions IS 'Individual trade executions/fills';
