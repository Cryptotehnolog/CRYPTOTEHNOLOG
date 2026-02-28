-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 006
-- Description: Monitoring, Alerts, and Advanced Analytics Tables
-- Created: 2026-02-28
-- Author: CRYPTOTEHNOLOG Team
-- ============================================================

-- ============================================================
-- Section 1: Monitoring Tables
-- ============================================================

-- Performance Metrics (detailed performance tracking)
CREATE TABLE IF NOT EXISTS performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_category VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(20),
    tags JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_metric_category CHECK (
        metric_category IN (
            'latency', 'throughput', 'error_rate', 'resource_usage',
            'order_latency', 'fill_rate', 'api_latency', 'db_latency'
        )
    )
);

-- API Request Logs
CREATE TABLE IF NOT EXISTS api_request_logs (
    id BIGSERIAL PRIMARY KEY,
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms DOUBLE PRECISION,
    request_size_bytes BIGINT,
    response_size_bytes BIGINT,
    user_agent VARCHAR(500),
    ip_address VARCHAR(45),
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_api_method CHECK (method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH'))
);

-- ============================================================
-- Section 2: Alerts Tables
-- ============================================================

-- Alert Rules
CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) UNIQUE NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    condition_expr TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    cooldown_seconds INTEGER DEFAULT 300,
    enabled BOOLEAN DEFAULT TRUE,
    notification_channels JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_alert_type CHECK (
        alert_type IN (
            'threshold', 'anomaly', 'rate', 'state_change',
            'error_rate', 'latency', 'availability'
        )
    ),
    CONSTRAINT chk_severity CHECK (
        severity IN ('info', 'warning', 'error', 'critical')
    )
);

-- Alert Events
CREATE TABLE IF NOT EXISTS alert_events (
    id BIGSERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL REFERENCES alert_rules(id),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    message TEXT,
    value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    state VARCHAR(20) DEFAULT 'firing',
    metadata JSONB DEFAULT '{}'::jsonb,
    fired_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT chk_alert_state CHECK (state IN ('firing', 'resolved', 'acknowledged'))
);

-- ============================================================
-- Section 3: Advanced Analytics
-- ============================================================

-- Trade Analytics (aggregated trade data)
CREATE TABLE IF NOT EXISTS trade_analytics (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    
    -- Volume metrics
    total_volume DOUBLE PRECISION DEFAULT 0,
    buy_volume DOUBLE PRECISION DEFAULT 0,
    sell_volume DOUBLE PRECISION DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    
    -- Price metrics
    open_price DOUBLE PRECISION,
    high_price DOUBLE PRECISION,
    low_price DOUBLE PRECISION,
    close_price DOUBLE PRECISION,
    vwap DOUBLE PRECISION,
    
    -- Execution metrics
    avg_fill_latency_ms DOUBLE PRECISION,
    avg_order_latency_ms DOUBLE PRECISION,
    fill_rate DOUBLE PRECISION,
    rejection_rate DOUBLE PRECISION,
    
    -- P&L metrics
    total_realized_pnl DOUBLE PRECISION DEFAULT 0,
    total_unrealized_pnl DOUBLE PRECISION DEFAULT 0,
    avg_trade_pnl DOUBLE PRECISION,
    
    -- Risk metrics
    max_position_size DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    var_95 DOUBLE PRECISION,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_trade_analytics_date_symbol UNIQUE (symbol, trade_date)
);

-- Symbol Performance
CREATE TABLE IF NOT EXISTS symbol_performance (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL UNIQUE,
    
    -- Performance metrics
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DOUBLE PRECISION,
    
    -- P&L
    total_pnl DOUBLE PRECISION DEFAULT 0,
    avg_pnl DOUBLE PRECISION,
    max_pnl DOUBLE PRECISION,
    min_pnl DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    
    -- Timing
    avg_holding_time_seconds DOUBLE PRECISION,
    
    -- Risk
    sharpe_ratio DOUBLE PRECISION,
    sortino_ratio DOUBLE PRECISION,
    profit_factor DOUBLE PRECISION,
    
    -- Metadata
    first_trade_at TIMESTAMP WITH TIME ZONE,
    last_trade_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- Section 4: Indexes
-- ============================================================

-- Performance Metrics indexes
CREATE INDEX IF NOT EXISTS idx_performance_metrics_category ON performance_metrics(metric_category, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_name ON performance_metrics(metric_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp DESC);

-- API Request Logs indexes
CREATE INDEX IF NOT EXISTS idx_api_request_logs_endpoint ON api_request_logs(endpoint, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_request_logs_status ON api_request_logs(status) WHERE status >= 400;
CREATE INDEX IF NOT EXISTS idx_api_request_logs_timestamp ON api_request_logs(timestamp DESC);

-- Alert Rules indexes
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_alert_rules_severity ON alert_rules(severity);

-- Alert Events indexes
CREATE INDEX IF NOT EXISTS idx_alert_events_rule ON alert_events(rule_id, fired_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_events_state ON alert_events(state) WHERE state = 'firing';
CREATE INDEX IF NOT EXISTS idx_alert_events_fired ON alert_events(fired_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_events_severity ON alert_events(severity) WHERE severity IN ('error', 'critical');

-- Trade Analytics indexes
CREATE INDEX IF NOT EXISTS idx_trade_analytics_date ON trade_analytics(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trade_analytics_symbol ON trade_analytics(symbol);

-- Symbol Performance indexes
CREATE INDEX IF NOT EXISTS idx_symbol_performance_symbol ON symbol_performance(symbol);

-- ============================================================
-- Default Alert Rules
-- ============================================================

INSERT INTO alert_rules (rule_name, alert_type, condition_expr, severity, cooldown_seconds) VALUES
    ('high_error_rate', 'error_rate', 'error_rate > 0.05', 'error', 60),
    ('high_latency', 'latency', 'avg_latency_ms > 1000', 'warning', 300),
    ('low_fill_rate', 'threshold', 'fill_rate < 0.95', 'warning', 300),
    ('high_rejection_rate', 'threshold', 'rejection_rate > 0.1', 'error', 120),
    ('circuit_breaker_open', 'state_change', 'circuit_breaker_state = "open"', 'critical', 30),
    ('emergency_stop', 'state_change', 'state = "emergency"', 'critical', 0)
ON CONFLICT (rule_name) DO NOTHING;

-- ============================================================
-- Migration Metadata
-- ============================================================

INSERT INTO schema_migrations (version, description)
VALUES ('006', 'Monitoring, Alerts, and Advanced Analytics Tables')
ON CONFLICT (version) DO NOTHING;

-- ============================================================
-- Comments for Documentation
-- ============================================================

COMMENT ON TABLE performance_metrics IS 'Detailed performance tracking metrics';
COMMENT ON TABLE api_request_logs IS 'API request/response logging';
COMMENT ON TABLE alert_rules IS 'Alert rule definitions';
COMMENT ON TABLE alert_events IS 'Alert event instances';
COMMENT ON TABLE trade_analytics IS 'Aggregated trade analytics by symbol and date';
COMMENT ON TABLE symbol_performance IS 'Symbol-level performance metrics';
