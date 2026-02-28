-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 002
-- Description: Risk Management Tables - Risk events, limits, and ledger
-- Author: CRYPTOTEHNOLOG Team
-- Created: 2026-02-28
-- ============================================================

-- ============================================================
-- Section 1: Risk Limits Tables
-- ============================================================

-- Risk Limits (configurable risk parameters)
CREATE TABLE IF NOT EXISTS risk_limits (
    id SERIAL PRIMARY KEY,
    limit_name VARCHAR(100) UNIQUE NOT NULL,
    limit_type VARCHAR(50) NOT NULL,
    max_value DOUBLE PRECISION NOT NULL,
    current_value DOUBLE PRECISION DEFAULT 0,
    min_value DOUBLE PRECISION DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_limit_type CHECK (
        limit_type IN (
            'POSITION_SIZE', 'PORTFOLIO_EXPOSURE', 'DRAWDOWN', 
            'DAILY_LOSS', 'MAX_LEVERAGE', 'ORDER_SIZE', 
            'CONCENTRATION', 'CORRELATION', 'VOLATILITY'
        )
    ),
    CONSTRAINT chk_max_min_values CHECK (max_value >= min_value)
);

-- Risk Ledger (rolling risk tracking)
CREATE TABLE IF NOT EXISTS risk_ledger (
    id BIGSERIAL PRIMARY KEY,
    limit_type VARCHAR(50) NOT NULL,
    limit_value DOUBLE PRECISION NOT NULL,
    current_value DOUBLE PRECISION NOT NULL,
    period_seconds INTEGER,
    reset_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_ledger_limit_type CHECK (
        limit_type IN (
            'POSITION_SIZE', 'PORTFOLIO_EXPOSURE', 'DRAWDOWN', 
            'DAILY_LOSS', 'ORDER_SIZE', 'CONCENTRATION'
        )
    ),
    CONSTRAINT chk_current_vs_limit CHECK (current_value >= 0)
);

-- Unique constraint for limit_type in risk_ledger
ALTER TABLE risk_ledger 
ADD CONSTRAINT uq_risk_ledger_limit_type UNIQUE (limit_type);

-- ============================================================
-- Section 2: Risk Events Tables
-- ============================================================

-- Risk Events (all risk-related events)
CREATE TABLE IF NOT EXISTS risk_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    symbol VARCHAR(50),
    side VARCHAR(10),
    size DOUBLE PRECISION,
    price DOUBLE PRECISION,
    risk_amount DOUBLE PRECISION,
    allowed BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT,
    rejected_order_id VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_risk_event_type CHECK (
            event_type IN (
                'POSITION_SIZE_EXCEEDED', 'DRAWDOWN_EXCEEDED', 
                'DAILY_LOSS_LIMIT', 'LEVERAGE_EXCEEDED',
                'ORDER_SIZE_EXCEEDED', 'CONCENTRATION_EXCEEDED',
                'CORRELATION_EXCEEDED', 'VOLATILITY_EXCEEDED',
                'RISK_CHECK_PASSED', 'EMERGENCY_STOP'
            )
    ),
    CONSTRAINT chk_side CHECK (side IN ('BUY', 'SELL', 'SHORT', 'LONG') OR side IS NULL)
);

-- Risk Event History (compressed historical data)
CREATE TABLE IF NOT EXISTS risk_event_history (
    id BIGSERIAL PRIMARY KEY,
    event_date DATE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    total_events INTEGER NOT NULL DEFAULT 0,
    allowed_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    total_risk_amount DOUBLE PRECISION DEFAULT 0,
    symbols JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_counts CHECK (
        allowed_count >= 0 AND 
        rejected_count >= 0 AND 
        total_events = allowed_count + rejected_count
    )
);

-- ============================================================
-- Section 3: Risk Aggregates (Materialized Views Alternative)
-- ============================================================

-- Daily Risk Summary
CREATE TABLE IF NOT EXISTS daily_risk_summary (
    id SERIAL PRIMARY KEY,
    trade_date DATE NOT NULL UNIQUE,
    total_orders_submitted INTEGER DEFAULT 0,
    total_orders_rejected INTEGER DEFAULT 0,
    total_risk_violations INTEGER DEFAULT 0,
    max_drawdown_pct DOUBLE PRECISION,
    max_position_size DOUBLE PRECISION,
    max_portfolio_exposure DOUBLE PRECISION,
    total_risk_amount DOUBLE PRECISION DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- Section 4: Indexes
-- ============================================================

-- Risk Limits indexes
CREATE INDEX IF NOT EXISTS idx_risk_limits_type 
    ON risk_limits(limit_type);

CREATE INDEX IF NOT EXISTS idx_risk_limits_enabled 
    ON risk_limits(enabled) WHERE enabled = TRUE;

-- Risk Ledger indexes
CREATE INDEX IF NOT EXISTS idx_risk_ledger_reset_at 
    ON risk_ledger(reset_at) WHERE reset_at IS NOT NULL;

-- Risk Events indexes
CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp 
    ON risk_events(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_risk_events_symbol 
    ON risk_events(symbol) WHERE symbol IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_risk_events_type 
    ON risk_events(event_type);

CREATE INDEX IF NOT EXISTS idx_risk_events_allowed 
    ON risk_events(allowed) WHERE allowed = FALSE;

CREATE INDEX IF NOT EXISTS idx_risk_events_date 
    ON risk_events(timestamp DESC, event_type);

-- Risk Event History indexes
CREATE INDEX IF NOT EXISTS idx_risk_event_history_date 
    ON risk_event_history(event_date DESC);

-- Daily Risk Summary indexes
CREATE INDEX IF NOT EXISTS idx_daily_risk_summary_date 
    ON daily_risk_summary(trade_date DESC);

-- ============================================================
-- Section 5: Default Risk Limits
-- ============================================================

INSERT INTO risk_limits (limit_name, limit_type, max_value, min_value, enabled) VALUES
    ('max_position_size_usd', 'POSITION_SIZE', 10000.0, 0, TRUE),
    ('max_portfolio_risk', 'PORTFOLIO_EXPOSURE', 5.0, 0, TRUE),
    ('max_drawdown_pct', 'DRAWDOWN', 0.15, 0, TRUE),
    ('max_daily_loss_usd', 'DAILY_LOSS', 1000.0, 0, TRUE),
    ('max_leverage', 'MAX_LEVERAGE', 10.0, 1.0, TRUE),
    ('max_order_size_usd', 'ORDER_SIZE', 5000.0, 0, TRUE),
    ('max_concentration_pct', 'CONCENTRATION', 0.30, 0, TRUE)
ON CONFLICT (limit_name) DO NOTHING;

-- ============================================================
-- Section 6: Migration Metadata
-- ============================================================

INSERT INTO schema_migrations (version, description)
VALUES ('002', 'Risk Management Tables - Risk events, limits, and ledger')
ON CONFLICT (version) DO NOTHING;

-- ============================================================
-- Comments for Documentation
-- ============================================================

COMMENT ON TABLE risk_limits IS 'Configurable risk parameters and thresholds';
COMMENT ON TABLE risk_ledger IS 'Rolling risk tracking with period-based reset';
COMMENT ON TABLE risk_events IS 'All risk-related events with acceptance status';
COMMENT ON TABLE risk_event_history IS 'Compressed historical risk event data';
COMMENT ON TABLE daily_risk_summary IS 'Daily aggregated risk metrics';
