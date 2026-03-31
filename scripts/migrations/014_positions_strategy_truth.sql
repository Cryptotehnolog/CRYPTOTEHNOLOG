-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 014
-- Description: Surface canonical strategy truth for open/closed positions
-- Author: CRYPTOTEHNOLOG Team
-- Created: 2026-03-31
-- ============================================================

ALTER TABLE position_risk_ledger
    ADD COLUMN IF NOT EXISTS strategy_id VARCHAR(100);

ALTER TABLE closed_position_history
    ADD COLUMN IF NOT EXISTS strategy_id VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_position_risk_ledger_strategy_symbol
    ON position_risk_ledger(strategy_id, symbol);

CREATE INDEX IF NOT EXISTS idx_closed_position_history_strategy_closed_at
    ON closed_position_history(strategy_id, closed_at DESC);

COMMENT ON COLUMN position_risk_ledger.strategy_id IS 'Каноническая стратегия активной позиции';
COMMENT ON COLUMN closed_position_history.strategy_id IS 'Каноническая стратегия закрытой позиции';

INSERT INTO schema_migrations (version, description)
VALUES ('014', 'Surface canonical strategy truth for positions')
ON CONFLICT (version) DO NOTHING;
