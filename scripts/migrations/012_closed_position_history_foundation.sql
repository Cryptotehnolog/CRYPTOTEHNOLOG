-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 012
-- Description: Closed position history foundation for Risk Engine
-- Author: CRYPTOTEHNOLOG Team
-- Created: 2026-03-30
-- ============================================================

-- ============================================================
-- Section 1: Closed position history foundation
-- ============================================================

CREATE TABLE IF NOT EXISTS closed_position_history (
    position_id VARCHAR(100) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    initial_stop NUMERIC(20, 8) NOT NULL,
    current_stop NUMERIC(20, 8) NOT NULL,
    trailing_state VARCHAR(20) NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ NOT NULL,
    realized_pnl_r NUMERIC(20, 8),

    CONSTRAINT chk_closed_position_history_side
        CHECK (side IN ('long', 'short')),
    CONSTRAINT chk_closed_position_history_quantity
        CHECK (quantity > 0)
);

CREATE INDEX IF NOT EXISTS idx_closed_position_history_closed_at
    ON closed_position_history(closed_at DESC);

CREATE INDEX IF NOT EXISTS idx_closed_position_history_symbol
    ON closed_position_history(symbol, closed_at DESC);

-- ============================================================
-- Section 2: Comments for documentation
-- ============================================================

COMMENT ON TABLE closed_position_history IS 'Каноническая history foundation закрытых позиций Risk Engine';

-- ============================================================
-- Section 3: Migration metadata
-- ============================================================

INSERT INTO schema_migrations (version, description)
VALUES ('012', 'Closed position history foundation for Risk Engine')
ON CONFLICT (version) DO NOTHING;
