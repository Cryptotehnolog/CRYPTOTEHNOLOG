-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 011
-- Description: Risk Engine persistence foundation and audit tables
-- Author: CRYPTOTEHNOLOG Team
-- Created: 2026-03-19
-- ============================================================

-- ============================================================
-- Section 1: Pre-trade risk checks audit
-- ============================================================

CREATE TABLE IF NOT EXISTS risk_checks (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100),
    symbol VARCHAR(50),
    system_state VARCHAR(32) NOT NULL,
    decision VARCHAR(10) NOT NULL,
    reason VARCHAR(100),
    risk_r NUMERIC(20, 8) NOT NULL DEFAULT 0,
    position_size_usd NUMERIC(20, 8) NOT NULL DEFAULT 0,
    position_size_base NUMERIC(20, 8) NOT NULL DEFAULT 0,
    current_total_r NUMERIC(20, 8) NOT NULL DEFAULT 0,
    max_total_r NUMERIC(20, 8) NOT NULL DEFAULT 0,
    correlation_with_portfolio NUMERIC(20, 8),
    recommended_exchange VARCHAR(50),
    max_size NUMERIC(20, 8),
    check_duration_ms INTEGER NOT NULL DEFAULT 0,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_risk_checks_decision
        CHECK (decision IN ('ALLOW', 'REJECT')),
    CONSTRAINT chk_risk_checks_duration
        CHECK (check_duration_ms >= 0)
);

