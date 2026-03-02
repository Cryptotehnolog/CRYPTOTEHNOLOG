-- ============================================================
-- Migration: 008 - Fix risk_events CHECK constraint
-- ============================================================
-- Add RISK_VIOLATION and ORDER_REJECTED to allowed event types
-- These event types are emitted by RiskListener but were missing from constraint

-- Drop existing constraint
ALTER TABLE risk_events DROP CONSTRAINT IF EXISTS chk_risk_event_type;

-- Add new constraint with additional event types
ALTER TABLE risk_events ADD CONSTRAINT chk_risk_event_type CHECK (
    event_type IN (
        'POSITION_SIZE_EXCEEDED', 'DRAWDOWN_EXCEEDED',
        'DAILY_LOSS_LIMIT', 'LEVERAGE_EXCEEDED',
        'ORDER_SIZE_EXCEEDED', 'CONCENTRATION_EXCEEDED',
        'CORRELATION_EXCEEDED', 'VOLATILITY_EXCEEDED',
        'RISK_CHECK_PASSED', 'EMERGENCY_STOP',
        'RISK_VIOLATION', 'ORDER_REJECTED'
    )
);

-- Migration metadata
INSERT INTO schema_migrations (version, description)
VALUES ('008', 'Fix risk_events CHECK constraint - add RISK_VIOLATION and ORDER_REJECTED')
ON CONFLICT (version) DO NOTHING;
