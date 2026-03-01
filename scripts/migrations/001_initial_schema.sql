-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 001
-- Description: Initial schema - Core tables for State Machine, Audit, and System
-- Author: CRYPTOTEHNOLOG Team
-- Created: 2026-02-28
-- ============================================================

-- ============================================================
-- Section 1: State Machine Tables
-- ============================================================

-- State Machine States (current state tracking)
CREATE TABLE IF NOT EXISTS state_machine_states (
    id SERIAL PRIMARY KEY,
    current_state VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT uq_state_machine_single_row CHECK (id = 1)
);

-- State Transitions (transition history for audit)
CREATE TABLE IF NOT EXISTS state_transitions (
    id BIGSERIAL PRIMARY KEY,
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    trigger VARCHAR(100) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    operator VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    duration_ms INTEGER,
    correlation_id UUID,
    
    CONSTRAINT chk_from_to_state_diff CHECK (from_state <> to_state)
);

-- Indexes for State Machine tables
CREATE INDEX IF NOT EXISTS idx_state_transitions_timestamp 
    ON state_transitions(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_state_transitions_operator 
    ON state_transitions(operator);

CREATE INDEX IF NOT EXISTS idx_state_transitions_correlation 
    ON state_transitions(correlation_id);

CREATE INDEX IF NOT EXISTS idx_state_transitions_from_to 
    ON state_transitions(from_state, to_state);

-- ============================================================
-- Section 2: Audit Events Tables
-- ============================================================

-- Audit Events (comprehensive audit trail)
CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(100),
    old_state JSONB,
    new_state JSONB,
    operator VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    severity VARCHAR(20) DEFAULT 'INFO',
    
    CONSTRAINT chk_audit_severity CHECK (
        severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    )
);

-- Indexes for Audit tables
CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp 
    ON audit_events(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_event_type 
    ON audit_events(event_type);

CREATE INDEX IF NOT EXISTS idx_audit_events_entity 
    ON audit_events(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_operator 
    ON audit_events(operator);

CREATE INDEX IF NOT EXISTS idx_audit_events_severity 
    ON audit_events(severity) WHERE severity IN ('ERROR', 'CRITICAL');

-- ============================================================
-- Section 3: System Metrics Tables
-- ============================================================

-- System Metrics (time-series metrics)
CREATE TABLE IF NOT EXISTS system_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    labels JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_metric_type CHECK (
        metric_type IN ('gauge', 'counter', 'histogram', 'summary')
    )
);

-- Indexes for System Metrics
CREATE INDEX IF NOT EXISTS idx_system_metrics_name_timestamp 
    ON system_metrics(metric_name, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp 
    ON system_metrics(timestamp DESC);

-- ============================================================
-- Section 4: Initial Data
-- ============================================================

-- Insert initial state for State Machine (only if not exists)
INSERT INTO state_machine_states (id, current_state, version, updated_at)
VALUES (1, 'boot', 0, NOW())
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Migration Metadata
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    checksum VARCHAR(64)
);

-- Record this migration
INSERT INTO schema_migrations (version, description)
VALUES ('001', 'Initial schema - Core tables for State Machine, Audit, and System')
ON CONFLICT (version) DO NOTHING;

-- ============================================================
-- Comments for Documentation
-- ============================================================

COMMENT ON TABLE state_machine_states IS 'Current state of the state machine - single row table';
COMMENT ON TABLE state_transitions IS 'History of all state transitions with metadata';
COMMENT ON TABLE audit_events IS 'Comprehensive audit trail for all system events';
COMMENT ON TABLE system_metrics IS 'Time-series system metrics for monitoring';
COMMENT ON TABLE schema_migrations IS 'Migration tracking table';
