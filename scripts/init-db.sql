-- ==================== CRYPTOTEHNOLOG Database Initialization Script ====================
-- PostgreSQL + TimescaleDB initialization for development environment

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create pgcrypto extension for cryptographic functions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ==================== Audit Trail Tables ====================

-- Audit events table (immutable audit trail)
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    event_source VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    previous_hash VARCHAR(64),
    current_hash VARCHAR(64) NOT NULL,
    signature VARCHAR(256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index on event_timestamp for queries
CREATE INDEX idx_audit_events_timestamp ON audit_events(event_timestamp DESC);

-- Create index on event_type for filtering
CREATE INDEX idx_audit_events_type ON audit_events(event_type);

-- Create index on current_hash for chain verification
CREATE INDEX idx_audit_events_hash ON audit_events(current_hash);

-- ==================== State Machine Tables ====================

-- State machine states table
CREATE TABLE IF NOT EXISTS state_machine_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state_name VARCHAR(50) NOT NULL UNIQUE,
    state_description TEXT,
    is_valid_state BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- State transitions table
CREATE TABLE IF NOT EXISTS state_transitions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    transition_reason TEXT,
    transition_metadata JSONB,
    transition_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (from_state) REFERENCES state_machine_states(state_name),
    FOREIGN KEY (to_state) REFERENCES state_machine_states(state_name)
);

-- Create index on transition_timestamp for queries
CREATE INDEX idx_state_transitions_timestamp ON state_transitions(transition_timestamp DESC);

-- ==================== Risk Management Tables ====================

-- Risk ledger (double-entry accounting)
CREATE TABLE IF NOT EXISTS risk_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id UUID NOT NULL,
    account_id VARCHAR(100) NOT NULL,
    asset VARCHAR(20) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL, -- 'DEBIT' or 'CREDIT'
    reference_type VARCHAR(50), -- 'ORDER', 'POSITION', 'FEE', etc.
    reference_id UUID,
    transaction_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_double_entry CHECK (
        (transaction_type = 'DEBIT' AND amount <= 0) OR
        (transaction_type = 'CREDIT' AND amount >= 0)
    )
);

-- Create index on transaction_id for queries
CREATE INDEX idx_risk_ledger_transaction ON risk_ledger(transaction_id);

-- Create index on account_id for queries
CREATE INDEX idx_risk_ledger_account ON risk_ledger(account_id);

-- Create index on transaction_timestamp for queries
CREATE INDEX idx_risk_ledger_timestamp ON risk_ledger(transaction_timestamp DESC);

-- Risk limits table
CREATE TABLE IF NOT EXISTS risk_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    limit_type VARCHAR(50) NOT NULL,
    limit_value DECIMAL(20, 8) NOT NULL,
    limit_currency VARCHAR(10) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_limit_type UNIQUE (limit_type)
);

-- Risk events table
CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL, -- 'VIOLATION', 'WARNING', 'INFO'
    event_description TEXT NOT NULL,
    event_data JSONB,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index on event_timestamp for queries
CREATE INDEX idx_risk_events_timestamp ON risk_events(event_timestamp DESC);

-- Create index on event_type for filtering
CREATE INDEX idx_risk_events_type ON risk_events(event_type);

-- ==================== Trading Tables ====================

-- Positions table
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL, -- 'LONG' or 'SHORT'
    quantity DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    leverage DECIMAL(4, 2) DEFAULT 1.0,
    is_open BOOLEAN DEFAULT TRUE,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_open_position UNIQUE (exchange, symbol, side) DEFERRABLE INITIALLY DEFERRED
);

-- Create index on exchange and symbol for queries
CREATE INDEX idx_positions_exchange_symbol ON positions(exchange, symbol);

