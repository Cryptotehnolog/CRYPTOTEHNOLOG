-- ==================== CRYPTOTEHNOLOG Migration ====================
-- Description: Add missing tables for Control Plane (Database + Event Bus)
-- Created: 2026-02-28
-- Author: CRYPTOTEHNOLOG Team
-- ============================================================

-- Сначала создаем таблицу миграций
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    checksum VARCHAR(64)
);

-- ============================================================
-- Migration 004: Event Bus Tables (missing)
-- ============================================================

-- Event Store (append-only event log for Event Sourcing)
CREATE TABLE IF NOT EXISTS event_store (
    id BIGSERIAL PRIMARY KEY,
    aggregate_id VARCHAR(200) NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    event_data JSONB NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    causation_id VARCHAR(200),
    correlation_id UUID,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_event_store_aggregate_version UNIQUE (aggregate_id, version),
    CONSTRAINT chk_version_positive CHECK (version > 0)
);

-- Event Consumers (tracking processed events per consumer)
CREATE TABLE IF NOT EXISTS event_consumers (
    id BIGSERIAL PRIMARY KEY,
    consumer_name VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(200) NOT NULL,
    last_processed_version INTEGER NOT NULL,
    last_processed_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active',
    CONSTRAINT uq_consumer_aggregate UNIQUE (consumer_name, aggregate_id)
);

-- Event Bus Subscriptions (subscription management)
CREATE TABLE IF NOT EXISTS event_subscriptions (
    id SERIAL PRIMARY KEY,
    subscription_name VARCHAR(100) UNIQUE NOT NULL,
    event_types TEXT[] NOT NULL,
    filter_expression JSONB DEFAULT '{}'::jsonb,
    handler_module VARCHAR(200),
    handler_function VARCHAR(200),
    enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Published Events (outbox pattern for reliable delivery)
-- Only create if table doesn't exist - avoid overwriting with incompatible schema
CREATE TABLE IF NOT EXISTS published_events (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL,
    topic VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    headers JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(20) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add missing columns if they don't exist (for idempotency)
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'published_events' AND column_name = 'status') THEN
        ALTER TABLE published_events ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'published_events' AND column_name = 'delivered_at') THEN
        ALTER TABLE published_events ADD COLUMN delivered_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Dead Letter Events (failed events for manual inspection)
CREATE TABLE IF NOT EXISTS dead_letter_events (
    id BIGSERIAL PRIMARY KEY,
    original_event_id BIGINT NOT NULL,
    original_event_type VARCHAR(100) NOT NULL,
    original_aggregate_id VARCHAR(200) NOT NULL,
    payload JSONB NOT NULL,
    error_message TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMP WITH TIME ZONE,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Add missing columns if they don't exist
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'dead_letter_events' AND column_name = 'resolved') THEN
        ALTER TABLE dead_letter_events ADD COLUMN resolved BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Default Subscriptions
INSERT INTO event_subscriptions (subscription_name, event_types, handler_module, handler_function, priority) VALUES
    ('state_machine_listener', ARRAY['OrderCreated', 'OrderFilled', 'OrderCancelled', 'PositionOpened', 'PositionClosed'], 'src.core.listeners', 'handle_state_event', 100),
    ('risk_check_listener', ARRAY['OrderCreated', 'PositionOpened', 'PositionClosed'], 'src.core.listeners', 'handle_risk_event', 90),
    ('audit_listener', ARRAY['*'], 'src.core.listeners', 'handle_audit_event', 50),
    ('metrics_listener', ARRAY['OrderFilled', 'PositionClosed', 'RiskViolation'], 'src.core.listeners', 'handle_metrics_event', 10)
ON CONFLICT (subscription_name) DO NOTHING;

-- ============================================================
-- Migration 006: Monitoring Tables (missing)
-- ============================================================