CREATE INDEX IF NOT EXISTS idx_risk_checks_created_at
    ON risk_checks(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_risk_checks_order_id
    ON risk_checks(order_id)
    WHERE order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_risk_checks_symbol
    ON risk_checks(symbol)
    WHERE symbol IS NOT NULL;

-- ============================================================
-- Section 2: Position risk ledger (new domain model, not legacy)
-- ============================================================

CREATE TABLE IF NOT EXISTS position_risk_ledger (
    position_id VARCHAR(100) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    initial_stop NUMERIC(20, 8) NOT NULL,
    current_stop NUMERIC(20, 8) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    risk_capital_usd NUMERIC(20, 8) NOT NULL,
    initial_risk_usd NUMERIC(20, 8) NOT NULL,
    initial_risk_r NUMERIC(20, 8) NOT NULL,
    current_risk_usd NUMERIC(20, 8) NOT NULL,
    current_risk_r NUMERIC(20, 8) NOT NULL,
    trailing_state VARCHAR(20) NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_position_risk_ledger_side
        CHECK (side IN ('long', 'short')),
    CONSTRAINT chk_position_risk_ledger_quantity
        CHECK (quantity > 0),
    CONSTRAINT chk_position_risk_ledger_risk_capital
        CHECK (risk_capital_usd > 0),
    CONSTRAINT chk_position_risk_ledger_risk_values
        CHECK (
            initial_risk_usd >= 0
            AND initial_risk_r >= 0
            AND current_risk_usd >= 0
            AND current_risk_r >= 0
        )
);

CREATE INDEX IF NOT EXISTS idx_position_risk_ledger_symbol
    ON position_risk_ledger(symbol);

CREATE INDEX IF NOT EXISTS idx_position_risk_ledger_updated_at
    ON position_risk_ledger(updated_at DESC);

CREATE TABLE IF NOT EXISTS position_risk_ledger_audit (
    id BIGSERIAL PRIMARY KEY,
    position_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    operation VARCHAR(20) NOT NULL,
    old_stop NUMERIC(20, 8),
    new_stop NUMERIC(20, 8),
    old_risk_r NUMERIC(20, 8),
    new_risk_r NUMERIC(20, 8),
    trailing_state VARCHAR(20),
    reason TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_position_risk_ledger_audit_operation
        CHECK (operation IN ('REGISTER', 'UPDATE', 'RELEASE', 'STATE_SYNC', 'TERMINATE'))
);

CREATE INDEX IF NOT EXISTS idx_position_risk_ledger_audit_position
    ON position_risk_ledger_audit(position_id, recorded_at DESC);

-- ============================================================
-- Section 3: Trailing stop snapshot + movement audit
-- ============================================================

CREATE TABLE IF NOT EXISTS trailing_stops (
    position_id VARCHAR(100) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    current_stop NUMERIC(20, 8) NOT NULL,
    previous_stop NUMERIC(20, 8) NOT NULL,
    trailing_state VARCHAR(20) NOT NULL,
    last_evaluation_type VARCHAR(20) NOT NULL,
    last_tier VARCHAR(8) NOT NULL,
    last_mode VARCHAR(20) NOT NULL,
    last_pnl_r NUMERIC(20, 8) NOT NULL,
    last_risk_before NUMERIC(20, 8) NOT NULL,
    last_risk_after NUMERIC(20, 8) NOT NULL,
    last_reason TEXT,
    last_evaluated_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_trailing_stops_tier
        CHECK (last_tier IN ('T1', 'T2', 'T3', 'T4')),
    CONSTRAINT chk_trailing_stops_evaluation_type
        CHECK (last_evaluation_type IN ('MOVE', 'BLOCKED', 'STATE_SYNC', 'TERMINATE')),
    CONSTRAINT chk_trailing_stops_mode
        CHECK (last_mode IN ('NORMAL', 'STRUCTURAL', 'EMERGENCY'))
);

CREATE INDEX IF NOT EXISTS idx_trailing_stops_symbol
    ON trailing_stops(symbol);

CREATE INDEX IF NOT EXISTS idx_trailing_stops_updated_at
    ON trailing_stops(updated_at DESC);

CREATE TABLE IF NOT EXISTS trailing_stop_movements (
    id BIGSERIAL PRIMARY KEY,
    position_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    old_stop NUMERIC(20, 8) NOT NULL,
    new_stop NUMERIC(20, 8) NOT NULL,
    pnl_r NUMERIC(20, 8) NOT NULL,
    evaluation_type VARCHAR(20) NOT NULL,
    tier VARCHAR(8) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    system_state VARCHAR(32) NOT NULL,
    risk_before NUMERIC(20, 8) NOT NULL,
    risk_after NUMERIC(20, 8) NOT NULL,
    should_execute BOOLEAN NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_trailing_stop_movements_tier
        CHECK (tier IN ('T1', 'T2', 'T3', 'T4')),
    CONSTRAINT chk_trailing_stop_movements_evaluation_type
        CHECK (evaluation_type IN ('MOVE', 'BLOCKED', 'STATE_SYNC', 'TERMINATE')),
    CONSTRAINT chk_trailing_stop_movements_mode
        CHECK (mode IN ('NORMAL', 'STRUCTURAL', 'EMERGENCY'))
);

CREATE INDEX IF NOT EXISTS idx_trailing_stop_movements_position
    ON trailing_stop_movements(position_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_trailing_stop_movements_symbol
    ON trailing_stop_movements(symbol, created_at DESC);

-- ============================================================
-- Section 4: Comments for documentation
-- ============================================================

COMMENT ON TABLE risk_checks IS 'Audit trail предторговых проверок нового Risk Engine';
COMMENT ON TABLE position_risk_ledger IS 'Новый позиционный ledger риска Фазы 5, не legacy risk_ledger';
COMMENT ON TABLE position_risk_ledger_audit IS 'Аудит изменений позиционного risk ledger';
COMMENT ON TABLE trailing_stops IS 'Актуальные snapshots trailing stop по открытым позициям';
COMMENT ON TABLE trailing_stop_movements IS 'История всех оценок и движений trailing stop';

-- ============================================================
-- Section 5: Migration metadata
-- ============================================================

INSERT INTO schema_migrations (version, description)
VALUES ('011', 'Risk Engine persistence foundation and audit tables')
ON CONFLICT (version) DO NOTHING;