-- Create index on is_open for queries
CREATE INDEX idx_positions_open ON positions(is_open) WHERE is_open = TRUE;

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exchange_order_id VARCHAR(100),
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    order_type VARCHAR(20) NOT NULL, -- 'MARKET', 'LIMIT', 'STOP', etc.
    side VARCHAR(10) NOT NULL, -- 'BUY' or 'SELL'
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8),
    stop_price DECIMAL(20, 8),
    status VARCHAR(20) NOT NULL, -- 'PENDING', 'OPEN', 'FILLED', 'PARTIALLY_FILLED', 'CANCELLED', 'REJECTED'
    filled_quantity DECIMAL(20, 8) DEFAULT 0,
    average_price DECIMAL(20, 8),
    fees DECIMAL(20, 8) DEFAULT 0,
    fee_currency VARCHAR(10),
    client_order_id VARCHAR(100),
    order_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index on exchange and symbol for queries
CREATE INDEX idx_orders_exchange_symbol ON orders(exchange, symbol);

-- Create index on status for queries
CREATE INDEX idx_orders_status ON orders(status);

-- Create index on created_at for queries
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);

-- ==================== Metrics Tables (TimescaleDB Hypertables) ====================

-- Market data table
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open_price DECIMAL(20, 8),
    high_price DECIMAL(20, 8),
    low_price DECIMAL(20, 8),
    close_price DECIMAL(20, 8),
    volume DECIMAL(20, 8),
    quote_volume DECIMAL(20, 8),
    trades_count INTEGER,
    timeframe VARCHAR(10), -- '1m', '5m', '15m', '1h', '4h', '1d'
    raw_data JSONB
);

-- Convert to hypertable (if not already)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'market_data'
    ) THEN
        PERFORM create_hypertable('market_data', 'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- Create index on time, exchange, symbol for queries
CREATE INDEX IF NOT EXISTS idx_market_data_time ON market_data(time DESC, exchange, symbol);

-- System metrics table
CREATE TABLE IF NOT EXISTS system_metrics (
    time TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(20, 8) NOT NULL,
    metric_tags JSONB,
    metric_metadata JSONB
);

-- Convert to hypertable (if not already)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'system_metrics'
    ) THEN
        PERFORM create_hypertable('system_metrics', 'time',
            chunk_time_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- Create index on time and metric_name for queries
CREATE INDEX IF NOT EXISTS idx_system_metrics_time ON system_metrics(time DESC, metric_name);

-- ==================== Initial Data ====================

-- Insert initial state machine states
INSERT INTO state_machine_states (state_name, state_description) VALUES
    ('BOOT', 'System boot state'),
    ('NORMAL', 'Normal operation state'),
    ('DEGRADED_1', 'First level degradation'),
    ('DEGRADED_2', 'Second level degradation'),
    ('DEGRADED_3', 'Third level degradation'),
    ('EMERGENCY', 'Emergency state'),
    ('SHUTDOWN', 'System shutdown state')
ON CONFLICT (state_name) DO NOTHING;

-- Insert initial risk limits
INSERT INTO risk_limits (limit_type, limit_value) VALUES
    ('MAX_R_PER_TRADE', 1.0),
    ('MAX_PORTFOLIO_R', 5.0),
    ('MAX_POSITION_SIZE', 10000.0),
    ('MAX_LEVERAGE', 10.0),
    ('MAX_DAILY_LOSS', 500.0)
ON CONFLICT (limit_type) DO NOTHING;

-- ==================== Grants ====================

-- Grant necessary permissions to bot_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO bot_user;

-- ==================== Maintenance ====================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_state_machine_states_updated_at
    BEFORE UPDATE ON state_machine_states
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_risk_limits_updated_at
    BEFORE UPDATE ON risk_limits
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==================== Completion ====================

-- Log initialization completion
INSERT INTO audit_events (event_type, event_source, event_data, current_hash)
VALUES (
    'DATABASE_INITIALIZED',
    'init-db.sql',
    '{"message": "Database initialized successfully", "version": "1.0.0"}',
    encode(digest('DATABASE_INITIALIZED:' || NOW()::text, 'sha256'), 'hex')
);

-- Output message
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'CRYPTOTEHNOLOG Database Initialized';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Database: trading_dev';
    RAISE NOTICE 'User: bot_user';
    RAISE NOTICE 'Extensions: timescaledb, uuid-ossp, pgcrypto';
    RAISE NOTICE 'Tables created: 12+';
    RAISE NOTICE 'Hypertables created: 2 (market_data, system_metrics)';
    RAISE NOTICE '========================================';
END $$;