-- Performance Metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_category VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(20),
    tags JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
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
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Alert Events
CREATE TABLE IF NOT EXISTS alert_events (
    id BIGSERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    message TEXT,
    value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    state VARCHAR(20) DEFAULT 'firing',
    metadata JSONB DEFAULT '{}'::jsonb,
    fired_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Trade Analytics
CREATE TABLE IF NOT EXISTS trade_analytics (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    total_volume DOUBLE PRECISION DEFAULT 0,
    buy_volume DOUBLE PRECISION DEFAULT 0,
    sell_volume DOUBLE PRECISION DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    open_price DOUBLE PRECISION,
    high_price DOUBLE PRECISION,
    low_price DOUBLE PRECISION,
    close_price DOUBLE PRECISION,
    vwap DOUBLE PRECISION,
    avg_fill_latency_ms DOUBLE PRECISION,
    avg_order_latency_ms DOUBLE PRECISION,
    fill_rate DOUBLE PRECISION,
    rejection_rate DOUBLE PRECISION,
    total_realized_pnl DOUBLE PRECISION DEFAULT 0,
    total_unrealized_pnl DOUBLE PRECISION DEFAULT 0,
    avg_trade_pnl DOUBLE PRECISION,
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
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DOUBLE PRECISION,
    total_pnl DOUBLE PRECISION DEFAULT 0,
    avg_pnl DOUBLE PRECISION,
    max_pnl DOUBLE PRECISION,
    min_pnl DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    avg_holding_time_seconds DOUBLE PRECISION,
    sharpe_ratio DOUBLE PRECISION,
    sortino_ratio DOUBLE PRECISION,
    profit_factor DOUBLE PRECISION,
    first_trade_at TIMESTAMP WITH TIME ZONE,
    last_trade_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Default Alert Rules
INSERT INTO alert_rules (rule_name, alert_type, condition_expr, severity, cooldown_seconds) VALUES
    ('high_error_rate', 'error_rate', 'error_rate > 0.05', 'error', 60),
    ('high_latency', 'latency', 'avg_latency_ms > 1000', 'warning', 300),
    ('low_fill_rate', 'threshold', 'fill_rate < 0.95', 'warning', 300),
    ('high_rejection_rate', 'threshold', 'rejection_rate > 0.1', 'error', 120),
    ('circuit_breaker_open', 'state_change', 'circuit_breaker_state = open', 'critical', 30),
    ('emergency_stop', 'state_change', 'state = emergency', 'critical', 0)
ON CONFLICT (rule_name) DO NOTHING;

-- ============================================================
-- Migration 005: Backup/Recovery Tables (missing)
-- ============================================================

-- Backup History
CREATE TABLE IF NOT EXISTS backup_history (
    id SERIAL PRIMARY KEY,
    backup_type VARCHAR(20) NOT NULL,
    backup_method VARCHAR(50) NOT NULL,
    file_path TEXT,
    file_size_bytes BIGINT,
    checksum VARCHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Recovery Points
CREATE TABLE IF NOT EXISTS recovery_points (
    id SERIAL PRIMARY KEY,
    recovery_time TIMESTAMP WITH TIME ZONE NOT NULL UNIQUE,
    backup_id INTEGER,
    wal_location TEXT,
    is_consistent BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- System State Snapshots
CREATE TABLE IF NOT EXISTS system_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_type VARCHAR(50) NOT NULL,
    snapshot_data JSONB NOT NULL,
    version INTEGER NOT NULL,
    checksum VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

-- System Health Checks
CREATE TABLE IF NOT EXISTS health_checks (
    id BIGSERIAL PRIMARY KEY,
    check_name VARCHAR(100) NOT NULL,
    component VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Component Heartbeats
CREATE TABLE IF NOT EXISTS component_heartbeats (
    id SERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL UNIQUE,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'alive',
    version VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Maintenance Tasks
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL UNIQUE,
    task_type VARCHAR(50) NOT NULL,
    schedule_expr VARCHAR(100),
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    next_run_at TIMESTAMP WITH TIME ZONE,
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Maintenance Task History
CREATE TABLE IF NOT EXISTS maintenance_task_history (
    id BIGSERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    rows_affected BIGINT DEFAULT 0,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Default Maintenance Tasks
INSERT INTO maintenance_tasks (task_name, task_type, schedule_expr, enabled) VALUES
    ('daily_vacuum', 'vacuum', '0 2 * * *', TRUE),
    ('hourly_analyze', 'analyze', '0 * * * *', TRUE),
    ('daily_backup', 'backup', '0 3 * * *', TRUE),
    ('daily_snapshot', 'snapshot', '0 4 * * *', TRUE),
    ('hourly_health_check', 'health_check', '0 * * * *', TRUE),
    ('cleanup_old_events', 'cleanup', '0 5 * * 0', TRUE)
ON CONFLICT (task_name) DO NOTHING;

-- ============================================================
-- Migration 002: Additional Risk Tables (missing)
-- ============================================================

-- Risk Event History
CREATE TABLE IF NOT EXISTS risk_event_history (
    id BIGSERIAL PRIMARY KEY,
    event_date DATE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    total_events INTEGER NOT NULL DEFAULT 0,
    allowed_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    total_risk_amount DOUBLE PRECISION DEFAULT 0,
    symbols JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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
-- Record Migration
-- ============================================================

INSERT INTO schema_migrations (version, description)
VALUES ('control_plane_additions', 'Add missing Control Plane tables for Event Bus, Monitoring, Backup')
ON CONFLICT (version) DO NOTHING;

-- Verify
SELECT 'Migration completed. Tables created:' as status;
SELECT COUNT(*) as new_tables FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'event_store', 'event_consumers', 'event_subscriptions', 
    'published_events', 'dead_letter_events', 'performance_metrics',
    'api_request_logs', 'alert_rules', 'alert_events',
    'trade_analytics', 'symbol_performance', 'backup_history',
    'recovery_points', 'system_snapshots', 'health_checks',
    'component_heartbeats', 'maintenance_tasks', 'maintenance_task_history',
    'risk_event_history', 'daily_risk_summary'
);
