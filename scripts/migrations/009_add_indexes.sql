-- ============================================================
-- Migration 009: Add indexes for all tables
-- ============================================================
-- This migration must run AFTER all tables are created
-- Indexes that were incorrectly placed in control_plane_additions.sql

-- Event Bus indexes
CREATE INDEX IF NOT EXISTS idx_event_store_aggregate ON event_store(aggregate_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_event_store_aggregate_type ON event_store(aggregate_type);
CREATE INDEX IF NOT EXISTS idx_event_store_event_type ON event_store(event_type);
CREATE INDEX IF NOT EXISTS idx_event_store_timestamp ON event_store(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_event_store_correlation ON event_store(correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_consumers_name ON event_consumers(consumer_name);
CREATE INDEX IF NOT EXISTS idx_published_events_status ON published_events(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_dead_letter_resolved ON dead_letter_events(resolved) WHERE resolved = FALSE;

-- Monitoring indexes
CREATE INDEX IF NOT EXISTS idx_performance_metrics_category ON performance_metrics(metric_category, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_request_logs_endpoint ON api_request_logs(endpoint, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_request_logs_timestamp ON api_request_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alert_events_fired ON alert_events(fired_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_analytics_date ON trade_analytics(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_symbol_performance_symbol ON symbol_performance(symbol);

-- Risk indexes
CREATE INDEX IF NOT EXISTS idx_risk_limits_enabled ON risk_limits(enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_risk_events_symbol ON risk_events(symbol) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_risk_events_type ON risk_events(event_type);
CREATE INDEX IF NOT EXISTS idx_risk_events_allowed ON risk_events(allowed) WHERE allowed = FALSE;
CREATE INDEX IF NOT EXISTS idx_risk_events_date ON risk_events(timestamp DESC, event_type);

-- Trading indexes
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_state ON orders(state);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_client_order_id ON orders(client_order_id) WHERE client_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_exchange_order_id ON orders(exchange_order_id) WHERE exchange_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_order_history_timestamp ON order_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_positions_opened_at ON positions(opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_position_history_closed_at ON position_history(closed_at DESC);

-- Migration metadata
INSERT INTO schema_migrations (version, description)
VALUES ('009', 'Add indexes for all tables')
ON CONFLICT (version) DO NOTHING;
