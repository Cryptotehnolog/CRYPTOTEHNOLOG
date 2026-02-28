-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 004
-- Description: Event Bus Tables - Event Store for Event Sourcing
-- Created: 2026-02-28
-- Author: CRYPTOTEHNOLOG Team
-- ============================================================

-- ============================================================
-- Section 1: Event Store Tables
-- ============================================================

-- Event Store (append-only event log for Event Sourcing)
CREATE TABLE IF NOT EXISTS event_store (
    id BIGSERIAL PRIMARY KEY,
    aggregate_id VARCHAR(200) NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    
    -- Event data (immutable after creation)
    event_data JSONB NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Causation and correlation
    causation_id VARCHAR(200),
    correlation_id UUID,
    
    -- Timestamp
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT uq_event_store_aggregate_version UNIQUE (aggregate_id, version),
    CONSTRAINT chk_version_positive CHECK (version > 0),
    CONSTRAINT chk_aggregate_type CHECK (
        aggregate_type IN (
            'Order', 'Position', 'RiskCheck', 'StateMachine',
            'TradingSession', 'Portfolio', 'Signal'
        )
    )
);

-- Event Consumers (tracking processed events per consumer)
CREATE TABLE IF NOT EXISTS event_consumers (
    id BIGSERIAL PRIMARY KEY,
    consumer_name VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(200) NOT NULL,
    last_processed_version INTEGER NOT NULL,
    last_processed_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active',
    
    CONSTRAINT uq_consumer_aggregate UNIQUE (consumer_name, aggregate_id),
    CONSTRAINT chk_consumer_status CHECK (status IN ('active', 'paused', 'error', 'completed'))
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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_priority_range CHECK (priority BETWEEN -100 AND 100)
);

-- Published Events (outbox pattern for reliable delivery)
CREATE TABLE IF NOT EXISTS published_events (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES event_store(id) ON DELETE CASCADE,
    topic VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    headers JSONB DEFAULT '{}'::jsonb,
    
    -- Delivery status
    status VARCHAR(20) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_published_status CHECK (
        status IN ('pending', 'publishing', 'delivered', 'failed', 'dead_letter')
    )
);

-- ============================================================
-- Section 2: Dead Letter Queue
-- ============================================================

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

-- ============================================================
-- Section 3: Indexes
-- ============================================================

-- Event Store indexes
CREATE INDEX IF NOT EXISTS idx_event_store_aggregate ON event_store(aggregate_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_event_store_aggregate_type ON event_store(aggregate_type);
CREATE INDEX IF NOT EXISTS idx_event_store_event_type ON event_store(event_type);
CREATE INDEX IF NOT EXISTS idx_event_store_timestamp ON event_store(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_event_store_correlation ON event_store(correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_store_causation ON event_store(causation_id) WHERE causation_id IS NOT NULL;

-- Event Consumers indexes
CREATE INDEX IF NOT EXISTS idx_event_consumers_name ON event_consumers(consumer_name);
CREATE INDEX IF NOT EXISTS idx_event_consumers_status ON event_consumers(status) WHERE status = 'active';

-- Event Subscriptions indexes
CREATE INDEX IF NOT EXISTS idx_event_subscriptions_enabled ON event_subscriptions(enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_event_subscriptions_priority ON event_subscriptions(priority DESC);

-- Published Events indexes
CREATE INDEX IF NOT idx_published_events_status ON published_events(status) WHERE status = 'pending';
CREATE INDEX IF NOT idx_published_events_topic ON published_events(topic);
CREATE INDEX IF NOT idx_published_events_created ON published_events(created_at DESC);

-- Dead Letter Events indexes
CREATE INDEX IF NOT EXISTS idx_dead_letter_resolved ON dead_letter_events(resolved) WHERE resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_dead_letter_created ON dead_letter_events(created_at DESC);

-- ============================================================
-- Default Subscriptions
-- ============================================================

INSERT INTO event_subscriptions (subscription_name, event_types, handler_module, handler_function, priority) VALUES
    ('state_machine_listener', ARRAY['OrderCreated', 'OrderFilled', 'OrderCancelled', 'PositionOpened', 'PositionClosed'], 'src.core.listeners', 'handle_state_event', 100),
    ('risk_check_listener', ARRAY['OrderCreated', 'PositionOpened', 'PositionClosed'], 'src.core.listeners', 'handle_risk_event', 90),
    ('audit_listener', ARRAY['*'], 'src.core.listeners', 'handle_audit_event', 50),
    ('metrics_listener', ARRAY['OrderFilled', 'PositionClosed', 'RiskViolation'], 'src.core.listeners', 'handle_metrics_event', 10)
ON CONFLICT (subscription_name) DO NOTHING;

-- ============================================================
-- Migration Metadata
-- ============================================================

INSERT INTO schema_migrations (version, description)
VALUES ('004', 'Event Bus Tables - Event Store for Event Sourcing')
ON CONFLICT (version) DO NOTHING;

-- ============================================================
-- Comments for Documentation
-- ============================================================

COMMENT ON TABLE event_store IS 'Append-only event log for Event Sourcing';
COMMENT ON TABLE event_consumers IS 'Tracking processed events per consumer';
COMMENT ON TABLE event_subscriptions IS 'Event bus subscription management';
COMMENT ON TABLE published_events IS 'Outbox pattern for reliable event delivery';
COMMENT ON TABLE dead_letter_events IS 'Failed events for manual inspection and retry';
